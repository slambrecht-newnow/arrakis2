"""
Capital efficiency and net slippage comparison utilities.

Pure-computation functions (no RPC calls) for cross-system V2 vs V4 analysis.
"""

import numpy as np
import pandas as pd


def _get_trade(r: dict, amt: int) -> dict:
    """Get trade result, handling JSON string-key cache."""
    trades = r.get("trades", {})
    return trades.get(amt) or trades.get(str(amt)) or {}


def _has_trade(r: dict, amt: int) -> bool:
    """Check if a valid trade exists for this amount."""
    t = _get_trade(r, amt)
    return bool(t) and "error" not in t and "gross_slippage_pct" in t


def compute_net_slippage_summary(
    v2_results: list[dict],
    v4_results: list[dict],
    v2_amounts: list[int],
    v4_amounts: list[int],
    sizes_usd: list[int],
    v2_fee_pct: float = 0.30,
    v4_fee_pct: float = 0.70,
) -> pd.DataFrame:
    """
    Compute time-averaged gross and net slippage per trade size for V2 and V4.

    Net slippage = gross slippage + fee (total cost to trader).
    Returns a DataFrame with columns: size_usd, v2_gross_avg, v4_gross_avg,
    v2_net_avg, v4_net_avg, gross_improvement_pct, net_improvement_pct.
    """
    rows = []
    for usd, v2_amt, v4_amt in zip(sizes_usd, v2_amounts, v4_amounts):
        v2_gross = [
            _get_trade(r, v2_amt)["gross_slippage_pct"]
            for r in v2_results
            if "error" not in r and _has_trade(r, v2_amt)
        ]
        v4_gross = [
            _get_trade(r, v4_amt)["gross_slippage_pct"]
            for r in v4_results
            if "error" not in r and _has_trade(r, v4_amt)
        ]

        v2_g = float(np.mean(v2_gross)) if v2_gross else 0.0
        v4_g = float(np.mean(v4_gross)) if v4_gross else 0.0

        v2_n = v2_g + v2_fee_pct
        v4_n = v4_g + v4_fee_pct

        gross_imp = (v2_g - v4_g) / v2_g * 100 if v2_g > 0 else 0.0
        net_imp = (v2_n - v4_n) / v2_n * 100 if v2_n > 0 else 0.0

        rows.append({
            "size_usd": usd,
            "v2_gross_avg": v2_g,
            "v4_gross_avg": v4_g,
            "v2_net_avg": v2_n,
            "v4_net_avg": v4_n,
            "gross_improvement_pct": gross_imp,
            "net_improvement_pct": net_imp,
        })

    return pd.DataFrame(rows)


def find_breakeven_trade_size(
    v2_net_avgs: list[float],
    v4_net_avgs: list[float],
    sizes_usd: list[int],
) -> float | None:
    """
    Linearly interpolate to find where V4 net cost equals V2 net cost.

    Returns the USD trade size at the crossover, or None if V4 is always
    cheaper or always more expensive.
    """
    diffs = [v2 - v4 for v2, v4 in zip(v2_net_avgs, v4_net_avgs)]

    for i in range(len(diffs) - 1):
        if diffs[i] * diffs[i + 1] < 0:
            # Sign change: interpolate
            frac = abs(diffs[i]) / (abs(diffs[i]) + abs(diffs[i + 1]))
            breakeven = sizes_usd[i] + frac * (sizes_usd[i + 1] - sizes_usd[i])
            return float(breakeven)

    return None


def compute_capital_efficiency_ratio(
    v2_gross_avg: float,
    v4_gross_avg: float,
) -> float:
    """
    Compute how many times more capital-efficient V4 is vs V2.

    Ratio = v2_gross / v4_gross. Higher means V4 needs less capital
    for the same price impact.
    """
    if v4_gross_avg <= 0:
        return float("inf")
    return v2_gross_avg / v4_gross_avg
