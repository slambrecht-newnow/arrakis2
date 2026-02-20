"""
Configuration constants for Uniswap V4 pool analysis.

Centralizes all contract addresses, pool parameters, and API endpoints.
"""

# Contract Addresses (Ethereum Mainnet)
STATE_VIEW = "0x7ffe42c4a5deea5b0fec41c94c136cf115597227"
QUOTER = "0x52f0e24d1c21c8a0cb1e5a5dd6198556bd9e1203"

# Token Addresses
ETH = "0x0000000000000000000000000000000000000000"  # Native ETH in V4
MORPHO = "0x58D97B57BB95320F9a05dC918Aef65434969c2B2"

# ETH/MORPHO Pool Configuration
POOL_ID = "0xd9f5cbaeb88b7f0d9b0549257ddd4c46f984e2fc4bccf056cc254b9fe3417fff"
POOL_ID_BYTES = bytes.fromhex(
    "d9f5cbaeb88b7f0d9b0549257ddd4c46f984e2fc4bccf056cc254b9fe3417fff"
)
TICK_SPACING = 60
FEE = 2999  # 0.2999% (in basis points * 100)
HOOKS = "0x0000000000000000000000000000000000000000"

# API Endpoints
UNISWAP_GRAPHQL_URL = "https://interface.gateway.uniswap.org/v1/graphql"
