"""
CEX orderbook analysis for cross-venue execution comparison.

Provides functions to fetch orderbook data from centralized exchanges
and calculate slippage for comparison with DEX execution.
"""

from dataclasses import dataclass
from typing import Any
import ccxt


@dataclass
class OrderbookSnapshot:
    """Snapshot of an exchange orderbook."""
    exchange: str
    symbol: str
    timestamp: int
    bids: list[list[float]]  # [[price, size], ...]
    asks: list[list[float]]  # [[price, size], ...]
    mid_price: float
    spread: float
    spread_bps: float


@dataclass
class SlippageResult:
    """Result of slippage calculation from orderbook."""
    exchange: str
    trade_size_usd: float
    direction: str  # "buy" or "sell"
    mid_price: float
    avg_execution_price: float
    slippage_percentage: float
    levels_consumed: int
    fully_filled: bool
    total_filled_usd: float


def create_exchange(exchange_name: str) -> ccxt.Exchange:
    """
    Create a CCXT exchange instance.

    Args:
        exchange_name: Name of the exchange (e.g., 'bitget', 'binance')

    Returns:
        Configured exchange instance
    """
    exchange_class = getattr(ccxt, exchange_name)
    return exchange_class({
        'enableRateLimit': True,
    })


def fetch_orderbook(
    exchange: ccxt.Exchange,
    symbol: str = "MORPHO/USDT",
    limit: int = 100
) -> OrderbookSnapshot:
    """
    Fetch current orderbook from CEX.

    Args:
        exchange: CCXT exchange instance
        symbol: Trading pair symbol
        limit: Number of orderbook levels to fetch

    Returns:
        OrderbookSnapshot with bids, asks, and spread info
    """
    orderbook = exchange.fetch_order_book(symbol, limit)

    bids = orderbook['bids']  # [[price, size], ...]
    asks = orderbook['asks']  # [[price, size], ...]

    best_bid = bids[0][0] if bids else 0
    best_ask = asks[0][0] if asks else 0
    mid_price = (best_bid + best_ask) / 2 if best_bid and best_ask else 0
    spread = best_ask - best_bid if best_bid and best_ask else 0
    spread_bps = (spread / mid_price * 10000) if mid_price > 0 else 0

    return OrderbookSnapshot(
        exchange=exchange.id,
        symbol=symbol,
        timestamp=orderbook.get('timestamp', 0) or 0,
        bids=bids,
        asks=asks,
        mid_price=mid_price,
        spread=spread,
        spread_bps=spread_bps
    )

def get_orderbook_depth_summary(orderbook: OrderbookSnapshot) -> dict[str, Any]:
    """
    Calculate orderbook depth statistics.

    Args:
        orderbook: OrderbookSnapshot to analyze

    Returns:
        Dict with depth statistics
    """
    def calc_bid_depth(levels: list[list[float]], pct_below_mid: float) -> float:
        """Calculate total bid depth within X% below mid price."""
        threshold = orderbook.mid_price * (1 - pct_below_mid / 100)
        total = 0.0
        for price, size in levels:
            if price >= threshold:
                total += price * size
            else:
                break  # Bids are sorted descending, so we can stop
        return total

    def calc_ask_depth(levels: list[list[float]], pct_above_mid: float) -> float:
        """Calculate total ask depth within X% above mid price."""
        threshold = orderbook.mid_price * (1 + pct_above_mid / 100)
        total = 0.0
        for price, size in levels:
            if price <= threshold:
                total += price * size
            else:
                break  # Asks are sorted ascending, so we can stop
        return total

    bid_depth_1pct = calc_bid_depth(orderbook.bids, 1)
    ask_depth_1pct = calc_ask_depth(orderbook.asks, 1)

    bid_depth_2pct = calc_bid_depth(orderbook.bids, 2)
    ask_depth_2pct = calc_ask_depth(orderbook.asks, 2)

    bid_depth_5pct = calc_bid_depth(orderbook.bids, 5)
    ask_depth_5pct = calc_ask_depth(orderbook.asks, 5)

    total_bid_depth = sum(p * s for p, s in orderbook.bids)
    total_ask_depth = sum(p * s for p, s in orderbook.asks)

    return {
        'mid_price': orderbook.mid_price,
        'spread_bps': orderbook.spread_bps,
        'bid_depth_1pct_usd': bid_depth_1pct,
        'ask_depth_1pct_usd': ask_depth_1pct,
        'bid_depth_2pct_usd': bid_depth_2pct,
        'ask_depth_2pct_usd': ask_depth_2pct,
        'bid_depth_5pct_usd': bid_depth_5pct,
        'ask_depth_5pct_usd': ask_depth_5pct,
        'total_bid_depth_usd': total_bid_depth,
        'total_ask_depth_usd': total_ask_depth,
        'num_bid_levels': len(orderbook.bids),
        'num_ask_levels': len(orderbook.asks)
    }


# 3.2

