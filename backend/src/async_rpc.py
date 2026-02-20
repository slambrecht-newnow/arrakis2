"""
Async RPC client for parallel Ethereum calls.

Uses aiohttp for efficient concurrent HTTP requests to the RPC provider.
"""

import asyncio
from typing import Any

import aiohttp


async def async_eth_call(
    session: aiohttp.ClientSession,
    rpc_url: str,
    to: str,
    data: str,
    request_id: int = 1
) -> dict[str, Any]:
    """
    Execute an async eth_call.

    Args:
        session: aiohttp session for connection pooling
        rpc_url: RPC endpoint URL
        to: Contract address
        data: Encoded call data (hex string with 0x prefix)
        request_id: JSON-RPC request ID

    Returns:
        JSON-RPC response dict
    """
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"to": to, "data": data}, "latest"],
        "id": request_id
    }

    async with session.post(rpc_url, json=payload) as response:
        return await response.json()


async def gather_eth_calls(
    rpc_url: str,
    calls: list[tuple[str, str]],
    timeout: float = 30.0
) -> list[dict[str, Any]]:
    """
    Execute multiple eth_calls in parallel.

    Args:
        rpc_url: RPC endpoint URL
        calls: List of (contract_address, call_data_hex) tuples
        timeout: Request timeout in seconds

    Returns:
        List of JSON-RPC response dicts in same order as calls
    """
    connector = aiohttp.TCPConnector(limit=100)
    timeout_config = aiohttp.ClientTimeout(total=timeout)

    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout_config
    ) as session:
        tasks = [
            async_eth_call(session, rpc_url, to, data, i)
            for i, (to, data) in enumerate(calls)
        ]
        return await asyncio.gather(*tasks)


async def async_batch_rpc(
    rpc_url: str,
    requests: list[dict[str, Any]],
    timeout: float = 30.0
) -> list[dict[str, Any]]:
    """
    Send a batch JSON-RPC request (multiple requests in single HTTP call).

    Args:
        rpc_url: RPC endpoint URL
        requests: List of JSON-RPC request objects
        timeout: Request timeout in seconds

    Returns:
        List of JSON-RPC response dicts
    """
    timeout_config = aiohttp.ClientTimeout(total=timeout)

    async with aiohttp.ClientSession(timeout=timeout_config) as session:
        async with session.post(rpc_url, json=requests) as response:
            results = await response.json()
            # Sort by id to ensure correct order
            if isinstance(results, list):
                results.sort(key=lambda r: r.get("id", 0))
            return results


def run_async(coro: Any) -> Any:
    """Run an async coroutine from sync code."""
    try:
        loop = asyncio.get_running_loop()
        # If we're already in an async context, we can't use run()
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(coro)
    except RuntimeError:
        # No running loop, safe to use asyncio.run()
        return asyncio.run(coro)
