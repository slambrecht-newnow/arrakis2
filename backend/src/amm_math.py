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