def calculate_cex_slippage(
    orderbook: OrderbookSnapshot,
    trade_size_usd: float,
    is_buy: bool = True
) -> SlippageResult:
    """
    Calculate slippage by walking through orderbook levels.

    For a BUY order: we consume ASKs (we're buying the base asset)
    For a SELL order: we consume BIDs (we're selling the base asset)

    Args:
        orderbook: OrderbookSnapshot from fetch_orderbook
        trade_size_usd: Size of trade in USD
        is_buy: True for buying the base asset (e.g., buying MORPHO with USDT)

    Returns:
        SlippageResult with execution details
    """
    # Select the appropriate side of the orderbook
    levels = orderbook.asks if is_buy else orderbook.bids
    direction = "buy" if is_buy else "sell"

    if not levels:
        return SlippageResult(
            exchange=orderbook.exchange,
            trade_size_usd=trade_size_usd,
            direction=direction,
            mid_price=orderbook.mid_price,
            avg_execution_price=0,
            slippage_percentage=0,
            levels_consumed=0,
            fully_filled=False,
            total_filled_usd=0
        )

    # Walk through orderbook levels
    remaining_usd = trade_size_usd
    total_base_filled = 0  # Amount of base asset (MORPHO) acquired
    total_quote_spent = 0  # Amount of quote asset (USDT) spent
    levels_consumed = 0

    for price, size in levels:
        if remaining_usd <= 0:
            break

        levels_consumed += 1

        # Value of this level in USD (USDT)
        level_value_usd = price * size

        if level_value_usd >= remaining_usd:
            # Partial fill of this level
            fill_fraction = remaining_usd / level_value_usd
            base_filled = size * fill_fraction
            quote_spent = remaining_usd
            remaining_usd = 0
        else:
            # Full fill of this level
            base_filled = size
            quote_spent = level_value_usd
            remaining_usd -= level_value_usd

        total_base_filled += base_filled
        total_quote_spent += quote_spent

    # Calculate average execution price and slippage
    avg_execution_price = (
        total_quote_spent / total_base_filled
        if total_base_filled > 0 else 0
    )

    # Slippage = |avg_execution_price - mid_price| / mid_price * 100
    slippage_pct = (
        abs(avg_execution_price - orderbook.mid_price) / orderbook.mid_price * 100
        if orderbook.mid_price > 0 else 0
    )

    return SlippageResult(
        exchange=orderbook.exchange,
        trade_size_usd=trade_size_usd,
        direction=direction,
        mid_price=orderbook.mid_price,
        avg_execution_price=avg_execution_price,
        slippage_percentage=slippage_pct,
        levels_consumed=levels_consumed,
        fully_filled=(remaining_usd <= 0),
        total_filled_usd=total_quote_spent
    )


def batch_slippage_analysis(
    exchange: ccxt.Exchange,
    symbol: str,
    trade_sizes_usd: list[float],
    is_buy: bool = True
) -> list[SlippageResult]:
    """
    Calculate slippage for multiple trade sizes.

    Fetches orderbook once and calculates slippage for each size.

    Args:
        exchange: CCXT exchange instance
        symbol: Trading pair symbol
        trade_sizes_usd: List of trade sizes in USD
        is_buy: True for buy orders

    Returns:
        List of SlippageResult for each trade size
    """
    # Fetch orderbook with deep limit for large trades
    orderbook = fetch_orderbook(exchange, symbol, limit=500)

    results = []
    for size in trade_sizes_usd:
        result = calculate_cex_slippage(orderbook, size, is_buy)
        results.append(result)

    return results


def compare_venues(
    v4_results: list[dict[str, Any]],
    cex_results: list[SlippageResult],
    v4_fee_bps: float = 29.99,
    cex_fee_bps: float = 10.0,
    gas_cost_usd: float = 10.0
) -> list[dict[str, Any]]:
    """
    Compare execution quality between V4 and CEX.

    Args:
        v4_results: Results from V4 slippage calculation (from Q1)
        cex_results: Results from CEX slippage calculation
        v4_fee_bps: V4 pool fee in basis points
        cex_fee_bps: CEX trading fee in basis points
        gas_cost_usd: Estimated gas cost for V4 swap

    Returns:
        List of comparison dicts for each trade size
    """
    comparisons = []

    for v4, cex in zip(v4_results, cex_results):
        trade_size = cex.trade_size_usd

        # Calculate total costs
        v4_slippage_cost = trade_size * (v4['slippage_percentage'] / 100)
        v4_fee_cost = trade_size * (v4_fee_bps / 10000)
        v4_total_cost = v4_slippage_cost + v4_fee_cost + gas_cost_usd

        cex_slippage_cost = trade_size * (cex.slippage_percentage / 100)
        cex_fee_cost = trade_size * (cex_fee_bps / 10000)
        cex_total_cost = cex_slippage_cost + cex_fee_cost

        winner = "V4" if v4_total_cost < cex_total_cost else "CEX"

        comparisons.append({
            'trade_size_usd': trade_size,
            'v4_slippage_pct': v4['slippage_percentage'],
            'cex_slippage_pct': cex.slippage_percentage,
            'v4_total_cost_usd': v4_total_cost,
            'cex_total_cost_usd': cex_total_cost,
            'winner': winner,
            'savings_usd': abs(v4_total_cost - cex_total_cost)
        })

    return comparisons
