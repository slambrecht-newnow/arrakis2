# Challenge 2: IXS/ETH Liquidity Migration Analysis

Deep-dive into the analysis of a liquidity migration from UniswapV2 to an Arrakis-managed UniswapV4 vault. All data obtained directly via RPC calls to Ethereum mainnet — no subgraphs, no GraphQL.

## Background

IXS (IX Swap) had liquidity in a UniswapV2 IXS/WETH pair. On December 10, 2025 (block ~23,982,496), the project migrated to an Arrakis-managed UniswapV4 concentrated liquidity vault. This analysis evaluates whether the migration was beneficial from three angles: execution quality for traders (D1), vault performance for LPs (D2), and a synthesis for the client (D3).

## Key Contracts

| Contract | Address | Role |
|---|---|---|
| UniV2 Pair | `0xC09bf2B1Bc8725903C509e8CAeef9190857215A8` | IXS/WETH constant-product pool |
| V4 Pool | ID: `0xd54a5e98...` | IXS/ETH concentrated liquidity |
| Arrakis Vault | `0x90bde935ce7feb6636afd5a1a0340af45eeae600` | Manages V4 position |
| V4 StateView | `0x7ffe42c4a5deea5b0fec41c94c136cf115597227` | Read pool state |
| V4 Quoter | `0x52f0e24d1c21c8a0cb1e5a5dd6198556bd9e1203` | Simulate swaps |
| Chainlink ETH/USD | `0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419` | On-chain price oracle |

### Discovered Pool Parameters

The V4 pool uses **non-standard** parameters that required iterative discovery:

