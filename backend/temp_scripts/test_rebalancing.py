"""
Temporary test script: validate vault_rebalancing module and produce plots.
Run from backend/ dir: uv run python temp_scripts/test_rebalancing.py
"""

import os
import sys
sys.path.append(".")

from dotenv import load_dotenv
from web3 import Web3
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from src.config import (
    STATE_VIEW, IXS_POOL_ID_BYTES, ARRAKIS_VAULT, ARRAKIS_MODULE,
    CHAINLINK_ETH_USD,
)
from src.abis import STATEVIEW_ABI_EXTENDED, ARRAKIS_VAULT_ABI, ARRAKIS_MODULE_ABI, CHAINLINK_ABI
from src.block_utils import generate_daily_block_samples, blocks_to_timestamps, timestamps_to_dates, get_latest_block
from src.vault_performance import batch_vault_underlying
from src.vault_rebalancing import (
    batch_pool_state_and_ranges, detect_rebalances,
    compute_capital_efficiency,
    get_pool_state_at_block, get_vault_ranges_at_block,
)
from src.amm_math import tick_to_sqrt_price
from src.migration_detection import find_v4_pool_creation_block

load_dotenv()

# All plots go to the single canonical location: notebooks/plots/
PLOT_DIR = "notebooks/plots"
os.makedirs(PLOT_DIR, exist_ok=True)

w3 = Web3(Web3.HTTPProvider(os.getenv("rpc_url_mainnet")))
print(f"Connected: {w3.is_connected()}")

stateview = w3.eth.contract(address=Web3.to_checksum_address(STATE_VIEW), abi=STATEVIEW_ABI_EXTENDED)
vault = w3.eth.contract(address=Web3.to_checksum_address(ARRAKIS_VAULT), abi=ARRAKIS_VAULT_ABI)
module = w3.eth.contract(address=Web3.to_checksum_address(ARRAKIS_MODULE), abi=ARRAKIS_MODULE_ABI)
chainlink = w3.eth.contract(address=Web3.to_checksum_address(CHAINLINK_ETH_USD), abi=CHAINLINK_ABI)

# ── Step 1: Quick single-block test ──
latest_block = get_latest_block(w3)
print(f"\n=== Single-block test at latest block {latest_block:,} ===")

state = get_pool_state_at_block(stateview, IXS_POOL_ID_BYTES, latest_block)
print(f"  tick={state['tick']}, liq={state['liquidity']:,}, price(IXS/ETH)={state['price']:.4f}")
print(f"  ETH per IXS = {1.0/state['price']:.8f}" if state["price"] > 0 else "  price=0")

ranges = get_vault_ranges_at_block(module, latest_block)
print(f"  Active ranges: {ranges}")
for tl, tu in ranges:
    p_lo = tick_to_sqrt_price(tl) ** 2
    p_hi = tick_to_sqrt_price(tu) ** 2
    print(f"    [{tl}, {tu}] -> IXS/ETH [{p_lo:.4f}, {p_hi:.4f}] -> ETH/IXS [{1/p_hi:.8f}, {1/p_lo:.8f}]")

# ── Step 2: Sample blocks (daily) ──
print("\n=== Sampling blocks ===")
search_start = latest_block - 7200 * 365
v4_start = find_v4_pool_creation_block(stateview, IXS_POOL_ID_BYTES, search_start, latest_block)
sample_blocks = generate_daily_block_samples(v4_start, latest_block)
print(f"V4 start: {v4_start:,}, samples: {len(sample_blocks)}")

sample_ts = blocks_to_timestamps(w3, sample_blocks)
sample_dates = timestamps_to_dates(sample_ts)
import pandas as pd
dates = pd.to_datetime(sample_dates)
print(f"Date range: {sample_dates[0]} to {sample_dates[-1]}")

# ── Step 3: Fetch vault amounts ──
print("\n=== Fetching vault amounts ===")
vault_data = batch_vault_underlying(vault, sample_blocks)
ixs_amounts = [d[1] / 1e18 for d in vault_data]
eth_amounts = [d[2] / 1e18 for d in vault_data]
print(f"IXS: {ixs_amounts[0]:,.0f} -> {ixs_amounts[-1]:,.0f}")
print(f"ETH: {eth_amounts[0]:.2f} -> {eth_amounts[-1]:.2f}")

# ── Step 4: Fetch pool state + ranges ──
print("\n=== Fetching pool state + vault ranges ===")
range_data = batch_pool_state_and_ranges(stateview, module, IXS_POOL_ID_BYTES, sample_blocks)
print(f"Fetched {len(range_data)} samples")

# ── Step 5: Detect rebalances ──
rebalance_idx = detect_rebalances(range_data)
print(f"\nDetected {len(rebalance_idx)} rebalance events:")
for idx in rebalance_idx:
    prev = range_data[idx - 1]["ranges"]
    curr = range_data[idx]["ranges"]
    print(f"  [{sample_dates[idx]}] block {range_data[idx]['block']:,}: {prev} -> {curr}")

# ── Step 6: Plot — Price + Range Bands ──
print("\n=== Generating plots ===")

