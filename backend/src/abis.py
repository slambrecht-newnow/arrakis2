"""
Contract ABIs for Uniswap V4 pool interactions.

Contains minimal ABIs for StateView, Quoter, and ERC20 contracts.
"""

# StateView ABI (minimal - for basic pool queries)
STATEVIEW_ABI = [
    {
        "name": "getSlot0",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "poolId", "type": "bytes32"}],
        "outputs": [
            {"name": "sqrtPriceX96", "type": "uint160"},
            {"name": "tick", "type": "int24"},
            {"name": "protocolFee", "type": "uint24"},
            {"name": "lpFee", "type": "uint24"},
        ],
    }
]


# StateView ABI (extended - for liquidity distribution analysis)
STATEVIEW_ABI_EXTENDED = [
    {
        "name": "getSlot0",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "poolId", "type": "bytes32"}],
        "outputs": [
            {"name": "sqrtPriceX96", "type": "uint160"},
            {"name": "tick", "type": "int24"},
            {"name": "protocolFee", "type": "uint24"},
            {"name": "lpFee", "type": "uint24"},
        ],
    },
    {
        "name": "getLiquidity",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "poolId", "type": "bytes32"}],
        "outputs": [{"name": "liquidity", "type": "uint128"}],
    },
    {
        "name": "getTickBitmap",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "poolId", "type": "bytes32"},
            {"name": "tick", "type": "int16"},
        ],
        "outputs": [{"name": "tickBitmap", "type": "uint256"}],
    },
    {
        "name": "getTickLiquidity",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "poolId", "type": "bytes32"},
            {"name": "tick", "type": "int24"},
        ],
        "outputs": [
            {"name": "liquidityGross", "type": "uint128"},
            {"name": "liquidityNet", "type": "int128"},
        ],
    },
]


# Quoter ABI (for swap simulation)
QUOTER_ABI = [
    {
        "name": "quoteExactInputSingle",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {
                "name": "params",
                "type": "tuple",
                "components": [
                    {
                        "name": "poolKey",
                        "type": "tuple",
                        "components": [
                            {"name": "currency0", "type": "address"},
                            {"name": "currency1", "type": "address"},
                            {"name": "fee", "type": "uint24"},
                            {"name": "tickSpacing", "type": "int24"},
                            {"name": "hooks", "type": "address"},
                        ],
                    },
                    {"name": "zeroForOne", "type": "bool"},
                    {"name": "exactAmount", "type": "uint128"},
                    {"name": "hookData", "type": "bytes"},
                ],
            }
        ],
        "outputs": [
            {"name": "amountOut", "type": "uint256"},
            {"name": "gasEstimate", "type": "uint256"},
        ],
    }
]
