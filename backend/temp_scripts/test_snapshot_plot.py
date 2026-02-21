"""
Arrakis vault range snapshot: 3x3 grid, 9 equally spaced dates.
Uses hardcoded data from test_rebalancing.py — no RPC calls.
Run from backend/: uv run python temp_scripts/test_snapshot_plot.py
"""
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

PLOT_DIR = "notebooks/plots"
os.makedirs(PLOT_DIR, exist_ok=True)


def tick_to_sqrt_price(tick: int) -> float:
    return 1.0001 ** (tick / 2)


# All 16 rebalance snapshots from test_rebalancing.py output.
# We'll pick 9 equally spaced from these + start/end.
all_snapshots = [
    {"date": "2025-12-11", "price": 18232.0, "ranges": [(82900, 113150), (87150, 98000)]},
    {"date": "2025-12-13", "price": 19500.0, "ranges": [(83050, 115450), (88400, 99200)]},
    {"date": "2025-12-15", "price": 20200.0, "ranges": [(83700, 116900), (89500, 100300)]},
    {"date": "2025-12-20", "price": 21000.0, "ranges": [(84750, 114200), (88550, 99450)]},
    {"date": "2026-01-01", "price": 23500.0, "ranges": [(84800, 116000), (89550, 100400)]},
    {"date": "2026-01-05", "price": 24500.0, "ranges": [(85000, 117700), (90550, 101350)]},
    {"date": "2026-01-15", "price": 26500.0, "ranges": [(85400, 119600), (91700, 102450)]},
    {"date": "2026-01-19", "price": 27500.0, "ranges": [(85850, 121100), (92700, 103450)]},
    {"date": "2026-01-26", "price": 29000.0, "ranges": [(86350, 122600), (93750, 104450)]},
    {"date": "2026-01-27", "price": 29500.0, "ranges": [(86950, 124000), (94750, 105450)]},
    {"date": "2026-02-05", "price": 31000.0, "ranges": [(88950, 122300), (94800, 105600)]},
    {"date": "2026-02-06", "price": 32000.0, "ranges": [(90250, 119300), (93850, 104750)]},
    {"date": "2026-02-08", "price": 32500.0, "ranges": [(93850, 104750), (90250, 119250)]},
    {"date": "2026-02-09", "price": 33000.0, "ranges": [(90300, 121250), (94900, 105750)]},
    {"date": "2026-02-12", "price": 33500.0, "ranges": [(91600, 118000), (93850, 104750)]},
    {"date": "2026-02-19", "price": 34000.0, "ranges": [(92150, 115700), (92950, 103900)]},
    {"date": "2026-02-21", "price": 34482.8, "ranges": [(92150, 115700), (92950, 103900)]},
]

# Pick 9 equally spaced
n = len(all_snapshots)
indices = np.linspace(0, n - 1, 9, dtype=int)
snapshots = [all_snapshots[i] for i in indices]


# Repo color palette
COLOR_VAULT = '#2ca02c'      # Green — vault/Arrakis throughout
COLOR_VAULT_LIGHT = '#a8ddb5' # Light green fill for ranges
COLOR_BASELINE = '#d9d9d9'    # Light gray for full-range
COLOR_BASELINE_EDGE = '#999999'
COLOR_PRICE = '#e15759'        # Red — consistent with repo price/marker lines


