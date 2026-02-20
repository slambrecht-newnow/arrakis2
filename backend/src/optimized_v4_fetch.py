"""
Optimized V4 data fetching using Multicall3 batching.

Reduces 200+ sequential RPC calls to 2 batched multicall requests.
"""

import time
from dataclasses import dataclass
from typing import Any

from web3 import Web3

from .config import STATE_VIEW, POOL_ID_BYTES, TICK_SPACING
from .multicall import (
    build_get_slot0_call,
    build_get_liquidity_call,
    build_get_tick_bitmap_call,
    build_get_tick_liquidity_call,
    decode_slot0_result,
    decode_liquidity_result,
    decode_tick_bitmap_result,
    decode_tick_liquidity_result,
    execute_multicall,
)


@dataclass
class TimingResults:
    """Timing breakdown for optimized fetch."""
    phase1_bitmap_ms: float
    phase2_parse_ms: float
    phase3_tick_liquidity_ms: float
    total_ms: float
    num_bitmap_calls: int
    num_tick_calls: int


@dataclass
class V4PoolData:
    """Complete V4 pool data from optimized fetch."""
    sqrt_price_x96: int
    current_tick: int
    protocol_fee: int
    lp_fee: int
    current_liquidity: int
    initialized_ticks: list[int]
    tick_liquidity: dict[int, tuple[int, int]]  # tick -> (gross, net)
    timing: TimingResults


def _parse_bitmap_for_ticks(
    bitmaps: dict[int, int],
    tick_spacing: int
) -> list[int]:
    """Parse bitmap results to find initialized ticks."""
    initialized_ticks = []
    for word_pos, bitmap in bitmaps.items():
        if bitmap == 0:
            continue
        for bit_pos in range(256):
            if bitmap & (1 << bit_pos):
                tick = ((word_pos * 256) + bit_pos) * tick_spacing
                initialized_ticks.append(tick)
    return sorted(initialized_ticks)


def fetch_all_v4_data_sync(
    w3: Web3,
    search_range: int = 100
) -> V4PoolData:
    """
    Fetch all V4 pool data using Multicall3 batching (sync version).

    Batches 200+ calls into just 2 multicall requests:
    - Phase 1: Slot0 + Liquidity + All bitmap words (single multicall)
    - Phase 2: Parse bitmaps to find initialized ticks (local computation)
    - Phase 3: All tick liquidity queries (single multicall)

    Args:
        w3: Web3 instance
        search_range: Number of bitmap words to scan in each direction

    Returns:
        V4PoolData with all pool data and timing breakdown
    """
    stateview_addr = Web3.to_checksum_address(STATE_VIEW)
    total_start = time.perf_counter()

    # ========== PHASE 1: Batch bitmap + basic state queries ==========
    phase1_start = time.perf_counter()

    calls: list[tuple[str, bool, bytes]] = []

    # Add slot0 and liquidity calls
    calls.append(build_get_slot0_call(stateview_addr, POOL_ID_BYTES))
    calls.append(build_get_liquidity_call(stateview_addr, POOL_ID_BYTES))

    # Add all bitmap calls
    word_positions = list(range(-search_range, search_range + 1))
    for word_pos in word_positions:
        calls.append(build_get_tick_bitmap_call(stateview_addr, POOL_ID_BYTES, word_pos))

    # Execute single multicall for all phase 1 data
    results = execute_multicall(w3, calls)

    # Parse results
    slot0_success, slot0_data = results[0]
    liq_success, liq_data = results[1]

    sqrt_price_x96, current_tick, protocol_fee, lp_fee = decode_slot0_result(slot0_data)
    current_liquidity = decode_liquidity_result(liq_data)

    # Parse bitmap results
    bitmaps: dict[int, int] = {}
    for i, word_pos in enumerate(word_positions):
        success, data = results[i + 2]  # +2 for slot0 and liquidity
        if success and data:
            bitmaps[word_pos] = decode_tick_bitmap_result(data)

    phase1_ms = (time.perf_counter() - phase1_start) * 1000

    # ========== PHASE 2: Parse bitmaps ==========
    phase2_start = time.perf_counter()
    initialized_ticks = _parse_bitmap_for_ticks(bitmaps, TICK_SPACING)
    phase2_ms = (time.perf_counter() - phase2_start) * 1000

    # ========== PHASE 3: Batch tick liquidity queries ==========
    phase3_start = time.perf_counter()

    tick_liquidity: dict[int, tuple[int, int]] = {}
    if initialized_ticks:
        tick_calls = [
            build_get_tick_liquidity_call(stateview_addr, POOL_ID_BYTES, tick)
            for tick in initialized_ticks
        ]
        tick_results = execute_multicall(w3, tick_calls)

        for i, tick in enumerate(initialized_ticks):
            success, data = tick_results[i]
            if success and data:
                gross, net = decode_tick_liquidity_result(data)
                tick_liquidity[tick] = (gross, net)

    phase3_ms = (time.perf_counter() - phase3_start) * 1000

    total_ms = (time.perf_counter() - total_start) * 1000

    timing = TimingResults(
        phase1_bitmap_ms=phase1_ms,
        phase2_parse_ms=phase2_ms,
        phase3_tick_liquidity_ms=phase3_ms,
        total_ms=total_ms,
        num_bitmap_calls=len(word_positions),
        num_tick_calls=len(initialized_ticks),
    )

    return V4PoolData(
        sqrt_price_x96=sqrt_price_x96,
        current_tick=current_tick,
        protocol_fee=protocol_fee,
        lp_fee=lp_fee,
        current_liquidity=current_liquidity,
        initialized_ticks=initialized_ticks,
        tick_liquidity=tick_liquidity,
        timing=timing,
    )


def fetch_original_sequential(
    w3: Web3,
    search_range: int = 100
) -> tuple[dict[str, Any], float]:
    """
    Fetch V4 pool data using original sequential method (for benchmarking).

    This mirrors the original implementation's approach of individual RPC calls.

    Returns:
        Tuple of (data_dict, elapsed_ms)
    """
    from .abis import STATEVIEW_ABI_EXTENDED

    stateview = w3.eth.contract(
        address=Web3.to_checksum_address(STATE_VIEW),
        abi=STATEVIEW_ABI_EXTENDED
    )

    start = time.perf_counter()

    # Individual slot0 call
    slot0 = stateview.functions.getSlot0(POOL_ID_BYTES).call()

    # Individual liquidity call
    liquidity = stateview.functions.getLiquidity(POOL_ID_BYTES).call()

    # Individual bitmap calls (sequential loop)
    initialized_ticks = []
    for word_pos in range(-search_range, search_range + 1):
        try:
            bitmap = stateview.functions.getTickBitmap(POOL_ID_BYTES, word_pos).call()
            if bitmap == 0:
                continue
            for bit_pos in range(256):
                if bitmap & (1 << bit_pos):
                    tick = ((word_pos * 256) + bit_pos) * TICK_SPACING
                    initialized_ticks.append(tick)
        except Exception:
            continue

    # Individual tick liquidity calls (sequential loop)
    tick_liquidity = {}
    for tick in sorted(initialized_ticks):
        try:
            gross, net = stateview.functions.getTickLiquidity(POOL_ID_BYTES, tick).call()
            tick_liquidity[tick] = (gross, net)
        except Exception:
            continue

    elapsed_ms = (time.perf_counter() - start) * 1000

    data = {
        "slot0": slot0,
        "liquidity": liquidity,
        "initialized_ticks": sorted(initialized_ticks),
        "tick_liquidity": tick_liquidity,
    }

    return data, elapsed_ms