pool_prices_eth_per_ixs = []
for rd in range_data:
    if rd["price"] > 0:
        pool_prices_eth_per_ixs.append(1.0 / rd["price"])
    else:
        pool_prices_eth_per_ixs.append(0.0)

fig, ax = plt.subplots(figsize=(14, 7))
ax.plot(dates, pool_prices_eth_per_ixs, color='#2ca02c', linewidth=1.8, label='IXS/ETH Price', zorder=3)

for i in range(len(range_data)):
    rd = range_data[i]
    if not rd["ranges"]:
        continue
    for tick_lower, tick_upper in rd["ranges"]:
        price_lower_ixs_eth = tick_to_sqrt_price(tick_lower) ** 2
        price_upper_ixs_eth = tick_to_sqrt_price(tick_upper) ** 2
        band_low = 1.0 / price_upper_ixs_eth if price_upper_ixs_eth > 0 else 0
        band_high = 1.0 / price_lower_ixs_eth if price_lower_ixs_eth > 0 else 0
        ax.axhspan(band_low, band_high, xmin=i / len(dates), xmax=(i + 1) / len(dates),
                   alpha=0.15, color='#2ca02c', zorder=1)

for idx in rebalance_idx:
    ax.axvline(dates[idx], color='red', linestyle='--', alpha=0.6, linewidth=1, zorder=2)
if rebalance_idx:
    ax.axvline(dates[rebalance_idx[0]], color='red', linestyle='--', alpha=0.6,
               linewidth=1, label='Rebalance Event')

ax.set_xlabel('Date')
ax.set_ylabel('ETH per IXS')
ax.set_title('Price Tracking: Vault Range Bands Follow the Price', fontsize=14, fontweight='bold')
ax.legend(loc='best')
ax.grid(True, alpha=0.3)
ax.tick_params(axis='x', rotation=45)
plt.tight_layout()
plt.savefig(f'{PLOT_DIR}/test_price_ranges.png', dpi=150, bbox_inches='tight')
print(f"  Saved {PLOT_DIR}/test_price_ranges.png")
plt.close()

# ── Step 7: Plot — Active Liquidity ──
liq_values = [rd["liquidity"] for rd in range_data]

fig, ax = plt.subplots(figsize=(14, 6))
ax.plot(dates, liq_values, color='#4e79a7', linewidth=1.8, label='Active In-Range Liquidity')
for idx in rebalance_idx:
    ax.axvline(dates[idx], color='red', linestyle='--', alpha=0.5, linewidth=1)
if rebalance_idx:
    ax.axvline(dates[rebalance_idx[0]], color='red', linestyle='--', alpha=0.5,
               linewidth=1, label='Rebalance Event')
ax.set_xlabel('Date')
ax.set_ylabel('Liquidity (L)')
ax.set_title('Active In-Range Liquidity Over Time', fontsize=14, fontweight='bold')
ax.legend(loc='best')
ax.grid(True, alpha=0.3)
ax.tick_params(axis='x', rotation=45)
plt.tight_layout()
plt.savefig(f'{PLOT_DIR}/test_active_liquidity.png', dpi=150, bbox_inches='tight')
print(f"  Saved {PLOT_DIR}/test_active_liquidity.png")
plt.close()

# ── Step 8: Plot — Capital Efficiency ──
# Use raw vault amounts (wei) since Uniswap L is in raw units: L = sqrt(x_raw * y_raw)
raw_ixs = [d[1] for d in vault_data]
raw_eth = [d[2] for d in vault_data]
ce_ratios = []
for i, rd in enumerate(range_data):
    ce = compute_capital_efficiency(rd["liquidity"], raw_ixs[i], raw_eth[i])
    ce_ratios.append(ce)

fig, ax = plt.subplots(figsize=(14, 6))
ax.plot(dates, ce_ratios, color='#59a14f', linewidth=1.8, label='Capital Efficiency Ratio')
ax.axhline(y=1.0, color='gray', linestyle=':', linewidth=1.5, label='Full-Range Baseline (1.0x)')
for idx in rebalance_idx:
    ax.axvline(dates[idx], color='red', linestyle='--', alpha=0.5, linewidth=1)
if rebalance_idx:
    ax.axvline(dates[rebalance_idx[0]], color='red', linestyle='--', alpha=0.5,
               linewidth=1, label='Rebalance Event')
ax.set_xlabel('Date')
ax.set_ylabel('CE Ratio (Concentrated / Full-Range)')
ax.set_title('Capital Efficiency: Concentration Multiplier Over Time', fontsize=14, fontweight='bold')
ax.legend(loc='best')
ax.grid(True, alpha=0.3)
ax.tick_params(axis='x', rotation=45)
plt.tight_layout()
plt.savefig(f'{PLOT_DIR}/test_capital_efficiency.png', dpi=150, bbox_inches='tight')
print(f"  Saved {PLOT_DIR}/test_capital_efficiency.png")
plt.close()

nz_ce = [c for c in ce_ratios if c > 0]
if nz_ce:
    print(f"\n  CE range: {min(nz_ce):.1f}x - {max(nz_ce):.1f}x (median: {sorted(nz_ce)[len(nz_ce)//2]:.1f}x)")

