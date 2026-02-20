"""
Liquidity distribution analysis for Uniswap V4 pools.

Uses bitmap scanning to efficiently find initialized ticks, then reconstructs
liquidity per tick range by walking up/down from the current tick.

Note: An alternative approach would be to sample all ticks at regular intervals
and query each one. We choose bitmap scanning for RPC efficiency - it only
queries ticks that actually have liquidity positions.
"""

import pandas as pd
from web3.contract import Contract


def find_initialized_ticks(
    stateview: Contract,
    pool_id: bytes,
    tick_spacing: int,
    search_range: int = 100
) -> list[int]:
    """
    Find initialized ticks by scanning the tick bitmap.

    The tick bitmap is organized in words of 256 bits, where each bit represents
    whether a tick is initialized or not.

    Args:
        stateview: StateView contract instance
        pool_id: Pool ID as bytes32
        tick_spacing: Pool's tick spacing (60 for this pool)
        search_range: Number of bitmap words to scan in each direction

    Returns:
        Sorted list of initialized tick indices
    """
    initialized_ticks = []

    for word_pos in range(-search_range, search_range + 1):
        try:
            bitmap = stateview.functions.getTickBitmap(pool_id, word_pos).call()

            if bitmap == 0:
                continue

            for bit_pos in range(256):
                if bitmap & (1 << bit_pos):
                    tick = ((word_pos * 256) + bit_pos) * tick_spacing
                    initialized_ticks.append(tick)
        except Exception:
            continue

    return sorted(initialized_ticks)


def get_tick_liquidity_data(
    stateview: Contract,
    pool_id: bytes,
    ticks: list[int]
) -> list[tuple[int, int, int]]:
    """
    Fetch liquidityGross and liquidityNet for each tick.

    Args:
        stateview: StateView contract instance
        pool_id: Pool ID as bytes32
        ticks: List of tick indices to query

    Returns:
        List of tuples: (tick, liquidityGross, liquidityNet)
    """
    results = []
    for tick in ticks:
        liquidity_gross, liquidity_net = stateview.functions.getTickLiquidity(
            pool_id, tick
        ).call()
        results.append((tick, liquidity_gross, liquidity_net))
    return results


def fetch_liquidity_distribution(
    stateview: Contract,
    pool_id: bytes,
    tick_spacing: int,
    search_range: int = 100
) -> tuple[pd.DataFrame, dict]:
    """
    Fetch liquidity distribution by scanning initialized ticks.

    Args:
        stateview: StateView contract instance
        pool_id: Pool ID as bytes32
        tick_spacing: Pool's tick spacing
        search_range: Number of bitmap words to scan

    Returns:
        Tuple of (DataFrame with tick_lower/tick_upper/active_liquidity, slot dict)
    """
    # Get current pool state
    slot0 = stateview.functions.getSlot0(pool_id).call()
    sqrt_price_x96, current_tick, protocol_fee, lp_fee = slot0
    current_liquidity = stateview.functions.getLiquidity(pool_id).call()

    slot = {
        "sqrt_price_x96": sqrt_price_x96,
        "tick": current_tick,
        "protocol_fee": protocol_fee,
        "lp_fee": lp_fee,
        "liquidity": current_liquidity,
    }

    # Find initialized ticks via bitmap scanning
    initialized_ticks = find_initialized_ticks(stateview, pool_id, tick_spacing, search_range)

    if not initialized_ticks:
        empty_df: pd.DataFrame = pd.DataFrame({"tick_lower": [], "tick_upper": [], "active_liquidity": []})
        return empty_df, slot

    # Get liquidityNet for each initialized tick - loop
    tick_data = get_tick_liquidity_data(stateview, pool_id, initialized_ticks)
    liq_net_by_tick = {tick: liq_net for tick, _, liq_net in tick_data}

    # NOTE here we start creating the bands with the net data we just gathered
    # Snap current tick to grid
    base_tick = (current_tick // tick_spacing) * tick_spacing

    # Split ticks above and below current
    ticks_above = sorted([t for t in initialized_ticks if t > current_tick])
    ticks_below = sorted([t for t in initialized_ticks if t <= current_tick], reverse=True)

    bands = []

    # Walk UPWARD from current tick
    L = current_liquidity
    if ticks_above:
        # Active range: from base_tick to first tick above
        bands.append({
            "tick_lower": base_tick,
            "tick_upper": ticks_above[0],
            "active_liquidity": L,
        })

        for i, t in enumerate(ticks_above):
            L = L + liq_net_by_tick[t]
            next_tick = ticks_above[i + 1] if i + 1 < len(ticks_above) else t + tick_spacing
            bands.append({
                "tick_lower": t,
                "tick_upper": next_tick,
                "active_liquidity": max(L, 0),
            })

    #NOTE Bridge band: from highest tick_below to base_tick (fills the gap)
    if ticks_below and ticks_below[0] < base_tick:
        bands.append({
            "tick_lower": ticks_below[0],
            "tick_upper": base_tick,
            "active_liquidity": current_liquidity,
        })

    # Walk DOWNWARD from current tick
    L = current_liquidity
    for i, t in enumerate(ticks_below):
        L = L - liq_net_by_tick[t]
        lower_tick = ticks_below[i + 1] if i + 1 < len(ticks_below) else t - tick_spacing
        bands.append({
            "tick_lower": lower_tick,
            "tick_upper": t,
            "active_liquidity": max(L, 0),
        })

    df = pd.DataFrame(bands)
    df.sort_values("tick_lower", inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df, slot