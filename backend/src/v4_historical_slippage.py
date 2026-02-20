"""
UniswapV4 slippage calculations at historical blocks.

Similar to slippage.py but passes block_identifier to all .call() invocations,
enabling historical slippage analysis for the IXS migration study.
"""


from web3 import Web3
from web3.contract import Contract

from .amm_math import sqrt_price_x96_to_price


def calculate_v4_slippage_at_block(
    stateview: Contract,
    quoter: Contract,
    pool_id: bytes,
    amount_in_wei: int,
    block: int,
    currency0: str,
    currency1: str,
    fee: int,
    tick_spacing: int,
    hooks: str,
    zero_for_one: bool = True,
) -> dict:
    """
    Calculate V4 slippage at a specific historical block.

    Uses getSlot0 for spot price and Quoter for execution price,
    both at the given block_identifier.
    """
    # Spot price at historical block
    sqrt_price_x96, tick, protocol_fee, lp_fee = stateview.functions.getSlot0(
        pool_id
    ).call(block_identifier=block)

    if sqrt_price_x96 == 0:
        return {"error": "pool not initialized", "block": block}

    # sqrtPriceX96 always encodes token1/token0
    spot_price_t1_per_t0 = float(sqrt_price_x96_to_price(sqrt_price_x96))

    # Quote at historical block
    pool_key = (
        Web3.to_checksum_address(currency0),
        Web3.to_checksum_address(currency1),
        fee,
        tick_spacing,
        Web3.to_checksum_address(hooks),
    )
    params = (pool_key, zero_for_one, amount_in_wei, b"")

    amount_out_wei, gas_estimate = quoter.functions.quoteExactInputSingle(
        params
    ).call(block_identifier=block)

    # Compute execution price in the same units as spot price (token1/token0)
    if zero_for_one:
        # Swapping token0→token1: exec_price = amount_out(t1) / amount_in(t0)
        exec_price = amount_out_wei / amount_in_wei if amount_in_wei > 0 else 0.0
    else:
        # Swapping token1→token0: exec_price = amount_in(t1) / amount_out(t0)
        exec_price = amount_in_wei / amount_out_wei if amount_out_wei > 0 else 0.0

    # Gross slippage (price impact excluding fee)
    fee_pct = lp_fee / 1_000_000  # lpFee is in parts per million
    gross_slippage_pct = abs(spot_price_t1_per_t0 - exec_price) / spot_price_t1_per_t0 * 100 - fee_pct * 100

    # Net slippage (including fee)
    net_slippage_pct = abs(spot_price_t1_per_t0 - exec_price) / spot_price_t1_per_t0 * 100

    return {
        "block": block,
        "spot_price": spot_price_t1_per_t0,
        "execution_price": exec_price,
        "amount_out_wei": amount_out_wei,
        "lp_fee": lp_fee,
        "gross_slippage_pct": max(gross_slippage_pct, 0.0),
        "net_slippage_pct": net_slippage_pct,
    }


def batch_v4_slippage_at_blocks(
    stateview: Contract,
    quoter: Contract,
    pool_id: bytes,
    blocks: list[int],
    trade_amounts_wei: list[int],
    currency0: str,
    currency1: str,
    fee: int,
    tick_spacing: int,
    hooks: str,
    zero_for_one: bool = True,
) -> list[dict]:
    """
    Compute V4 slippage across multiple blocks and trade sizes.

    Returns list of dicts, one per block, each containing slippage for each trade size.
    Note: requires 1 getSlot0 + N Quoter calls per block (N = number of trade sizes).
    """
    results = []
    for block in blocks:
        try:
            sqrt_price_x96, tick, protocol_fee, lp_fee = stateview.functions.getSlot0(
                pool_id
            ).call(block_identifier=block)

            if sqrt_price_x96 == 0:
                results.append({"block": block, "error": "pool not initialized"})
                continue

            current_price = float(sqrt_price_x96_to_price(sqrt_price_x96))
            fee_pct = lp_fee / 1_000_000

            pool_key = (
                Web3.to_checksum_address(currency0),
                Web3.to_checksum_address(currency1),
                fee,
                tick_spacing,
                Web3.to_checksum_address(hooks),
            )

            block_result = {
                "block": block,
                "spot_price": current_price,
                "lp_fee": lp_fee,
                "trades": {},
            }

            for amount in trade_amounts_wei:
                try:
                    params = (pool_key, zero_for_one, amount, b"")
                    amount_out, _ = quoter.functions.quoteExactInputSingle(
                        params
                    ).call(block_identifier=block)

                    if zero_for_one:
                        exec_price = amount_out / amount if amount > 0 else 0.0
                    else:
                        exec_price = amount / amount_out if amount_out > 0 else 0.0
                    gross = abs(current_price - exec_price) / current_price * 100 - fee_pct * 100
                    net = abs(current_price - exec_price) / current_price * 100

                    block_result["trades"][amount] = {
                        "amount_out": amount_out,
                        "gross_slippage_pct": max(gross, 0.0),
                        "net_slippage_pct": net,
                    }
                except Exception as e:
                    block_result["trades"][amount] = {"error": str(e)}

            results.append(block_result)
        except Exception as e:
            results.append({"block": block, "error": str(e)})

    return results
