"""
Tests for capital_efficiency module.

Unit tests with synthetic data (known answers) + optional RPC integration check.
Run: cd backend && uv run python tests/test_capital_efficiency.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.capital_efficiency import (
    compute_capital_efficiency_ratio,
    compute_net_slippage_summary,
    find_breakeven_trade_size,
)


def test_net_slippage_summary() -> None:
    """Verify summary with hand-crafted V2/V4 results."""
    # Synthetic: 2 blocks, 2 trade sizes
    v2_results = [
        {
            "block": 100,
            "spot_price": 1.0,
            "trades": {
                1000: {"gross_slippage_pct": 0.10, "net_slippage_pct": 0.40},
                5000: {"gross_slippage_pct": 0.50, "net_slippage_pct": 0.80},
            },
        },
        {
            "block": 200,
            "spot_price": 1.0,
            "trades": {
                1000: {"gross_slippage_pct": 0.20, "net_slippage_pct": 0.50},
                5000: {"gross_slippage_pct": 0.60, "net_slippage_pct": 0.90},
            },
        },
    ]
    v4_results = [
        {
            "block": 300,
            "spot_price": 1.0,
            "trades": {
                1000: {"gross_slippage_pct": 0.02, "net_slippage_pct": 0.72},
                5000: {"gross_slippage_pct": 0.10, "net_slippage_pct": 0.80},
            },
        },
        {
            "block": 400,
            "spot_price": 1.0,
            "trades": {
                1000: {"gross_slippage_pct": 0.04, "net_slippage_pct": 0.74},
                5000: {"gross_slippage_pct": 0.12, "net_slippage_pct": 0.82},
            },
        },
    ]

    df = compute_net_slippage_summary(
        v2_results,
        v4_results,
        v2_amounts=[1000, 5000],
        v4_amounts=[1000, 5000],
        sizes_usd=[1000, 5000],
        v2_fee_pct=0.30,
        v4_fee_pct=0.70,
    )

    assert len(df) == 2, f"Expected 2 rows, got {len(df)}"

    # $1K: V2 gross avg = (0.10+0.20)/2 = 0.15, V4 gross avg = (0.02+0.04)/2 = 0.03
    assert math.isclose(df.iloc[0]["v2_gross_avg"], 0.15, abs_tol=1e-6)
    assert math.isclose(df.iloc[0]["v4_gross_avg"], 0.03, abs_tol=1e-6)

    # Net: V2 = 0.15+0.30 = 0.45, V4 = 0.03+0.70 = 0.73
    assert math.isclose(df.iloc[0]["v2_net_avg"], 0.45, abs_tol=1e-6)
    assert math.isclose(df.iloc[0]["v4_net_avg"], 0.73, abs_tol=1e-6)

    # $5K: V2 gross avg = 0.55, V4 gross avg = 0.11
    assert math.isclose(df.iloc[1]["v2_gross_avg"], 0.55, abs_tol=1e-6)
    assert math.isclose(df.iloc[1]["v4_gross_avg"], 0.11, abs_tol=1e-6)

    # Net: V2 = 0.85, V4 = 0.81
    assert math.isclose(df.iloc[1]["v2_net_avg"], 0.85, abs_tol=1e-6)
    assert math.isclose(df.iloc[1]["v4_net_avg"], 0.81, abs_tol=1e-6)

    print("  [PASS] net_slippage_summary")


def test_breakeven_trade_size() -> None:
    """Verify linear interpolation finds correct crossover."""
    # V2 net: [0.45, 0.85], V4 net: [0.73, 0.81]
    # At $1K: V2=0.45 < V4=0.73 (V2 cheaper), diff = -0.28
    # At $5K: V2=0.85 > V4=0.81 (V4 cheaper), diff = +0.04
    # Crossover: linear interpolation between 1000 and 5000
    v2_nets = [0.45, 0.85]
    v4_nets = [0.73, 0.81]

    be = find_breakeven_trade_size(v2_nets, v4_nets, [1000, 5000])
    assert be is not None, "Expected a breakeven point"

    # diff = [-0.28, 0.04], frac = 0.28/(0.28+0.04) = 0.875
    # breakeven = 1000 + 0.875 * 4000 = 4500
    assert math.isclose(be, 4500.0, abs_tol=1.0), f"Expected ~4500, got {be}"
    print("  [PASS] breakeven_trade_size")


def test_breakeven_no_crossover() -> None:
    """When V4 is always cheaper, returns None."""
    be = find_breakeven_trade_size([1.0, 2.0], [0.5, 1.0], [1000, 5000])
    assert be is None, f"Expected None, got {be}"
    print("  [PASS] breakeven_no_crossover")


def test_capital_efficiency_ratio() -> None:
    """Verify ratio computation."""
    ratio = compute_capital_efficiency_ratio(1.0, 0.1)
    assert math.isclose(ratio, 10.0, abs_tol=1e-6), f"Expected 10.0, got {ratio}"

    ratio_zero = compute_capital_efficiency_ratio(0.5, 0.0)
    assert ratio_zero == float("inf"), f"Expected inf, got {ratio_zero}"
    print("  [PASS] capital_efficiency_ratio")


def test_summary_with_errors() -> None:
    """Verify that error results are skipped gracefully."""
    v2 = [
        {"block": 1, "error": "timeout"},
        {"block": 2, "spot_price": 1.0, "trades": {100: {"gross_slippage_pct": 0.5, "net_slippage_pct": 0.8}}},
    ]
    v4 = [
        {"block": 3, "spot_price": 1.0, "trades": {100: {"gross_slippage_pct": 0.1, "net_slippage_pct": 0.8}}},
        {"block": 4, "spot_price": 1.0, "trades": {100: {"error": "revert"}}},
    ]
    df = compute_net_slippage_summary(v2, v4, [100], [100], [1000])
    assert len(df) == 1
    assert math.isclose(df.iloc[0]["v2_gross_avg"], 0.5, abs_tol=1e-6)
    assert math.isclose(df.iloc[0]["v4_gross_avg"], 0.1, abs_tol=1e-6)
    print("  [PASS] summary_with_errors")


if __name__ == "__main__":
    print("=== test_capital_efficiency.py ===")
    test_net_slippage_summary()
    test_breakeven_trade_size()
    test_breakeven_no_crossover()
    test_capital_efficiency_ratio()
    test_summary_with_errors()
    print("\nAll capital efficiency tests passed.")
