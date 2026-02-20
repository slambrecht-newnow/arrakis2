# Arrakis - UniV4 Market Making Analysis

Two analysis challenges: (1) ETH/MORPHO V4 pool analysis and (2) IXS/ETH liquidity migration from UniswapV2 to Arrakis-managed V4 vault.

**Note:** Pool state (prices, ticks, liquidity) changes over time. Outputs may vary slightly depending on when the code is run.

## Key Results

### Q1: Slippage vs Trade Size

**Pool**: ETH/MORPHO (fee: 0.30%, TVL: ~$3.27M)

1.1) Getting the sublinear slippage for the specified dollar amounts

1.2) Finding TVL both on chain using the V4 singleton and the GraphQL

1.3) Showing that slippage is sublinear by deriving the hyperbolic curve based on V2 math (`S = Δx/(x+Δx)`)

### Q2: Liquidity Distribution

2.1) Pulled liquidity distribution from V4 singleton via tick bitmap scanning. Log-scale can visualize it nicely.

2.2) We see that liquidity is roughly speaking concentrated around tick. The V3/V4 slippage formula within an active range is `1 - 1/(1 + Δx√p/L)²`

2.4) TVL alone is insufficient: two pools with identical TVL but different liquidity distributions will have vastly different execution quality. Must consider liquidity depth at the current price.

### Q3: DEX vs CEX Comparison

3.1) Binance has deepest MORPHO liquidity (~$293,885 (ask) within 2% of mid). Also checked Bitget, BitMart.

3.2) CEX slippage (buying MORPHO) in MORPHO/USDT across Binance, Bitget, and BitMart. Slippage is generally low.

3.3) V4 DEX slippage is higher than CEX for same trade sizes. CEX wins on total cost (slippage + fees) at all sizes tested.

### Bonus: V4 Data Optimization

Used Multicall3 to batch sequential RPC calls into 2 calls. Speeding up fetch time by ~50x. See `optimization_benchmark.ipynb`. Note, I did not have a lot of time left for this question



## Repository Structure

```
backend/
├── src/
│   ├── config.py                    # Contract addresses, pool params (both challenges)
│   ├── abis.py                      # StateView, Quoter, V2 Pair, Vault, Chainlink ABIs
│   ├── amm_math.py                  # Price/tick conversions (Decimal precision)
│   ├── slippage.py                  # V4 real-time slippage (MORPHO)
│   ├── tvl.py                       # TVL from on-chain + GraphQL
│   ├── liquidity_distribution.py    # Tick bitmap scanning
│   ├── cex_analysis.py              # CEX orderbook analysis via CCXT
│   ├── multicall.py                 # Multicall3 batching utilities
│   ├── async_rpc.py                 # Async RPC helpers
│   ├── optimized_v4_fetch.py        # Optimized batch data fetching
│   ├── block_utils.py               # Block sampling and timestamps (IXS)
│   ├── price_feeds.py               # Chainlink + pool price feeds (IXS)
│   ├── migration_detection.py       # Binary search for migration block (IXS)
│   ├── v2_slippage.py               # UniV2 constant-product slippage (IXS)
│   ├── v4_historical_slippage.py    # V4 slippage at historical blocks (IXS)
│   └── vault_performance.py         # Arrakis vault tracking + benchmarks (IXS)
├── notebooks/
│   ├── slippage.ipynb               # Challenge 1: Slippage analysis
│   ├── liquidity_analysis.ipynb     # Challenge 1: Liquidity distribution
│   ├── cex_comparison.ipynb         # Challenge 1: DEX vs CEX
│   ├── optimization_benchmark.ipynb # Challenge 1: Multicall optimization
│   ├── ixs_execution_quality.ipynb  # Challenge 2: V2 vs V4 execution quality
│   ├── ixs_vault_performance.ipynb  # Challenge 2: Vault performance analysis
│   ├── ixs_client_synthesis.ipynb   # Challenge 2: Client synthesis & recommendations
│   └── plots/                       # Generated charts
└── pyproject.toml
```

## Setup

```bash
cd backend
uv sync
```

Create `backend/.env`:
```
rpc_url_mainnet=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
```

Run notebooks:
```bash
uv run jupyter notebook
```

## Challenge 2: IXS/ETH Liquidity Migration

Analysis of a liquidity migration from UniswapV2 to an Arrakis-managed UniswapV4 vault. All data obtained via RPC calls.

### Key Results

**D1 - Execution Quality:**
- V4 concentrated liquidity provides lower price impact than V2 for all trade sizes
- V4 fee (0.70%) is higher than V2 (0.30%), partially offsetting the improvement on net cost
- Larger trades ($10K+) benefit most from the migration

**D2 - Vault Performance:**
- Vault tracks IXS and ETH amounts over time with active rebalancing
- Compared against HODL and full-range LP benchmarks

**D3 - Client Synthesis:**
- Migration is beneficial under price impact metrics
- Recommends migrating remaining V2 liquidity to consolidate depth

### Key Contracts (Challenge 2)

- **UniV2 Pair (IXS/WETH):** `0xC09bf2B1Bc8725903C509e8CAeef9190857215A8`
- **UniV4 Pool ID:** `0xd54a5e98dc3d...` (fee=7000, tickSpacing=50)
- **Arrakis Vault:** `0x90bde935ce7feb6636afd5a1a0340af45eeae600`
- **Chainlink ETH/USD:** `0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419`

### Key Contracts (Challenge 1)

- **V4 Quoter**: `0x52f0e24d1c21c8a0cb1e5a5dd6198556bd9e1203`
- **MORPHO Pool ID**: `0xd9f5cbaeb88b7f0d9b0549257ddd4c46f984e2fc...`
