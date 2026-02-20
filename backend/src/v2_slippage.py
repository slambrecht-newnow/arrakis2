"""
UniswapV2 slippage calculations using the constant-product formula.

Computes slippage from on-chain reserves with no Quoter needed —
just one getReserves call per block, then all trade sizes computed locally.
"""

from web3.contract import Contract


def calculate_v2_amount_out(
    amount_in: int, reserve_in: int, reserve_out: int, fee_bps: int = 30
) -> int:
    """
    Compute V2 swap output using constant-product formula with fee.

    fee_bps=30 means 0.30% fee (UniswapV2 default).
    Formula: amount_out = (amount_in * (10000 - fee_bps) * reserve_out) /
                          (reserve_in * 10000 + amount_in * (10000 - fee_bps))
    """
    amount_in_with_fee = amount_in * (10000 - fee_bps)
    numerator = amount_in_with_fee * reserve_out
    denominator = reserve_in * 10000 + amount_in_with_fee
    return numerator // denominator


def calculate_v2_slippage_at_block(
    pair: Contract,
    amount_in: int,
    block: int,
    ixs_is_token0: bool,
    buy_ixs: bool = True,
    fee_bps: int = 30,
) -> dict:
    """
    Calculate V2 slippage for a trade at a specific historical block.

    Returns dict with spot_price, execution_price, slippage_pct, amount_out.
    """
    r0, r1, _ = pair.functions.getReserves().call(block_identifier=block)

    if buy_ixs:
        # Buying IXS with ETH
        if ixs_is_token0:
            reserve_in, reserve_out = r1, r0  # ETH in, IXS out
        else:
            reserve_in, reserve_out = r0, r1  # ETH in, IXS out
    else:
        # Selling IXS for ETH
        if ixs_is_token0:
            reserve_in, reserve_out = r0, r1  # IXS in, ETH out
        else:
            reserve_in, reserve_out = r1, r0  # IXS in, ETH out

    if reserve_in == 0 or reserve_out == 0:
        return {"spot_price": 0.0, "execution_price": 0.0, "slippage_pct": 0.0, "amount_out": 0}

    # Spot price: reserve_out / reserve_in (output per unit input)
    spot_price = reserve_out / reserve_in

    # Execution (with fee applied)
    amount_out = calculate_v2_amount_out(amount_in, reserve_in, reserve_out, fee_bps)
    execution_price = amount_out / amount_in if amount_in > 0 else 0.0

    # Gross slippage (price impact only, fee excluded)
    amount_out_no_fee = calculate_v2_amount_out(amount_in, reserve_in, reserve_out, fee_bps=0)
    exec_price_no_fee = amount_out_no_fee / amount_in if amount_in > 0 else 0.0
    gross_slippage_pct = abs(spot_price - exec_price_no_fee) / spot_price * 100 if spot_price > 0 else 0.0

    # Net slippage (including fee)
    net_slippage_pct = abs(spot_price - execution_price) / spot_price * 100 if spot_price > 0 else 0.0

    return {
        "spot_price": spot_price,
        "execution_price": execution_price,
        "amount_out": amount_out,
        "gross_slippage_pct": gross_slippage_pct,
        "net_slippage_pct": net_slippage_pct,
        "reserve_in": reserve_in,
        "reserve_out": reserve_out,
    }


def batch_v2_slippage_at_blocks(
    pair: Contract,
    blocks: list[int],
    trade_amounts_wei: list[int],
    ixs_is_token0: bool,
    buy_ixs: bool = True,
    fee_bps: int = 30,
) -> list[dict]:
    """
    Compute V2 slippage across multiple blocks and trade sizes.

    Returns list of dicts, one per block, each containing slippage for each trade size.
    Efficient: only 1 RPC call per block (getReserves), all sizes computed locally.
    """
    results = []
    for block in blocks:
        try:
            r0, r1, _ = pair.functions.getReserves().call(block_identifier=block)

            if buy_ixs:
                if ixs_is_token0:
                    reserve_in, reserve_out = r1, r0
                else:
                    reserve_in, reserve_out = r0, r1
            else:
                if ixs_is_token0:
                    reserve_in, reserve_out = r0, r1
                else:
                    reserve_in, reserve_out = r1, r0

            spot_price = reserve_out / reserve_in if reserve_in > 0 else 0.0

            block_result = {"block": block, "spot_price": spot_price, "trades": {}}

            for amount in trade_amounts_wei:
                amount_out = calculate_v2_amount_out(amount, reserve_in, reserve_out, fee_bps)
                exec_price = amount_out / amount if amount > 0 else 0.0

                amount_out_no_fee = calculate_v2_amount_out(amount, reserve_in, reserve_out, fee_bps=0)
                exec_no_fee = amount_out_no_fee / amount if amount > 0 else 0.0
                gross_slip = abs(spot_price - exec_no_fee) / spot_price * 100 if spot_price > 0 else 0.0
                net_slip = abs(spot_price - exec_price) / spot_price * 100 if spot_price > 0 else 0.0

                block_result["trades"][amount] = {
                    "amount_out": amount_out,
                    "gross_slippage_pct": gross_slip,
                    "net_slippage_pct": net_slip,
                }

            results.append(block_result)
        except Exception as e:
            results.append({"block": block, "error": str(e)})

    return results
