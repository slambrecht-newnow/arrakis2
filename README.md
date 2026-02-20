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
│   ├── vault_performance.py         # Arrakis vault tracking + benchmarks (IXS)
│   └── capital_efficiency.py        # Net slippage, break-even, capital efficiency (IXS)
├── notebooks/
│   ├── slippage.ipynb               # Challenge 1: Slippage analysis
│   ├── liquidity_analysis.ipynb     # Challenge 1: Liquidity distribution
│   ├── cex_comparison.ipynb         # Challenge 1: DEX vs CEX
│   ├── optimization_benchmark.ipynb # Challenge 1: Multicall optimization
│   ├── ixs_execution_quality.ipynb  # Challenge 2: V2 vs V4 execution quality
│   ├── ixs_vault_performance.ipynb  # Challenge 2: Vault performance analysis
│   ├── ixs_client_synthesis.ipynb   # Challenge 2: Client synthesis & recommendations
│   ├── data/                        # Exported CSVs (slippage_summary, vault_summary)
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

Analysis of a liquidity migration from UniswapV2 to an Arrakis-managed UniswapV4 vault (Dec 10, 2025). All data obtained directly via RPC calls — no GraphQL or subgraph dependencies.

### D1: Execution Quality (V2 vs V4)

**Pool parameters:** V2 fee 0.30% | V4 fee 0.70% (tickSpacing=50, hooks=address(0))

1.1) Historical slippage computed for $1K/$5K/$10K/$50K in both directions (IXS→ETH and ETH→IXS) across ~6 months pre-migration (V2) and post-migration (V4). V2 uses `getReserves()` + constant-product formula; V4 uses `StateView.getSlot0()` + `Quoter.quoteExactInputSingle()` at archive blocks.

1.2) V4 concentrated liquidity delivers significantly lower *price impact* (gross slippage) than V2 for all trade sizes. The capital efficiency ratio (V2 gross / V4 gross) quantifies how much more efficient V4 is.

1.3) **Net slippage analysis (NEW):** Net cost = gross slippage + fee. The V4 fee (0.70%) is 2.3× higher than V2 (0.30%), creating a 0.40pp fee premium. Break-even analysis identifies the exact trade size where V4 becomes cheaper on net cost despite the higher fee. Visualized with break-even plots and net slippage time series.

1.4) V4 liquidity distribution scanned via tick bitmap — most capital concentrated near the active tick. Compared against a theoretical full-range (V2-style) uniform distribution to visualize capital efficiency gains.

1.5) **Theory sections (NEW):** Derivation of V2 slippage formula (`S = Δx/(x+Δx)`), V4 concentrated slippage formula (`S = 1 - 1/(1 + Δx√P/L)²`), and the net cost framework.

### D2: Vault Performance

2.1) Tracked vault token amounts (IXS + ETH) daily since inception via `totalUnderlying()`. Initial deposit: ~1.88M IXS + 70 ETH; grew to ~4.2M IXS + 97 ETH. Vault composition visualized as USD stacked area (IXS value + ETH value).

2.2) Compared vault against two benchmarks: **HODL** (hold initial amounts, no LP) and **full-range LP** (V2-style impermanent loss formula: `V = V_hodl × 2√r/(1+r)`). Concentrated positions amplify both fee capture *and* impermanent loss relative to full-range.

2.3) Prices sourced entirely on-chain: ETH/USD from Chainlink oracle, IXS/ETH from V4 pool `sqrtPriceX96`. No external price APIs.

2.4) **Return decomposition (NEW):** Vault return = price return + IL (full-range) + management premium. The management premium quantifies Arrakis's active management alpha vs passive full-range LP. Visualized as stacked area chart and waterfall bar.

2.5) **Annualized performance (NEW):** Vault, HODL, and full-range returns annualized via `(final/initial)^(365/days) - 1` for fair comparison.

### D3: Client Synthesis

3.1) **Hybrid notebook (NEW):** Loads computed CSVs from D1 and D2 — all numbers in the synthesis are programmatically derived, not hard-coded.

3.2) Migration is beneficial under execution quality metrics — traders get better prices, especially on larger trades. The higher fee tier is a tradeoff: better for LPs (more revenue), but small trades may be cheaper on V2 in net terms.

3.3) Key risks: amplified impermanent loss in concentrated ranges, rebalancing gas costs (not visible in `totalUnderlying`), smart contract risk from the additional vault layer, and dependency on Arrakis's rebalancing strategy quality.

3.4) **Key Metrics Dashboard (NEW):** Single computed summary including price impact improvement, net cost break-even, capital efficiency multiplier, annualized returns, and management premium.

### Key Contracts

| Contract | Address |
|----------|---------|
| UniV2 Pair (IXS/WETH) | `0xC09bf2B1Bc8725903C509e8CAeef9190857215A8` |
| UniV4 Pool ID | `0xd54a5e98dc3d...` (fee=7000, tickSpacing=50) |
| Arrakis Vault | `0x90bde935ce7feb6636afd5a1a0340af45eeae600` |
| Chainlink ETH/USD | `0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419` |
| V4 Quoter (Challenge 1) | `0x52f0e24d1c21c8a0cb1e5a5dd6198556bd9e1203` |
| MORPHO Pool ID (Challenge 1) | `0xd9f5cbaeb88b7f0d9b0549257ddd4c46f984e2fc...` |
