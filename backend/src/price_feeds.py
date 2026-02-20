"""
Price feed utilities for historical IXS and ETH prices.

Fetches ETH/USD from Chainlink oracle and IXS/ETH from V2 reserves
or V4 sqrtPriceX96 at historical blocks.
"""


import logging

from web3 import Web3
from web3.contract import Contract

from .amm_math import sqrt_price_x96_to_price

logger = logging.getLogger(__name__)


def get_eth_usd_at_block(chainlink: Contract, block: int) -> float:
    """Get ETH/USD price from Chainlink at a historical block."""
    _, answer, _, _, _ = chainlink.functions.latestRoundData().call(
        block_identifier=block
    )
    return answer / 1e8  # Chainlink ETH/USD uses 8 decimals


def get_ixs_eth_price_from_v2(
    pair: Contract, block: int, ixs_is_token0: bool
) -> float:
    """Get IXS/ETH price from V2 reserves at a historical block."""
    reserve0, reserve1, _ = pair.functions.getReserves().call(
        block_identifier=block
    )
    if ixs_is_token0:
        # price = reserve_eth / reserve_ixs (both 18 decimals)
        return reserve1 / reserve0 if reserve0 > 0 else 0.0
    else:
        return reserve0 / reserve1 if reserve1 > 0 else 0.0


def get_ixs_eth_price_from_v4(
    stateview: Contract, pool_id: bytes, block: int,
    ixs_is_currency0: bool
) -> float:
    """Get IXS/ETH price from V4 sqrtPriceX96 at a historical block."""
    sqrt_price_x96, _, _, _ = stateview.functions.getSlot0(pool_id).call(
        block_identifier=block
    )
    if sqrt_price_x96 == 0:
        return 0.0
    # sqrtPriceX96 encodes price as token1/token0
    price_token1_per_token0 = float(sqrt_price_x96_to_price(sqrt_price_x96))
    if ixs_is_currency0:
        # price = token1/token0 = ETH/IXS → IXS/ETH = 1/price... wait:
        # If IXS is currency0, price is ETH per IXS
        return price_token1_per_token0
    else:
        # If IXS is currency1, price is IXS per ETH → invert
        return 1.0 / price_token1_per_token0 if price_token1_per_token0 > 0 else 0.0


def batch_eth_usd_prices(
    chainlink: Contract, blocks: list[int]
) -> list[float]:
    """Fetch ETH/USD at multiple historical blocks."""
    prices = []
    for block in blocks:
        try:
            price = get_eth_usd_at_block(chainlink, block)
            prices.append(price)
        except Exception:
            logger.warning("Failed to fetch ETH/USD at block %d", block, exc_info=True)
            prices.append(0.0)
    return prices


def batch_ixs_prices(
    w3: Web3,
    blocks: list[int],
    migration_block: int,
    pair: Contract,
    stateview: Contract,
    pool_id: bytes,
    ixs_is_token0_v2: bool,
    ixs_is_currency0_v4: bool,
) -> list[float]:
    """Fetch IXS/ETH price at multiple blocks, using V2 pre-migration and V4 post."""
    prices = []
    for block in blocks:
        try:
            if block < migration_block:
                price = get_ixs_eth_price_from_v2(pair, block, ixs_is_token0_v2)
            else:
                price = get_ixs_eth_price_from_v4(
                    stateview, pool_id, block, ixs_is_currency0_v4
                )
            prices.append(price)
        except Exception:
            logger.warning("Failed to fetch IXS price at block %d", block, exc_info=True)
            prices.append(0.0)
    return prices