- **fee = 7000** (0.70% — higher than V2's 0.30%)
- **tickSpacing = 50** (non-standard; not 1/10/60/200)
- **hooks = address(0)** (no custom hooks)
- **currency0 = ETH** (`0x000...000`), **currency1 = IXS**
- Pool ID verified via `keccak256(abi.encode(currency0, currency1, fee, tickSpacing, hooks))`

Token ordering differs across contracts:
- **V2**: token0 = IXS, token1 = WETH
- **V4**: currency0 = ETH (native), currency1 = IXS
- **Vault**: token0 = IXS, token1 = `0xEeee...EEeE` (native ETH sentinel)

---

## Source Module Walkthrough

### `config.py` — Central Configuration

All contract addresses, pool parameters, and constants in one place. Every other module references `config.py` for addresses but receives them as function parameters (not hardcoded imports), keeping functions testable.

Key constants:
```python
IXS_FEE = 7000           # 0.7% in V4 ppm units
IXS_TICK_SPACING = 50     # Non-standard
BLOCKS_PER_DAY = 7200     # ~12s block time
```

### `amm_math.py` — Price/Tick Conversions

Handles the core V4 price encoding. UniswapV4 stores prices as `sqrtPriceX96 = sqrt(price) * 2^96`, a fixed-point representation.

```python
def sqrt_price_x96_to_price(sqrt_price_x96: int) -> Decimal:
    sqrt_price = Decimal(sqrt_price_x96) / Q96   # Q96 = Decimal(2**96)
    return sqrt_price ** 2                         # price = (sqrtP / 2^96)^2
```

Uses Python `Decimal` with 50-digit precision to avoid floating-point errors in price calculations. Also provides `tick_to_sqrt_price()` for tick range conversions.

### `migration_detection.py` — Finding the Migration Block

Uses **binary search** over archive RPC calls (not event scanning) to pinpoint the exact migration moment. This is necessary because Alchemy's free tier restricts `eth_getLogs` to small block ranges, but `eth_call` with `block_identifier` works for any historical block.

Three signals are detected:

1. **`find_v4_pool_creation_block()`** — Binary searches for the first block where `StateView.getSlot0(poolId)` returns non-zero `sqrtPriceX96`. This is when the V4 pool was initialized.

2. **`find_vault_first_deposit_block()`** — Binary searches for the first block where `vault.totalUnderlying()` returns non-zero amounts. This is when the Arrakis vault received its first deposit.

3. **`detect_v2_liquidity_drop()`** — Samples V2 reserves at daily intervals around the vault deposit and finds where reserves drop >50%.

The vault deposit block (23,982,428) actually precedes V4 pool creation (23,982,496) by ~68 blocks, showing the vault was set up slightly before the pool was initialized.

### `block_utils.py` — Block Sampling

Generates evenly-spaced block samples for time-series analysis:

```python
def generate_daily_block_samples(start_block, end_block) -> list[int]:
    # Yields blocks ~7200 apart (one per day at ~12s block time)
```

Also handles block→timestamp→date conversion via RPC, which is how all x-axes in the plots show real dates.

### `price_feeds.py` — On-Chain Price Sourcing

All prices are sourced entirely on-chain (no external APIs):

- **ETH/USD**: Chainlink oracle `latestRoundData()` at historical blocks (8 decimal places)
- **IXS/ETH pre-migration**: V2 reserves ratio (`reserve_ETH / reserve_IXS`)
- **IXS/ETH post-migration**: V4 `sqrtPriceX96` converted via `amm_math`

The `batch_ixs_prices()` function automatically switches between V2 and V4 sources based on whether the block is before or after the migration block.

### `v2_slippage.py` — UniswapV2 Slippage

V2 uses the constant-product formula `x * y = k`. Only **1 RPC call per block** is needed (`getReserves()`), then all trade sizes are computed locally.

```python
def calculate_v2_amount_out(amount_in, reserve_in, reserve_out, fee_bps=30):
    # amount_out = (amount_in * (10000 - fee) * reserve_out) /
    #              (reserve_in * 10000 + amount_in * (10000 - fee))
```

Slippage is computed two ways:
- **Gross** (price impact only): Compare spot price to execution price with fee=0
- **Net** (total cost): Compare spot price to execution price with fee applied

This distinction is critical because V4 has a 0.70% fee vs V2's 0.30%.

### `v4_historical_slippage.py` — UniswapV4 Slippage at Archive Blocks

Unlike V2, V4 concentrated liquidity cannot be computed from a simple formula. Each quote requires an on-chain simulation via the Quoter contract:

1. **Spot price**: `StateView.getSlot0(poolId)` → `sqrtPriceX96`
2. **Execution price**: `Quoter.quoteExactInputSingle(params)` → `amountOut`

Both called with `block_identifier=block` for historical state.

Direction handling is non-trivial:
```python
if zero_for_one:
    # Swapping token0→token1: exec_price = amount_out / amount_in
    exec_price = amount_out_wei / amount_in_wei
else:
    # Swapping token1→token0: exec_price = amount_in / amount_out
    exec_price = amount_in_wei / amount_out_wei
```

Both prices must be in the same units (token1/token0) for the slippage formula to work correctly. Getting this wrong was a bug that caused negative slippage values.

### `capital_efficiency.py` — Cross-System Comparison

Pure-computation module (no RPC calls) that takes V2 and V4 results and produces summary metrics:

- **`compute_net_slippage_summary()`**: Time-averages gross and net slippage across all sampled blocks per trade size. Returns a DataFrame with V2 vs V4 comparison including improvement percentages.

- **`find_breakeven_trade_size()`**: Linearly interpolates between trade sizes to find where V4 net cost equals V2 net cost. Because V4's fee is 0.40pp higher, V4 only wins on net cost when the price impact savings exceed 0.40pp — which only happens at large trade sizes.

- **`compute_capital_efficiency_ratio()`**: Simple `v2_gross / v4_gross` — measures how many times more capital-efficient V4 is at avoiding price impact.

### `vault_performance.py` — Vault Tracking and Benchmarks

Tracks the Arrakis vault against two benchmarks:

1. **HODL**: Just hold the initial token amounts, no LP. Pure price exposure.
2. **Full-range LP**: V2-style constant-product LP with the impermanent loss formula:
   ```
   V_LP = V_HODL * 2*sqrt(r) / (1+r)
   ```
   where `r = current_price_ratio / initial_price_ratio`.

**Return decomposition** breaks the vault return into three components:
```python
price_return = hodl[t] - hodl[0]              # Pure market movement
il_fullrange = fullrange[t] - hodl[t]         # IL for passive full-range
management_premium = vault[t] - fullrange[t]  # Arrakis alpha
```

Identity: `vault = hodl_initial + price_return + il_fullrange + management_premium`

This was verified to pass exactly (within floating-point precision) across all sampled blocks.

**Annualized return**: `((final/initial)^(365/days) - 1) * 100` for fair comparison across different time periods.

---

## Notebooks

### D1: `ixs_execution_quality.ipynb`

Computes historical slippage for $1K/$5K/$10K/$50K in both directions (IXS→ETH buy and ETH→IXS sell) across ~6 months pre-migration (V2) and post-migration (V4).

Key sections:
1. **Theory**: Derivation of V2 (`S = Δx/(x+Δx)`) and V4 (`S = 1 - 1/(1+Δx√P/L)²`) slippage formulas, plus the net cost framework
2. **Gross slippage comparison**: 2x2 grid — buy/sell × V2/V4
3. **Net slippage comparison**: Same grid but including fees
4. **Break-even analysis**: Where V4 becomes cheaper despite higher fee
5. **Capital efficiency**: V2 gross / V4 gross ratios
6. **Liquidity distribution**: V4 tick bitmap vs theoretical full-range

Exports `data/slippage_summary.csv` for use in D3.

### D2: `ixs_vault_performance.ipynb`

Tracks vault composition and performance over time.

Key sections:
1. **Theory**: IL derivation from first principles, HODL formula, decomposition identity
2. **Vault composition**: IXS + ETH amounts over time, USD stacked area
3. **HODL benchmark**: Side-by-side vault vs HODL
4. **Full-range LP benchmark**: With IL formula applied
5. **Return decomposition**: Stacked area + waterfall chart
6. **Annualized performance**: Fair cross-strategy comparison

Exports `data/vault_summary.csv` for use in D3.

### D3: `ixs_client_synthesis.ipynb`

Hybrid notebook that loads computed CSVs from D1 and D2 — all numbers are programmatically derived, not hard-coded.

Includes:
- Executive summary with key verdict
- Per-metric analysis (execution quality, vault performance)
- Key metrics dashboard
- Client-facing summary paragraph
- Risks and tradeoffs

---

## Key Findings

### Execution Quality (D1)

- V4 gross slippage (price impact) is **comparable** to V2, not dramatically better. Capital efficiency ratio is ~1.0x.
- V4's higher fee (0.70% vs 0.30%) means **V4 is more expensive on net cost** for most trade sizes.
- Break-even point is around ~$33K for buys (IXS→ETH). For sells, V4 is more expensive at all tested sizes.
- The execution quality argument alone does not justify migration.

### Vault Performance (D2)

- **This is where the migration shines.** The vault returned ~-26% vs HODL's ~-58% and full-range LP's ~-60%.
- Management premium: ~+$197K — Arrakis's active management significantly outperformed passive strategies.
- The vault captured fees and managed rebalancing to mitigate impermanent loss.

### Client Synthesis (D3)

- Migration is beneficial **primarily for LPs**, not traders. The vault's active management provides substantial alpha.
- For traders, the higher fee is a real cost. Small trades are cheaper on V2.
- Risks: amplified IL in concentrated ranges, rebalancing gas costs (hidden in `totalUnderlying`), smart contract risk from the vault layer.

---

## Technical Notes

### Alchemy Free Tier Limits
- `eth_getLogs` fails for large block ranges — use binary search on state changes instead
- `eth_call` with `block_identifier` works fine for any archive block

### Token Ordering
V2 and V4 have **opposite** token ordering for this pair. V2: IXS=token0, WETH=token1. V4: ETH=currency0, IXS=currency1. This means `zero_for_one=True` in V4 is ETH→IXS (buying IXS), while in V2 the equivalent is `reserve_in=token1, reserve_out=token0`.

### Slippage Direction
When `zero_for_one=False` (selling token1), execution price = `amount_in / amount_out` (not `amount_out / amount_in`). Both prices must be in the same units (token1/token0) for the slippage percentage to be correct.

### Matplotlib Large Int Overflow
V4 liquidity values (~10^22) exceed C `long` max. Must cast to `float()` before passing to matplotlib's `ax.bar()`.
