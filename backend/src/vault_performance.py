"""
Arrakis vault performance tracking and benchmark comparisons.

Tracks vault token holdings over time, compares against HODL and
full-range (constant-product) LP benchmarks.
"""

import logging
import math

from web3.contract import Contract

logger = logging.getLogger(__name__)


def get_vault_underlying_at_block(
    vault: Contract, block: int
) -> tuple[int, int]:
    """Get vault totalUnderlying (amount0, amount1) at a historical block."""
    amount0, amount1 = vault.functions.totalUnderlying().call(
        block_identifier=block
    )
    return amount0, amount1


def batch_vault_underlying(
    vault: Contract, blocks: list[int]
) -> list[tuple[int, int, int]]:
    """
    Fetch vault underlying at multiple blocks.

    Returns list of (block, amount0, amount1) tuples.
    """
    results = []
    for block in blocks:
        try:
            a0, a1 = get_vault_underlying_at_block(vault, block)
            results.append((block, a0, a1))
        except Exception:
            logger.warning("Vault underlying query failed at block %d", block, exc_info=True)
            results.append((block, 0, 0))
    return results


def calculate_hodl_value(
    initial_amount0: float,
    initial_amount1: float,
    price0_usd: float,
    price1_usd: float,
) -> float:
    """Calculate HODL portfolio value: just hold initial token amounts."""
    return initial_amount0 * price0_usd + initial_amount1 * price1_usd


def calculate_fullrange_lp_value(
    initial_amount0: float,
    initial_amount1: float,
    initial_price0_usd: float,
    initial_price1_usd: float,
    current_price0_usd: float,
    current_price1_usd: float,
) -> float:
    """
    Calculate full-range (x*y=k) LP value at current prices.

    A full-range LP on V2 follows x*y=k. Given initial deposit,
    the value at new prices follows the impermanent loss formula:
    V_lp = V_hodl * 2*sqrt(r) / (1+r) where r = price_ratio_change.

    We compute for each token independently and combine.
    """
    initial_value = (
        initial_amount0 * initial_price0_usd
        + initial_amount1 * initial_price1_usd
    )

    if initial_value == 0:
        return 0.0

    # For a two-asset LP, the IL formula uses the relative price change
    # between the two assets. We compute the price ratio.
    # Initial price ratio: price0/price1
    if initial_price1_usd == 0 or current_price1_usd == 0:
        return initial_value

    initial_ratio = initial_price0_usd / initial_price1_usd
    current_ratio = current_price0_usd / current_price1_usd

    if initial_ratio == 0:
        return initial_value

    r = current_ratio / initial_ratio

    # Impermanent loss multiplier: 2*sqrt(r) / (1 + r)
    il_multiplier = 2 * math.sqrt(r) / (1 + r)

    # HODL value at current prices
    hodl_value = calculate_hodl_value(
        initial_amount0, initial_amount1, current_price0_usd, current_price1_usd
    )

    return hodl_value * il_multiplier


def get_vault_performance_timeseries(
    vault: Contract,
    blocks: list[int],
    token0_prices_usd: list[float],
    token1_prices_usd: list[float],
    token0_decimals: int = 18,
    token1_decimals: int = 18,
) -> list[dict]:
    """
    Compute vault value, HODL value, and full-range LP value over time.

    Returns list of dicts with block, vault_usd, hodl_usd, fullrange_usd.
    """
    # Get initial vault amounts
    try:
        init_a0, init_a1 = get_vault_underlying_at_block(vault, blocks[0])
    except Exception:
        logger.warning("Failed to fetch initial vault state at block %d", blocks[0], exc_info=True)
        init_a0, init_a1 = 0, 0

    init_amount0 = init_a0 / (10 ** token0_decimals)
    init_amount1 = init_a1 / (10 ** token1_decimals)
    init_price0 = token0_prices_usd[0]
    init_price1 = token1_prices_usd[0]

    results = []
    for i, block in enumerate(blocks):
        try:
            a0, a1 = get_vault_underlying_at_block(vault, block)
        except Exception:
            logger.warning("Vault underlying query failed at block %d", block, exc_info=True)
            a0, a1 = 0, 0

        amount0 = a0 / (10 ** token0_decimals)
        amount1 = a1 / (10 ** token1_decimals)
        p0 = token0_prices_usd[i]
        p1 = token1_prices_usd[i]

        vault_usd = amount0 * p0 + amount1 * p1
        hodl_usd = calculate_hodl_value(init_amount0, init_amount1, p0, p1)
        fullrange_usd = calculate_fullrange_lp_value(
            init_amount0, init_amount1, init_price0, init_price1, p0, p1
        )

        results.append({
            "block": block,
            "amount0": amount0,
            "amount1": amount1,
            "vault_usd": vault_usd,
            "hodl_usd": hodl_usd,
            "fullrange_usd": fullrange_usd,
        })

    return results


def compute_il_factor(price_ratio: float) -> float:
    """
    Compute the impermanent loss multiplier for a given price ratio.

    IL factor = 2*sqrt(r) / (1+r), where r = p_t / p_0.
    Always <= 1.0 (equality at r=1, i.e. no price change).
    """
    if price_ratio <= 0:
        return 0.0
    return 2 * math.sqrt(price_ratio) / (1 + price_ratio)


def compute_annualized_return(
    initial_value: float,
    final_value: float,
    days: float,
) -> float:
    """
    Compute annualized return as a percentage.

    Formula: ((final/initial)^(365/days) - 1) * 100
    """
    if initial_value <= 0 or days <= 0:
        return 0.0
    return (((final_value / initial_value) ** (365.0 / days)) - 1) * 100


def decompose_vault_returns(
    vault_usd: list[float],
    hodl_usd: list[float],
    fullrange_usd: list[float],
) -> list[dict]:
    """
    Decompose vault returns into price return, IL, and management premium.

    Identity: vault = hodl + il_fullrange + management_premium
    - price_return = hodl - hodl[0] (pure price movement)
    - il_fullrange = fullrange - hodl (impermanent loss for full-range LP)
    - management_premium = vault - fullrange (Arrakis active management alpha)
    - total_lp_effect = il_fullrange + management_premium = vault - hodl
    """
    initial_hodl = hodl_usd[0] if hodl_usd else 0.0
    results = []

    for i in range(len(vault_usd)):
        price_return = hodl_usd[i] - initial_hodl
        il_fullrange = fullrange_usd[i] - hodl_usd[i]
        management_premium = vault_usd[i] - fullrange_usd[i]
        total_lp_effect = il_fullrange + management_premium

        results.append({
            "price_return": price_return,
            "il_fullrange": il_fullrange,
            "management_premium": management_premium,
            "total_lp_effect": total_lp_effect,
        })

    return results