# ── Step 9: Arrakis-Style Snapshot Comparison ──
# Mimics the Arrakis bootstrapping diagram: x=price, y=liquidity height,
# narrower ranges = taller bars, with a low flat full-range bar at the bottom.

# Pick first sample WITH ranges, and latest sample
snap_idx_a = next(i for i, rd in enumerate(range_data) if rd["ranges"])
snap_a = range_data[snap_idx_a]
snap_b = range_data[-1]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

for ax, snap, label, date_label in [
    (ax1, snap_a, 'Early', sample_dates[snap_idx_a]),
    (ax2, snap_b, 'Current', sample_dates[-1]),
]:
    current_price_ixs_eth = snap["price"]  # IXS per ETH
    current_eth_per_ixs = 1.0 / current_price_ixs_eth if current_price_ixs_eth > 0 else 0

    # Determine x-axis range: center on current price, extend to cover all ranges
    all_eth_prices = [current_eth_per_ixs]
    for tl, tu in snap["ranges"]:
        p_lo = tick_to_sqrt_price(tl) ** 2  # IXS/ETH
        p_hi = tick_to_sqrt_price(tu) ** 2
        all_eth_prices.append(1.0 / p_hi if p_hi > 0 else 0)
        all_eth_prices.append(1.0 / p_lo if p_lo > 0 else 0)

    x_min = min(all_eth_prices) * 0.7
    x_max = max(all_eth_prices) * 1.3

    # Full-range bar: spans entire x-axis, short height
    ax.bar(
        x=(x_min + x_max) / 2, height=0.8, width=(x_max - x_min),
        bottom=0, color='#6baed6', alpha=0.4, edgecolor='#3182bd',
        linewidth=1.5, label='Full Range', zorder=1
    )

    # Vault ranges: narrower = taller, sorted by width (widest first for z-order)
    range_bars = []
    for tl, tu in snap["ranges"]:
        p_lo_ixs = tick_to_sqrt_price(tl) ** 2
        p_hi_ixs = tick_to_sqrt_price(tu) ** 2
        eth_lo = 1.0 / p_hi_ixs if p_hi_ixs > 0 else 0
        eth_hi = 1.0 / p_lo_ixs if p_lo_ixs > 0 else 0
        tick_width = tu - tl
        range_bars.append((eth_lo, eth_hi, tick_width))

    # Sort widest first so narrow bars render on top
    range_bars.sort(key=lambda r: -(r[1] - r[0]))

    # Assign heights: narrower range gets taller bar
    # Scale relative to tick width — inverse relationship
    max_tick_w = max(r[2] for r in range_bars) if range_bars else 1
    for eth_lo, eth_hi, tick_w in range_bars:
        # Height inversely proportional to tick width
        # Wider range: base height ~2, narrower: up to ~5
        height = 1.0 + 4.0 * (1.0 - tick_w / max_tick_w) if len(range_bars) > 1 else 3.0
        center = (eth_lo + eth_hi) / 2
        width = eth_hi - eth_lo

        ax.bar(
            x=center, height=height, width=width,
            bottom=0.8,  # stack above full-range
            color='#f4a460', alpha=0.75, edgecolor='#d2691e',
            linewidth=1.5, zorder=2
        )

    # Add a single legend entry for vault ranges
    ax.bar(0, 0, color='#f4a460', alpha=0.75, edgecolor='#d2691e',
           linewidth=1.5, label='Vault Ranges')

    # Current price line
    ax.axvline(current_eth_per_ixs, color='#333333', linestyle=':', linewidth=2,
               label=f'Current Price', zorder=5)

    # Token labels on each side of the price line
    y_top = ax.get_ylim()[1] if ax.get_ylim()[1] > 3 else 6
    ax.text(current_eth_per_ixs * 0.65, y_top * 0.85, 'ETH',
            fontsize=16, fontweight='bold', color='#3182bd',
            ha='center', va='center')
    ax.text(current_eth_per_ixs * 1.4, y_top * 0.85, 'IXS',
            fontsize=16, fontweight='bold', color='#d2691e',
            ha='center', va='center')

    # Formatting
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(0, 7)
    ax.set_xlabel('Price (ETH per IXS)', fontsize=11)
    ax.set_ylabel('Liquidity Depth', fontsize=11)
    ax.set_title(f'{label} ({date_label})', fontsize=13, fontweight='bold')
    ax.legend(loc='upper right', fontsize=9, framealpha=0.9)
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

    # Add arrow on x-axis
    ax.annotate('', xy=(x_max, 0), xytext=(x_min, 0),
                arrowprops=dict(arrowstyle='->', color='gray', lw=1.5))

fig.suptitle('Liquidity Concentration: Arrakis Vault Snapshot',
             fontsize=15, fontweight='bold')
plt.tight_layout()
plt.savefig(f'{PLOT_DIR}/test_snapshot_comparison.png', dpi=150, bbox_inches='tight')
print(f"  Saved {PLOT_DIR}/test_snapshot_comparison.png")
plt.close()

print("\n=== All tests passed, all plots generated! ===")
