"""
Migration detection for IXS/ETH liquidity migration from V2 to V4.

Uses binary search to find the block where:
1. V4 pool was first initialized (non-zero sqrtPriceX96)
2. Arrakis vault received its first deposit (non-zero totalUnderlying)
3. V2 liquidity dropped significantly
"""

from web3 import Web3
from web3.contract import Contract


def find_v4_pool_creation_block(
    stateview: Contract,
    pool_id: bytes,
    search_start: int,
    search_end: int,
) -> int:
    """Binary search for the first block with non-zero sqrtPriceX96 in V4."""
    low, high = search_start, search_end

    while low < high:
        mid = (low + high) // 2
        try:
            sqrt_price, _, _, _ = stateview.functions.getSlot0(pool_id).call(
                block_identifier=mid
            )
            if sqrt_price > 0:
                high = mid
            else:
                low = mid + 1
        except Exception:
            low = mid + 1

    return low


def find_vault_first_deposit_block(
    vault: Contract,
    search_start: int,
    search_end: int,
) -> int:
    """Binary search for the first block with non-zero totalUnderlying in vault."""
    low, high = search_start, search_end

    while low < high:
        mid = (low + high) // 2
        try:
            amount0, amount1 = vault.functions.totalUnderlying().call(
                block_identifier=mid
            )
            if amount0 > 0 or amount1 > 0:
                high = mid
            else:
                low = mid + 1
        except Exception:
            low = mid + 1

    return low


def detect_v2_liquidity_drop(
    pair: Contract,
    blocks: list[int],
    threshold_pct: float = 50.0,
) -> int | None:
    """
    Sample V2 reserves at given blocks and find the block where
    reserves drop by more than threshold_pct from the previous sample.
    """
    prev_total = None
    for block in blocks:
        try:
            r0, r1, _ = pair.functions.getReserves().call(block_identifier=block)
            total = r0 + r1
            if prev_total is not None and prev_total > 0:
                drop_pct = (prev_total - total) / prev_total * 100
                if drop_pct > threshold_pct:
                    return block
            prev_total = total
        except Exception:
            continue
    return None


def get_migration_info(
    w3: Web3,
    stateview: Contract,
    pool_id: bytes,
    vault: Contract,
    pair: Contract,
    search_start: int,
    search_end: int,
) -> dict[str, int | None]:
    """
    Combine all three migration signals into a summary.

    Returns dict with keys: v4_creation_block, vault_deposit_block, v2_drop_block.
    The vault_deposit_block is the definitive migration moment.
    """
    from .block_utils import generate_daily_block_samples

    v4_block = find_v4_pool_creation_block(
        stateview, pool_id, search_start, search_end
    )
    vault_block = find_vault_first_deposit_block(vault, search_start, search_end)

    # Sample V2 reserves daily around the migration window
    sample_start = max(search_start, vault_block - 7200 * 30)  # 30 days before
    sample_end = min(search_end, vault_block + 7200 * 30)
    sample_blocks = generate_daily_block_samples(sample_start, sample_end)
    v2_drop = detect_v2_liquidity_drop(pair, sample_blocks)

    return {
        "v4_creation_block": v4_block,
        "vault_deposit_block": vault_block,
        "v2_drop_block": v2_drop,
    }
