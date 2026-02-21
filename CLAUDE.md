# Arrakis2 - UniswapV4 Market Making Analysis

## Project Overview

Two analysis challenges in one repo:

1. **MORPHO/ETH** (Challenge 1): Slippage analysis, liquidity distribution, DEX vs CEX comparison for an existing UniV4 pool.
2. **IXS/ETH Migration** (Challenge 2): Liquidity migration analysis from UniswapV2 to Arrakis-managed UniswapV4 vault. All data obtained via RPC calls to the blockchain.

### Challenge 2 Deliverables (from PDF brief)

**D1 - Execution Quality Comparison:**
- Historical slippage for $1K/$5K/$10K/$50K in both directions (IXS→ETH, ETH→IXS) on V2 pre-migration
- Same trade sizes/directions on V4 post-migration
- Time-series visualization of execution quality across the migration
- V4 liquidity distribution across tick ranges vs theoretical full-range
- Slippage formula: `|spot_price - avg_execution_price| / spot_price × 100 - fee × 100`

**D2 - Vault Performance Analysis:**
- Vault token amounts over time (IXS and ETH) and composition (USD value split)
- Vault performance vs HODL benchmark since inception
- Theoretical full-range LP performance over same period
- Performance differential analysis and tradeoff explanation

**D3 - Client Synthesis:**
- Was migration beneficial? Under which metrics?
- Tradeoffs the client should understand
- Quantitative argument for migrating remaining V2 funds
- Short client-facing summary

### Discovered Pool Parameters
- V4 fee: 7000 (0.7% in V4 ppm)
- V4 tickSpacing: 50
- V4 hooks: address(0)
- V2 token ordering: IXS=token0, WETH=token1
- V4 token ordering: ETH(0x0)=currency0, IXS=currency1
- Vault token ordering: IXS=token0, NativeETH(0xEeee...EEeE)=token1
- Migration block: ~23,982,496 (2025-12-10) — V4 pool creation
- Vault first deposit: block 23,982,428 (slightly before V4 pool init)

## Key Contracts

### Challenge 1 - MORPHO/ETH
- StateView: `0x7ffe42c4a5deea5b0fec41c94c136cf115597227`
- Quoter: `0x52f0e24d1c21c8a0cb1e5a5dd6198556bd9e1203`
- Pool ID: `0xd9f5cbaeb88b7f0d9b0549257ddd4c46f984e2fc4bccf056cc254b9fe3417fff`

### Challenge 2 - IXS/ETH Migration
- IXS Token: `0x73d7c860998CA3c01Ce8c808F5577d94d545d1b4` (18 decimals)
- WETH: `0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2`
- UniV2 Pair: `0xC09bf2B1Bc8725903C509e8CAeef9190857215A8`
- UniV4 Pool ID: `0xd54a5e98dc3d0a90a058d4e46b2db9e7d92dbf50598833035e1f27eac4f23a4f`
- Arrakis Vault: `0x90bde935ce7feb6636afd5a1a0340af45eeae600`
- Chainlink ETH/USD: `0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419`

## Setup

```bash
cd backend
uv sync
```

Create `backend/.env`:
```
rpc_url_mainnet=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
```

## Running Notebooks

```bash
cd backend
uv run jupyter notebook
```

## Module Structure

> **Repo split TODO:** This repo currently contains both challenges. Shared modules
> (config, abis, amm_math, async_rpc, multicall) are used by both. When splitting
> Challenge 2 into its own repo, copy the shared modules and remove all Challenge 1
> code (slippage.py, tvl.py, liquidity_distribution.py, cex_analysis.py,
> optimized_v4_fetch.py, and Challenge 1 notebooks).

```
backend/src/
├── config.py                    # All contract addresses and pool params [SHARED]
├── abis.py                      # Minimal smart contract ABIs [SHARED]
├── amm_math.py                  # Price/tick conversion math (Decimal) [SHARED]
├── async_rpc.py                 # Async RPC helpers [SHARED]
├── multicall.py                 # Multicall3 batching [SHARED]
│
│   # Challenge 1 - MORPHO/ETH (remove when splitting repo)
├── slippage.py                  # V4 real-time slippage
├── tvl.py                       # TVL calculations (on-chain + GraphQL)
├── liquidity_distribution.py    # Tick bitmap scanning
├── cex_analysis.py              # CEX orderbook analysis (CCXT)
├── optimized_v4_fetch.py        # Optimized batch fetching
│
│   # Challenge 2 - IXS/ETH Migration
├── block_utils.py               # Block sampling and timestamp utils
├── price_feeds.py               # Chainlink + pool price feeds
├── migration_detection.py       # Binary search for migration block
├── v2_slippage.py               # UniV2 constant-product slippage
├── v4_historical_slippage.py    # V4 slippage at historical blocks
├── vault_performance.py         # Arrakis vault tracking + benchmarks
├── vault_rebalancing.py         # Active range tracking & capital efficiency
└── capital_efficiency.py        # Net slippage, break-even, capital efficiency
```

## Conventions

- Type hints on all function parameters and return types
- Short docstrings on all functions
- Functions take addresses/ABIs as params (not hardcoded imports from config)
- Use `Decimal` for price math where precision matters
- Use `web3.py` for all on-chain interactions
- Package management via `uv`
- Keep files small and focused — split into logical modules

## Directory Structure Rules

**No parallel structures.** There is ONE canonical location for each type of file:

- **Plots:** `backend/notebooks/plots/` — the ONLY plots directory. Notebooks save here
  (relative as `plots/`). Temp scripts also save here. Never create `backend/plots/`.
- **Temp scripts:** `backend/temp_scripts/` — all prototype/test `.py` files go here.
  Never leave loose `.py` files in `backend/` root.
- **Source modules:** `backend/src/` — all importable Python code.
- **Notebooks:** `backend/notebooks/` — all `.ipynb` files.
- **Data exports:** `backend/notebooks/data/` — CSV exports from notebooks.

## Notebook Development Workflow

**Always test before adding to notebooks.** Notebooks are client-facing — never add untested
code or plots directly. For any new analysis section:

1. Write a test script in `backend/temp_scripts/` that exercises the new module functions
   and generates the plots (saving to `notebooks/plots/`)
2. Run it from `backend/`: `uv run python temp_scripts/my_test.py`
3. Inspect the output (print statements, saved PNGs) to verify correctness
4. Iterate on the plot styling until it looks good
5. Only then add the finalized code to the notebook
6. Delete the temp script when done (or keep for reference if useful)

## Linting & Type Checking

Always run both before committing:

```bash
cd backend
ruff check src/ --fix        # Lint and auto-fix
uv run pyright src/          # Type checking
```