def draw_snapshot(ax: plt.Axes, snap: dict, x_min: float, x_max: float) -> None:
    """Draw one vault range snapshot panel with shared x-axis range."""
    current_eth_per_ixs = 1.0 / snap["price"] if snap["price"] > 0 else 0

    # Convert tick ranges to ETH-per-IXS
    range_bars = []
    for tl, tu in snap["ranges"]:
        p_lo = tick_to_sqrt_price(tl) ** 2
        p_hi = tick_to_sqrt_price(tu) ** 2
        eth_lo = 1.0 / p_hi
        eth_hi = 1.0 / p_lo
        range_bars.append((eth_lo, eth_hi, tu - tl))

    # Full-range bar: wide, flat, gray
    fr_h = 0.5
    ax.bar((x_min + x_max) / 2, fr_h, width=(x_max - x_min) * 0.95,
           bottom=0, color=COLOR_BASELINE, alpha=0.6, edgecolor=COLOR_BASELINE_EDGE,
           linewidth=0.8, zorder=1)

    # Vault ranges: wider = shorter, narrower = taller
    range_bars.sort(key=lambda r: -(r[1] - r[0]))
    n_ranges = len(range_bars)
    for i, (eth_lo, eth_hi, tw) in enumerate(range_bars):
        height = 1.5 + 3.0 * (i + 1) / n_ranges
        ax.bar((eth_lo + eth_hi) / 2, height, width=eth_hi - eth_lo,
               bottom=fr_h, color=COLOR_VAULT_LIGHT, alpha=0.8,
               edgecolor=COLOR_VAULT, linewidth=1.5, zorder=2 + i)

    # Current price line
    ax.axvline(current_eth_per_ixs, color=COLOR_PRICE, linestyle='--',
               linewidth=1.8, zorder=10)

    # Token labels on each side of price
    y_label = 5.5
    left_space = current_eth_per_ixs - x_min
    right_space = x_max - current_eth_per_ixs
    ax.text(current_eth_per_ixs - left_space * 0.5, y_label, 'ETH',
            fontsize=12, fontweight='bold', color='#4e79a7', ha='center', va='center')
    ax.text(current_eth_per_ixs + right_space * 0.5, y_label, 'IXS',
            fontsize=12, fontweight='bold', color=COLOR_VAULT, ha='center', va='center')

    # Formatting
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(0, 6.2)
    ax.set_title(snap["date"], fontsize=11, fontweight='bold')
    ax.set_yticks([])
    # Show x-tick values with scientific formatting
    ax.ticklabel_format(axis='x', style='scientific', scilimits=(-5, -5))
    ax.tick_params(axis='x', labelsize=8, rotation=30)
    for sp in ['top', 'right', 'left']:
        ax.spines[sp].set_visible(False)


# ── Compute global x-axis range across all 9 snapshots ──
global_prices = []
for snap in snapshots:
    global_prices.append(1.0 / snap["price"])
    for tl, tu in snap["ranges"]:
        p_lo = tick_to_sqrt_price(tl) ** 2
        p_hi = tick_to_sqrt_price(tu) ** 2
        global_prices.extend([1.0 / p_hi, 1.0 / p_lo])

global_x_min = min(global_prices) * 0.5
global_x_max = max(global_prices) * 1.15

# ── 3x3 Grid ──
fig, axes = plt.subplots(3, 3, figsize=(15, 13))

for ax, snap in zip(axes.flat, snapshots):
    draw_snapshot(ax, snap, global_x_min, global_x_max)

# Shared x-label
for ax in axes[2]:
    ax.set_xlabel('Price (ETH per IXS)', fontsize=10)

# Single legend
legend_elements = [
    Patch(facecolor=COLOR_BASELINE, alpha=0.6, edgecolor=COLOR_BASELINE_EDGE, label='Full Range'),
    Patch(facecolor=COLOR_VAULT_LIGHT, alpha=0.8, edgecolor=COLOR_VAULT, linewidth=1.5, label='Vault Ranges'),
    Line2D([0], [0], color=COLOR_PRICE, linestyle='--', linewidth=1.8, label='Current Price'),
]
fig.legend(handles=legend_elements, loc='lower center', ncol=3, fontsize=11,
           framealpha=0.9, bbox_to_anchor=(0.5, -0.005))

fig.suptitle('Vault Range Evolution Over Time', fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0, 0.03, 1, 0.96])
out = f'{PLOT_DIR}/test_snapshot_comparison.png'
plt.savefig(out, dpi=150, bbox_inches='tight')
print(f"Saved {out}")
plt.close()
