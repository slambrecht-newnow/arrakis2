"""
Tests for vault performance decomposition functions.

Unit tests with synthetic data (known answers) + optional RPC integration check.
Run: cd backend && uv run python tests/test_vault_decomposition.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.vault_performance import (
    compute_annualized_return,
    compute_il_factor,
    decompose_vault_returns,
)


def test_il_factor_no_change() -> None:
    """IL factor at r=1 (no price change) should be exactly 1.0."""
    assert math.isclose(compute_il_factor(1.0), 1.0, abs_tol=1e-10)
    print("  [PASS] il_factor(1.0) == 1.0")


def test_il_factor_4x() -> None:
    """IL factor at r=4 should be 2*sqrt(4)/(1+4) = 4/5 = 0.8."""
    assert math.isclose(compute_il_factor(4.0), 0.8, abs_tol=1e-10)
    print("  [PASS] il_factor(4.0) == 0.8")


def test_il_factor_quarter() -> None:
    """IL factor at r=0.25 should also be 0.8 (symmetric)."""
    # 2*sqrt(0.25)/(1+0.25) = 2*0.5/1.25 = 0.8
    assert math.isclose(compute_il_factor(0.25), 0.8, abs_tol=1e-10)
    print("  [PASS] il_factor(0.25) == 0.8")


def test_il_factor_always_lte_one() -> None:
    """IL factor should be <= 1 for any positive price ratio."""
    for r in [0.01, 0.1, 0.5, 1.0, 2.0, 10.0, 100.0]:
        f = compute_il_factor(r)
        assert f <= 1.0 + 1e-10, f"il_factor({r}) = {f} > 1.0"
    print("  [PASS] il_factor always <= 1.0")


def test_il_factor_zero() -> None:
    """IL factor at r=0 should return 0."""
    assert compute_il_factor(0.0) == 0.0
    assert compute_il_factor(-1.0) == 0.0
    print("  [PASS] il_factor(0) == 0")


def test_annualized_return() -> None:
    """Verify annualized return computation."""
    # 10% in 365 days → 10% annualized
    ann = compute_annualized_return(100.0, 110.0, 365.0)
    assert math.isclose(ann, 10.0, abs_tol=1e-6), f"Expected 10.0, got {ann}"

    # 10% in 182.5 days → ~21.0% annualized
    ann2 = compute_annualized_return(100.0, 110.0, 182.5)
    expected = ((1.1 ** (365.0 / 182.5)) - 1) * 100
    assert math.isclose(ann2, expected, abs_tol=0.01), f"Expected {expected:.2f}, got {ann2:.2f}"
    print("  [PASS] annualized_return")


def test_annualized_edge_cases() -> None:
    """Edge cases: zero initial, zero days."""
    assert compute_annualized_return(0, 100, 30) == 0.0
    assert compute_annualized_return(100, 110, 0) == 0.0
    print("  [PASS] annualized_edge_cases")


def test_decompose_vault_returns() -> None:
    """Verify decomposition identity: vault = hodl + il + premium."""
    vault_usd = [1000.0, 1050.0, 980.0, 1100.0]
    hodl_usd = [1000.0, 1080.0, 1020.0, 1150.0]
    fullrange_usd = [1000.0, 1060.0, 990.0, 1120.0]

    decomp = decompose_vault_returns(vault_usd, hodl_usd, fullrange_usd)
    assert len(decomp) == 4

    for i in range(4):
        d = decomp[i]

        # price_return = hodl[i] - hodl[0]
        assert math.isclose(d["price_return"], hodl_usd[i] - hodl_usd[0], abs_tol=1e-6)

        # il_fullrange = fullrange[i] - hodl[i]
        assert math.isclose(d["il_fullrange"], fullrange_usd[i] - hodl_usd[i], abs_tol=1e-6)

        # management_premium = vault[i] - fullrange[i]
        assert math.isclose(d["management_premium"], vault_usd[i] - fullrange_usd[i], abs_tol=1e-6)

        # Identity: total_lp_effect = vault - hodl = il + premium
        assert math.isclose(
            d["total_lp_effect"],
            vault_usd[i] - hodl_usd[i],
            abs_tol=1e-6,
        ), f"Identity broken at i={i}"

    print("  [PASS] decompose_vault_returns")


def test_decompose_sums_to_vault() -> None:
    """Verify hodl[0] + price_return + il + premium = vault at each step."""
    vault = [500.0, 520.0, 480.0]
    hodl = [500.0, 540.0, 490.0]
    fr = [500.0, 530.0, 485.0]

    decomp = decompose_vault_returns(vault, hodl, fr)
    initial = hodl[0]

    for i in range(3):
        d = decomp[i]
        reconstructed = initial + d["price_return"] + d["il_fullrange"] + d["management_premium"]
        assert math.isclose(reconstructed, vault[i], abs_tol=1e-6), (
            f"Reconstruction failed at i={i}: {reconstructed} != {vault[i]}"
        )

    print("  [PASS] decompose_sums_to_vault")


if __name__ == "__main__":
    print("=== test_vault_decomposition.py ===")
    test_il_factor_no_change()
    test_il_factor_4x()
    test_il_factor_quarter()
    test_il_factor_always_lte_one()
    test_il_factor_zero()
    test_annualized_return()
    test_annualized_edge_cases()
    test_decompose_vault_returns()
    test_decompose_sums_to_vault()
    print("\nAll vault decomposition tests passed.")
