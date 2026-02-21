"""
Active liquidity management tracking for Arrakis vault.

Fetches pool state and vault tick ranges at historical blocks,
detects rebalance events, and computes capital efficiency ratios.
"""

import logging
import math

from web3.contract import Contract

from .amm_math import sqrt_price_x96_to_price, tick_to_sqrt_price

logger = logging.getLogger(__name__)


def get_pool_state_at_block(
    stateview: Contract, pool_id: bytes, block: int
) -> dict:
    """Fetch pool tick, sqrtPriceX96, active liquidity, and price at a block."""
    sqrt_price_x96, tick, _, _ = stateview.functions.getSlot0(pool_id).call(
        block_identifier=block
    )
    liquidity: int = stateview.functions.getLiquidity(pool_id).call(
        block_identifier=block
    )
    price = float(sqrt_price_x96_to_price(sqrt_price_x96)) if sqrt_price_x96 > 0 else 0.0
    return {
        "tick": tick,
        "sqrtPriceX96": sqrt_price_x96,
        "liquidity": liquidity,
        "price": price,
    }


def get_vault_ranges_at_block(
    module: Contract, block: int
) -> list[tuple[int, int]]:
    """Fetch the vault's active tick ranges at a historical block."""
    raw = module.functions.getRanges().call(block_identifier=block)
    return [(r[0], r[1]) for r in raw]


def batch_pool_state_and_ranges(
    stateview: Contract,
    module: Contract,
    pool_id: bytes,
    blocks: list[int],
) -> list[dict]:
    """
    Fetch pool state and vault ranges at multiple blocks.

    Returns list of dicts with block, tick, sqrtPriceX96, liquidity,
    price, and ranges for each sampled block.
    """
    results = []
    for block in blocks:
        try:
            state = get_pool_state_at_block(stateview, pool_id, block)
            ranges = get_vault_ranges_at_block(module, block)
            results.append({
                "block": block,
                "tick": state["tick"],
                "sqrtPriceX96": state["sqrtPriceX96"],
                "liquidity": state["liquidity"],
                "price": state["price"],
                "ranges": ranges,
            })
        except Exception:
            logger.warning(
                "Failed to fetch state/ranges at block %d", block, exc_info=True
            )
            results.append({
                "block": block,
                "tick": 0,
                "sqrtPriceX96": 0,
                "liquidity": 0,
                "price": 0.0,
                "ranges": [],
            })
    return results


def detect_rebalances(
    range_history: list[dict],
) -> list[int]:
    """
    Detect rebalance events by comparing ranges between consecutive samples.

    Returns list of indices where ranges changed from the previous sample.
    """
    rebalance_indices = []
    for i in range(1, len(range_history)):
        prev_ranges = range_history[i - 1]["ranges"]
        curr_ranges = range_history[i]["ranges"]
        if prev_ranges != curr_ranges:
            rebalance_indices.append(i)
    return rebalance_indices


def ranges_to_prices(
    ranges: list[tuple[int, int]],
) -> list[tuple[float, float]]:
    """Convert tick ranges to price ranges (token1 per token0)."""
    price_ranges = []
    for tick_lower, tick_upper in ranges:
        price_lower = tick_to_sqrt_price(tick_lower) ** 2
        price_upper = tick_to_sqrt_price(tick_upper) ** 2
        price_ranges.append((price_lower, price_upper))
    return price_ranges


def compute_capital_efficiency(
    active_liquidity: int,
    raw_amount0: int,
    raw_amount1: int,
) -> float:
    """
    Compute capital efficiency as ratio of actual L vs full-range L.

    Uniswap L is in units of sqrt(token0_raw * token1_raw), so we must
    use raw (wei) token amounts for a comparable full-range L.

    Full-range L = sqrt(x_raw * y_raw).
    CE ratio = L_actual / L_fullrange.

    Returns ratio >= 1.0 for concentrated positions (higher = more efficient).
    """
    if raw_amount0 <= 0 or raw_amount1 <= 0 or active_liquidity <= 0:
        return 0.0

    l_fullrange = math.sqrt(float(raw_amount0) * float(raw_amount1))

    if l_fullrange <= 0:
        return 0.0

    return active_liquidity / l_fullrange
