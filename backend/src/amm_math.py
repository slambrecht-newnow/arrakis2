import math

import pandas as pd
from decimal import Decimal, getcontext

# Set high precision for Decimal operations
getcontext().prec = 50

# Pre-compute 2^96 as Decimal for price conversions
Q96 = Decimal(2 ** 96)


def sqrt_price_x96_to_price(sqrt_price_x96: int) -> Decimal:
    """
    Convert sqrtPriceX96 to human-readable price (token1 per token0).

    Uses Decimal for high precision arithmetic.

    sqrtPriceX96 = sqrt(price) * 2^96
    price = (sqrtPriceX96 / 2^96)^2

    Args:
        sqrt_price_x96: The sqrtPriceX96 value from the pool

    Returns:
        Decimal price (token1 per token0)
    """
    sqrt_price = Decimal(sqrt_price_x96) / Q96
    return sqrt_price ** 2


def sqrt_price_x96_to_sqrt_price(sqrt_price_x96: int) -> Decimal:
    """
    Convert sqrtPriceX96 to sqrt(price).

    Args:
        sqrt_price_x96: The sqrtPriceX96 value from the pool

    Returns:
        Decimal sqrt(price)
    """
    return Decimal(sqrt_price_x96) / Q96


def calculate_token0_amount(liquidity: int, sqrt_price_current: float, sqrt_price_low: float, sqrt_price_high: float) -> float:
    """
    Calculate token0 (ETH) amount for a liquidity position.
    
    token0 = L * (sqrt_price_high - sqrt_price_current) / (sqrt_price_current * sqrt_price_high)
    """
    # Clamp current price to tick range
    sp = max(min(sqrt_price_current, sqrt_price_high), sqrt_price_low)
    
    if sp >= sqrt_price_high:
        return 0.0  # All liquidity is in token1
    
    return liquidity * (sqrt_price_high - sp) / (sp * sqrt_price_high)


def calculate_token1_amount(liquidity: int, sqrt_price_current: float, sqrt_price_low: float, sqrt_price_high: float) -> float:
    """
    Calculate token1 (MORPHO) amount for a liquidity position.
    
    token1 = L * (sqrt_price_current - sqrt_price_low)
    """
    # Clamp current price to tick range
    sp = max(min(sqrt_price_current, sqrt_price_high), sqrt_price_low)
    
    if sp <= sqrt_price_low:
        return 0.0  # All liquidity is in token0
    
    return liquidity * (sp - sqrt_price_low)


def tick_to_sqrt_price(tick: int) -> float:
    """Convert tick to sqrt price: sqrt(1.0001^tick) = 1.0001^(tick/2)"""
    return 1.0001 ** (tick / 2)


def theoretical_v4_slippage(
    amount_wei: int,
    zero_for_one: bool,
    current_tick: int,
    df_liq: pd.DataFrame,
) -> float:
    """Compute theoretical V4 slippage by stepping through tick bands.

    Walks the liquidity distribution starting at current_tick, consuming
    liquidity in each band until the full amount is swapped. Returns
    the gross slippage percentage (fee excluded).
    """
    tick = current_tick
    remaining = float(amount_wei)

    band = df_liq[(df_liq["tick_lower"] <= tick) & (df_liq["tick_upper"] > tick)]
    if band.empty:
        return float("nan")

    row0 = band.iloc[0]
    L = float(row0["active_liquidity"])
    sqrt_p = math.sqrt(1.0001 ** tick)
    spot_price = 1.0001 ** current_tick

    while remaining > 0 and L > 0:
        r = band.iloc[0]
        tick_lower = int(r["tick_lower"])
        tick_upper = int(r["tick_upper"])

        if zero_for_one:
            sqrt_p_lower = math.sqrt(1.0001 ** tick_lower)
            max_dx = L * (1 / sqrt_p_lower - 1 / sqrt_p) if sqrt_p > sqrt_p_lower else 0.0

            if remaining <= max_dx or max_dx <= 0:
                sqrt_p = 1.0 / (1.0 / sqrt_p + remaining / L)
                remaining = 0
            else:
                remaining -= max_dx
                sqrt_p = sqrt_p_lower
                tick = tick_lower - 1
                band = df_liq[(df_liq["tick_lower"] <= tick) & (df_liq["tick_upper"] > tick)]
                if band.empty:
                    break
                L = float(band.iloc[0]["active_liquidity"])
        else:
            sqrt_p_upper = math.sqrt(1.0001 ** tick_upper)
            max_dy = L * (sqrt_p_upper - sqrt_p) if sqrt_p_upper > sqrt_p else 0.0

            if remaining <= max_dy or max_dy <= 0:
                sqrt_p = sqrt_p + remaining / L
                remaining = 0
            else:
                remaining -= max_dy
                sqrt_p = sqrt_p_upper
                tick = tick_upper
                band = df_liq[(df_liq["tick_lower"] <= tick) & (df_liq["tick_upper"] > tick)]
                if band.empty:
                    break
                L = float(band.iloc[0]["active_liquidity"])

    final_price = sqrt_p ** 2
    return abs(spot_price - final_price) / spot_price * 100