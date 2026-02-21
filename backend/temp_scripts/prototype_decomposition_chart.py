"""
Prototype: Fee vs Depth decomposition chart.

Standalone script to test the visualization before adding to the notebook.
Uses realistic mock data based on typical IXS/ETH V2 vs V4 results.

Run: cd backend && uv run python prototype_decomposition_chart.py
"""

import matplotlib.pyplot as plt
import numpy as np

# --- Challenge 2 consistent palette ---
COLOR_NEGATIVE = "#e15759"  # red — cost / penalty (matches waterfall negative)
COLOR_POSITIVE = "#59a14f"  # green — saving (matches waterfall positive)
COLOR_NET_WORSE = "#f28e2b"  # orange — V4 more expensive (Challenge 2 secondary)
COLOR_NET_BETTER = "#4e79a7"  # steelblue — V4 cheaper (Challenge 2 primary)

# --- Mock data (realistic values from IXS/ETH analysis) ---
TRADE_SIZES_USD = [1_000, 5_000, 10_000, 50_000]
V2_FEE = 0.30  # %
V4_FEE = 0.70  # %
FEE_PENALTY = V4_FEE - V2_FEE  # +0.40pp always

# Realistic gross slippage (price impact only) — V4 concentrated liquidity wins
# V2 gross slippage grows faster because full-range = less depth at spot
v2_gross = {"buy": [0.02, 0.10, 0.20, 1.05], "sell": [0.02, 0.12, 0.24, 1.20]}
v4_gross = {"buy": [0.005, 0.025, 0.05, 0.28], "sell": [0.006, 0.03, 0.06, 0.35]}


def plot_decomposition(
    sizes: list[int],
    v2_gross_vals: list[float],
    v4_gross_vals: list[float],
    v2_fee: float,
    v4_fee: float,
    direction: str,
) -> plt.Figure:
    """Plot waterfall decomposition: fee penalty vs depth saving vs net effect."""
    fee_penalty = v4_fee - v2_fee  # always positive (V4 costs more)
    depth_savings = [
        v2_g - v4_g for v2_g, v4_g in zip(v2_gross_vals, v4_gross_vals)
    ]  # positive = V4 saves
    net_effects = [
        fee_penalty - ds for ds in depth_savings
    ]  # positive = V4 worse, negative = V4 better

    x = np.arange(len(sizes))
    width = 0.25

    fig, ax = plt.subplots(figsize=(13, 6.5))

    # Three bars per trade size
    bars_fee = ax.bar(
        x - width,
        [fee_penalty] * len(sizes),
        width,
        label=f"Fee penalty (+{fee_penalty:.2f}pp)",
        color=COLOR_NEGATIVE,
        alpha=0.85,
    )
    bars_depth = ax.bar(
        x,
        [-ds for ds in depth_savings],
        width,
        label="Depth saving (concentrated liq.)",
        color=COLOR_POSITIVE,
        alpha=0.85,
    )
    bars_net = ax.bar(
        x + width,
        net_effects,
        width,
        color=[COLOR_NET_WORSE if n > 0 else COLOR_NET_BETTER for n in net_effects],
        alpha=0.85,
        edgecolor="black",
        linewidth=0.8,
    )
    # Manual legend patches for all bar types
    from matplotlib.patches import Patch
    patch_fee = Patch(facecolor=COLOR_NEGATIVE, alpha=0.85, label=f"Fee penalty (+{fee_penalty:.2f}pp)")
    patch_depth = Patch(facecolor=COLOR_POSITIVE, alpha=0.85, label="Depth saving (concentrated liq.)")
    patch_net_worse = Patch(facecolor=COLOR_NET_WORSE, edgecolor="black", linewidth=0.8, alpha=0.85, label="Net effect: V4 costlier")
    patch_net_better = Patch(facecolor=COLOR_NET_BETTER, edgecolor="black", linewidth=0.8, alpha=0.85, label="Net effect: V4 cheaper")

    # Dynamic label offset based on data range
    all_vals = [fee_penalty] + [-ds for ds in depth_savings] + net_effects
    y_range = max(all_vals) - min(all_vals)
    label_offset = y_range * 0.04

    # Value labels
    for bars in [bars_fee, bars_depth, bars_net]:
        for bar in bars:
            h = bar.get_height()
            sign = "+" if h > 0 else ""
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + (label_offset if h >= 0 else -label_offset),
                f"{sign}{h:.2f}pp",
                ha="center",
                va="bottom" if h >= 0 else "top",
                fontsize=8.5,
                fontweight="bold",
            )

    # Pad y-axis to prevent label clipping
    y_min = min(all_vals) - y_range * 0.25
    y_max = max(all_vals) + y_range * 0.25
    ax.set_ylim(y_min, y_max)

    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([f"${s:,}" for s in sizes])
    ax.set_xlabel("Trade Size (USD)", fontsize=12)
    ax.set_ylabel("Cost Change vs V2 (pp)", fontsize=12)
    ax.set_title(
        f"{direction}: Fee Penalty vs Depth Saving Decomposition",
        fontsize=14,
        fontweight="bold",
    )
    ax.legend(
        handles=[patch_fee, patch_depth, patch_net_worse, patch_net_better],
        loc="lower left", framealpha=0.95, fontsize=10,
    )
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    return fig


if __name__ == "__main__":
    # Generate both directions
    fig_buy = plot_decomposition(
        TRADE_SIZES_USD, v2_gross["buy"], v4_gross["buy"], V2_FEE, V4_FEE, "ETH \u2192 IXS"
    )
    fig_buy.savefig("plots/proto_decomposition_buy.png", dpi=150, bbox_inches="tight")

    fig_sell = plot_decomposition(
        TRADE_SIZES_USD,
        v2_gross["sell"],
        v4_gross["sell"],
        V2_FEE,
        V4_FEE,
        "IXS \u2192 ETH",
    )
    fig_sell.savefig("plots/proto_decomposition_sell.png", dpi=150, bbox_inches="tight")

    print("Saved to plots/proto_decomposition_buy.png and plots/proto_decomposition_sell.png")
    plt.show()
