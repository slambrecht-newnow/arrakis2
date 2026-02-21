"""Test bar plot of V2 reserves before/after migration."""
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from web3 import Web3
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import numpy as np

from src.config import UNIV2_PAIR, CHAINLINK_ETH_USD
from src.abis import UNIV2_PAIR_ABI, CHAINLINK_ABI
from src.price_feeds import get_eth_usd_at_block

load_dotenv()
w3 = Web3(Web3.HTTPProvider(os.getenv("rpc_url_mainnet")))

pair = w3.eth.contract(address=Web3.to_checksum_address(UNIV2_PAIR), abi=UNIV2_PAIR_ABI)
chainlink = w3.eth.contract(address=Web3.to_checksum_address(CHAINLINK_ETH_USD), abi=CHAINLINK_ABI)

MIGRATION_BLOCK = 23_982_496

check_points = {
    "6mo before": MIGRATION_BLOCK - 7200 * 180,
    "1mo before": MIGRATION_BLOCK - 7200 * 30,
    "6h before":  MIGRATION_BLOCK - 900,
    "Migration":  MIGRATION_BLOCK,
    "6h after":   MIGRATION_BLOCK + 900,
    "1wk after":  MIGRATION_BLOCK + 7200 * 7,
    "1mo after":  MIGRATION_BLOCK + 7200 * 30,
    "Now":        w3.eth.block_number,
}

labels = []
ixs_vals = []
eth_vals = []

for label, block in check_points.items():
    r0, r1, _ = pair.functions.getReserves().call(block_identifier=block)
    labels.append(label)
    ixs_vals.append(r0 / 1e18 / 1e6)  # millions
    eth_vals.append(r1 / 1e18)

# Compute k = IXS_raw * ETH_raw (in trillions for readability)
k_vals = [ixs * 1e6 * eth / 1e9 for ixs, eth in zip(ixs_vals, eth_vals)]  # billions

# Bar plot
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 11))
fig.suptitle("V2 Pool Reserves Around Migration", fontsize=14, fontweight="bold")

x = np.arange(len(labels))
migration_idx = labels.index("Migration")

# Color: blue before migration, red at/after
colors = ["steelblue" if i < migration_idx else "indianred" for i in range(len(labels))]

# IXS reserves
ax1.bar(x, ixs_vals, color=colors, alpha=0.85, edgecolor="white", linewidth=0.5)
ax1.axvline(migration_idx - 0.5, color="red", linestyle="--", alpha=0.7, label="Migration")
ax1.set_ylabel("IXS (millions)")
ax1.set_title("IXS Reserve")
ax1.set_xticks(x)
ax1.set_xticklabels(labels, rotation=35, ha="right")
ax1.legend()
ax1.set_ylim(0, 6)
ax1.grid(True, alpha=0.3, axis="y")
# Add value labels
for i, v in enumerate(ixs_vals):
    ax1.text(i, v + 0.05, f"{v:.1f}M", ha="center", va="bottom", fontsize=9)

# ETH reserves
ax2.bar(x, eth_vals, color=colors, alpha=0.85, edgecolor="white", linewidth=0.5)
ax2.axvline(migration_idx - 0.5, color="red", linestyle="--", alpha=0.7, label="Migration")
ax2.set_ylabel("ETH")
ax2.set_title("ETH Reserve")
ax2.set_xticks(x)
ax2.set_xticklabels(labels, rotation=35, ha="right")
ax2.legend()
ax2.set_ylim(0, 265)
ax2.grid(True, alpha=0.3, axis="y")
for i, v in enumerate(eth_vals):
    ax2.text(i, v + 2, f"{v:.0f}", ha="center", va="bottom", fontsize=9)

# k = x * y (constant product)
ax3.bar(x, k_vals, color=colors, alpha=0.85, edgecolor="white", linewidth=0.5)
ax3.axvline(migration_idx - 0.5, color="red", linestyle="--", alpha=0.7, label="Migration")
ax3.set_ylabel("k (billions)")
ax3.set_title("Constant Product k = IXS × ETH")
ax3.set_xticks(x)
ax3.set_xticklabels(labels, rotation=35, ha="right")
ax3.legend()
ax3.set_ylim(0, 1.25)
ax3.grid(True, alpha=0.3, axis="y")
for i, v in enumerate(k_vals):
    ax3.text(i, v + max(k_vals) * 0.01, f"{v:,.1f}B", ha="center", va="bottom", fontsize=9)

plt.tight_layout()
fig.subplots_adjust(right=0.95)
plt.savefig("notebooks/plots/ixs_v2_reserves_migration.png", dpi=150, bbox_inches="tight")
plt.show()
print("Saved to notebooks/plots/ixs_v2_reserves_migration.png")

# Print % retained
print(f"\nLiquidity retained in V2 (vs 1d before):")
pre_idx = labels.index("6h before")
for i in range(migration_idx, len(labels)):
    ixs_pct = ixs_vals[i] / ixs_vals[pre_idx] * 100
    eth_pct = eth_vals[i] / eth_vals[pre_idx] * 100
    print(f"  {labels[i]:<12}: IXS {ixs_pct:.0f}%, ETH {eth_pct:.0f}%")
