"""
TVL (Total Value Locked) calculations for Uniswap V4 pools.

Provides StateView helper functions and two methods for calculating pool TVL:
on-chain tick iteration and GraphQL API.
"""

import requests
from web3.contract import Contract

from .amm_math import (
    tick_to_sqrt_price,
    calculate_token0_amount,
    calculate_token1_amount,
    sqrt_price_x96_to_sqrt_price,
)
from .config import UNISWAP_GRAPHQL_URL
from .liquidity_distribution import find_initialized_ticks


# StateView Helper Functions

def get_slot0(stateview: Contract, pool_id: bytes) -> tuple[int, int, int, int]:
    """
    Get pool slot0 data from StateView contract.

    Args:
        stateview: StateView contract instance
        pool_id: Pool ID as bytes32

    Returns:
        Tuple of (sqrtPriceX96, tick, protocolFee, lpFee)
    """
    result = stateview.functions.getSlot0(pool_id).call()
    return (result[0], result[1], result[2], result[3])


def get_tick_liquidity(stateview: Contract, pool_id: bytes, tick: int) -> tuple[int, int]:
    """
    Get liquidity data at a specific tick.

    Args:
        stateview: StateView contract instance
        pool_id: Pool ID as bytes32
        tick: Tick index to query

    Returns:
        Tuple of (liquidityGross, liquidityNet)
    """
    result = stateview.functions.getTickLiquidity(pool_id, tick).call()
    return (result[0], result[1])


def get_pool_liquidity(stateview: Contract, pool_id: bytes) -> int:
    """
    Get current pool liquidity L := sqrt(k).

    Args:
        stateview: StateView contract instance
        pool_id: Pool ID as bytes32

    Returns:
        Current liquidity value
    """
    return stateview.functions.getLiquidity(pool_id).call()


def get_tick_bitmap(stateview: Contract, pool_id: bytes, word_pos: int) -> int:
    """
    Get tick bitmap word at a specific position.

    Args:
        stateview: StateView contract instance
        pool_id: Pool ID as bytes32
        word_pos: Bitmap word position (int16)

    Returns:
        256-bit bitmap word
    """
    return stateview.functions.getTickBitmap(pool_id, word_pos).call()


# TVL Calculation Methods

def calculate_tvl_from_ticks(
    stateview: Contract,
    pool_id: bytes,
    tick_spacing: int,
    search_range: int = 100
) -> tuple[float, float]:
    """
    Calculate TVL by iterating through tick ranges (on-chain method).

    This method scans initialized ticks, accumulates liquidityNet deltas,
    and calculates token amounts for each tick range using V3/V4 math.

    Args:
        stateview: StateView contract instance with STATEVIEW_ABI_EXTENDED
        pool_id: Pool ID as bytes32
        tick_spacing: Pool's tick spacing (e.g., 60)
        search_range: Number of bitmap words to scan in each direction

    Returns:
        Tuple of (token0_amount_raw, token1_amount_raw) in wei units
    """
    # Find all initialized ticks
    initialized_ticks = find_initialized_ticks(
        stateview, pool_id, tick_spacing, search_range
    )

    if not initialized_ticks:
        return 0.0, 0.0

    # Get current sqrt price (using Decimal for precision)
    sqrt_price_x96, _, _, _ = get_slot0(stateview, pool_id)
    sqrt_price_current = float(sqrt_price_x96_to_sqrt_price(sqrt_price_x96))

    total_amount0 = 0.0
    total_amount1 = 0.0

    # Track cumulative liquidity as we traverse ticks
    cumulative_liquidity = 0
    sorted_ticks = sorted(initialized_ticks)

    for i, tick in enumerate(sorted_ticks):
        # Get liquidity delta at this tick
        _, liquidity_net = get_tick_liquidity(stateview, pool_id, tick)

        # Add delta to get liquidity for the next range
        cumulative_liquidity += liquidity_net

        # Calculate amounts for range from this tick to next
        if i < len(sorted_ticks) - 1:
            tick_low = tick
            tick_high = sorted_ticks[i + 1]

            sqrt_price_low = tick_to_sqrt_price(tick_low)
            sqrt_price_high = tick_to_sqrt_price(tick_high)

            if cumulative_liquidity > 0:
                amount0 = calculate_token0_amount(
                    cumulative_liquidity, sqrt_price_current,
                    sqrt_price_low, sqrt_price_high
                )
                amount1 = calculate_token1_amount(
                    cumulative_liquidity, sqrt_price_current,
                    sqrt_price_low, sqrt_price_high
                )

                total_amount0 += amount0
                total_amount1 += amount1

    return total_amount0, total_amount1


def fetch_pool_tvl_graphql(pool_id: str) -> dict:
    """
    Fetch pool TVL from Uniswap GraphQL API.

    This method queries the Uniswap interface gateway for pool-specific
    TVL data including token balances and USD values.

    Args:
        pool_id: Pool ID as hex string (with or without 0x prefix)

    Returns:
        Dict with pool data including:
        - token0/token1: Token info (id, symbol, decimals)
        - token0Balance/token1Balance: Raw token balances
        - liquidity: Pool liquidity
        - sqrtPrice: Current sqrt price
        - tvl: TVL data (value, token0Value, token1Value)

    Raises:
        requests.RequestException: If API request fails
        KeyError: If response structure is unexpected
    """
    # Ensure pool_id has 0x prefix
    if not pool_id.startswith("0x"):
        pool_id = "0x" + pool_id

    query = """
    query PoolData($chain: Chain!, $poolId: String!) {
      v4Pool(chain: $chain, poolId: $poolId) {
        poolId
        token0 {
          address
          symbol
          decimals
        }
        token1 {
          address
          symbol
          decimals
        }
        token0Supply
        token1Supply
        totalLiquidity {
          value
        }
        feeTier
        tickSpacing
      }
    }
    """

    headers = {
        "Content-Type": "application/json",
        "Origin": "https://app.uniswap.org",
        "Referer": "https://app.uniswap.org/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }

    response = requests.post(
        UNISWAP_GRAPHQL_URL,
        json={"query": query, "variables": {"chain": "ETHEREUM", "poolId": pool_id}},
        headers=headers,
        timeout=30
    )
    response.raise_for_status()

    data = response.json()

    if "errors" in data:
        raise ValueError(f"GraphQL errors: {data['errors']}")

    pool_data = data.get("data", {}).get("v4Pool")
    if pool_data is None:
        raise ValueError(f"Pool not found: {pool_id}")

    return pool_data
