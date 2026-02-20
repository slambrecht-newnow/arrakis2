# Arrakis - UniV4 Market Making Analysis

Analysis of the ETH/MORPHO Uniswap V4 pool: slippage mechanics, liquidity distribution, and DEX vs CEX execution comparison.
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
│   ├── config.py              # Contract addresses, pool params
│   ├── abis.py                # StateView, Quoter ABIs
│   ├── slippage.py            # V4 Quoter slippage calculation
│   ├── tvl.py                 # TVL from on-chain + GraphQL
│   ├── liquidity_distribution.py  # Tick bitmap scanning
│   ├── amm_math.py            # Price/tick conversions
│   ├── cex_analysis.py        # Orderbook analysis via CCXT
│   ├── multicall.py           # Multicall3 batching utilities
│   ├── optimized_v4_fetch.py  # Optimized batch data fetching
│   └── async_rpc.py           # Async RPC helpers
├── notebooks/
│   ├── slippage.ipynb             # Q1: Slippage analysis
│   ├── liquidity_analysis.ipynb   # Q2: Liquidity distribution
│   ├── cex_comparison.ipynb       # Q3: DEX vs CEX
│   ├── optimization_benchmark.ipynb  # Bonus: Multicall optimization
│   └── plots/                     # Generated charts
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

## Key Contracts

- **V4 Singleton**: `0x000000000004444c5dc75cB358380D2e3dE08A90`
- **V4 Quoter**: `0x52f0e24d1c21c8a0cb1e5a5dd6198556bd9e1203`
- **Pool ID**: `0xd9f5cbaeb88b7f0d9b0549257ddd4c46f984e2fc...`
