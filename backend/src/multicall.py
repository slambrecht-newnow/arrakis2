"""
Multicall3 helper for batching multiple contract calls into a single RPC request.

Uses the Multicall3 contract deployed at a standard address on Ethereum mainnet
to aggregate multiple view/pure function calls into one eth_call.
"""

from eth_abi.abi import encode, decode
from web3 import Web3
from web3.contract import Contract


# Multicall3 contract address (same on all major EVM chains)
MULTICALL3_ADDRESS = "0xcA11bde05977b3631167028862bE2a173976CA11"

# Multicall3 ABI (minimal - only aggregate3)
MULTICALL3_ABI = [
    {
        "name": "aggregate3",
        "type": "function",
        "stateMutability": "payable",
        "inputs": [
            {
                "name": "calls",
                "type": "tuple[]",
                "components": [
                    {"name": "target", "type": "address"},
                    {"name": "allowFailure", "type": "bool"},
                    {"name": "callData", "type": "bytes"},
                ],
            }
        ],
        "outputs": [
            {
                "name": "returnData",
                "type": "tuple[]",
                "components": [
                    {"name": "success", "type": "bool"},
                    {"name": "returnData", "type": "bytes"},
                ],
            }
        ],
    }
]


def create_multicall3(w3: Web3) -> Contract:
    """Create a Multicall3 contract instance."""
    return w3.eth.contract(
        address=Web3.to_checksum_address(MULTICALL3_ADDRESS),
        abi=MULTICALL3_ABI
    )


def encode_call(target: str, calldata: bytes) -> tuple[str, bool, bytes]:
    """
    Encode a single call for Multicall3.aggregate3.

    Args:
        target: Contract address to call
        calldata: Encoded function call data

    Returns:
        Tuple of (target, allowFailure, callData) for aggregate3
    """
    return (Web3.to_checksum_address(target), True, calldata)


def execute_multicall(
    w3: Web3,
    calls: list[tuple[str, bool, bytes]]
) -> list[tuple[bool, bytes]]:
    """
    Execute multiple calls via Multicall3.

    Args:
        w3: Web3 instance
        calls: List of (target, allowFailure, callData) tuples

    Returns:
        List of (success, returnData) tuples
    """
    multicall = create_multicall3(w3)
    results = multicall.functions.aggregate3(calls).call()
    return [(r[0], r[1]) for r in results]


def build_get_slot0_call(stateview_address: str, pool_id: bytes) -> tuple[str, bool, bytes]:
    """Build a getSlot0 call for multicall."""
    selector = bytes.fromhex("c815641c")
    calldata = selector + encode(["bytes32"], [pool_id])
    return encode_call(stateview_address, calldata)


def build_get_liquidity_call(stateview_address: str, pool_id: bytes) -> tuple[str, bool, bytes]:
    """Build a getLiquidity call for multicall."""
    selector = bytes.fromhex("fa6793d5")
    calldata = selector + encode(["bytes32"], [pool_id])
    return encode_call(stateview_address, calldata)


def build_get_tick_bitmap_call(
    stateview_address: str,
    pool_id: bytes,
    word_pos: int
) -> tuple[str, bool, bytes]:
    """Build a getTickBitmap call for multicall."""
    selector = bytes.fromhex("1c7ccb4c")
    calldata = selector + encode(["bytes32", "int16"], [pool_id, word_pos])
    return encode_call(stateview_address, calldata)


def build_get_tick_liquidity_call(
    stateview_address: str,
    pool_id: bytes,
    tick: int
) -> tuple[str, bool, bytes]:
    """Build a getTickLiquidity call for multicall."""
    selector = bytes.fromhex("caedab54")
    calldata = selector + encode(["bytes32", "int24"], [pool_id, tick])
    return encode_call(stateview_address, calldata)


def decode_slot0_result(data: bytes) -> tuple[int, int, int, int]:
    """Decode getSlot0 return data."""
    result = decode(["uint160", "int24", "uint24", "uint24"], data)
    return (result[0], result[1], result[2], result[3])


def decode_liquidity_result(data: bytes) -> int:
    """Decode getLiquidity return data."""
    result = decode(["uint128"], data)
    return result[0]


def decode_tick_bitmap_result(data: bytes) -> int:
    """Decode getTickBitmap return data."""
    result = decode(["uint256"], data)
    return result[0]


def decode_tick_liquidity_result(data: bytes) -> tuple[int, int]:
    """Decode getTickLiquidity return data."""
    result = decode(["uint128", "int128"], data)
    return (result[0], result[1])


# ─── IXS Migration: V2 Pair, Vault, Chainlink ───


def build_get_reserves_call(pair_address: str) -> tuple[str, bool, bytes]:
    """Build a UniV2 getReserves call for multicall."""
    selector = bytes.fromhex("0902f1ac")  # getReserves()
    return encode_call(pair_address, selector)


def decode_get_reserves_result(data: bytes) -> tuple[int, int, int]:
    """Decode UniV2 getReserves return data."""
    result = decode(["uint112", "uint112", "uint32"], data)
    return (result[0], result[1], result[2])


def build_total_underlying_call(vault_address: str) -> tuple[str, bool, bytes]:
    """Build an Arrakis vault totalUnderlying call for multicall."""
    selector = bytes.fromhex("c70920bc")  # totalUnderlying()
    return encode_call(vault_address, selector)


def decode_total_underlying_result(data: bytes) -> tuple[int, int]:
    """Decode Arrakis vault totalUnderlying return data."""
    result = decode(["uint256", "uint256"], data)
    return (result[0], result[1])


def build_chainlink_latest_round_call(feed_address: str) -> tuple[str, bool, bytes]:
    """Build a Chainlink latestRoundData call for multicall."""
    selector = bytes.fromhex("feaf968c")  # latestRoundData()
    return encode_call(feed_address, selector)


def decode_chainlink_latest_round_result(data: bytes) -> tuple[int, int, int, int, int]:
    """Decode Chainlink latestRoundData return data."""
    result = decode(["uint80", "int256", "uint256", "uint256", "uint80"], data)
    return (result[0], result[1], result[2], result[3], result[4])
