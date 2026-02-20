"""
Block sampling and timestamp utilities for historical analysis.

Generates evenly-spaced block samples and converts between blocks,
timestamps, and human-readable dates.
"""

from datetime import datetime, timezone

from web3 import Web3

from .config import BLOCKS_PER_DAY


def generate_daily_block_samples(start_block: int, end_block: int) -> list[int]:
    """Generate block numbers at ~daily intervals (~7200 blocks apart)."""
    blocks = []
    current = start_block
    while current <= end_block:
        blocks.append(current)
        current += BLOCKS_PER_DAY
    if blocks[-1] != end_block:
        blocks.append(end_block)
    return blocks


def blocks_to_timestamps(w3: Web3, blocks: list[int]) -> list[int]:
    """Convert block numbers to unix timestamps via RPC."""
    timestamps = []
    for block_num in blocks:
        block_data = w3.eth.get_block(block_num)
        ts = block_data.get("timestamp", 0)
        timestamps.append(int(ts))
    return timestamps


def timestamps_to_dates(timestamps: list[int]) -> list[str]:
    """Convert unix timestamps to 'YYYY-MM-DD' strings."""
    return [
        datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        for ts in timestamps
    ]


def get_latest_block(w3: Web3) -> int:
    """Get the latest block number."""
    return w3.eth.block_number
