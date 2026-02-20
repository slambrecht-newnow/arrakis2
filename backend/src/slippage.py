from decimal import Decimal

from .amm_math import sqrt_price_x96_to_price


def calculate_slippage(
    w3,
    amount_in_wei: int,
    stateview_address: str, stateview_abi: list,
    quoter_address: str, quoter_abi: list,
    pool_id: bytes,
    currency0: str, currency1: str,
    fee: int,
    tick_spacing: int,
    hooks: str,
    zero_for_one: bool = True
) -> dict:
    """
    Calculate slippage for a given trade size.

    :param w3: Web3 instance
    :param amount_in_wei: Trade amount in wei (ETH)
    :param zero_for_one: True if swapping token0 for token1 (ETH -> MORPHO)
    :return: Dict with current_price, execution_price, slippage_pct
    """
    # Create contract instances
    stateview = w3.eth.contract(address=stateview_address, abi=stateview_abi)
    quoter = w3.eth.contract(address=quoter_address, abi=quoter_abi)

    # Spot price for trade (token1/token0)
    raw_spot, tick, protocol_fee, lp_fee = stateview.functions.getSlot0(pool_id).call()
    current_price = sqrt_price_x96_to_price(raw_spot)  # Already returns Decimal

    # Quote for the trade - aka what comes out (MORPHO)
    pool_key = (currency0, currency1, fee, tick_spacing, hooks)
    params = (pool_key, zero_for_one, amount_in_wei, b"")

    amount_out_wei, gas_estimate_wei = quoter.functions.quoteExactInputSingle(params).call()

    # token1/token0 in wei - assuming they are the same unit of 10e18
    execution_price = Decimal(amount_out_wei) / Decimal(amount_in_wei)
    # Calculate slippage
    slippage_percentage = abs(current_price - execution_price) / current_price * 100

    return {
        "amount_in_wei": amount_in_wei,
        "amount_out_wei": amount_out_wei,
        "current_spot_price": float(current_price),
        "execution_spot_price": float(execution_price),
        "slippage_percentage": float(slippage_percentage)
    }