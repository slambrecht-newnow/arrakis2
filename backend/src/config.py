"""
Configuration constants for Uniswap V4 pool analysis.

Centralizes all contract addresses, pool parameters, and API endpoints.
"""

# ─── Shared Contract Addresses (Ethereum Mainnet) ───
STATE_VIEW = "0x7ffe42c4a5deea5b0fec41c94c136cf115597227"
QUOTER = "0x52f0e24d1c21c8a0cb1e5a5dd6198556bd9e1203"

# ─── Challenge 1: ETH/MORPHO ───

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

# ─── Challenge 2: IXS/ETH Migration ───

# Token Addresses
IXS = "0x73d7c860998CA3c01Ce8c808F5577d94d545d1b4"
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

# UniswapV2 Pair (IXS/WETH)
UNIV2_PAIR = "0xC09bf2B1Bc8725903C509e8CAeef9190857215A8"

# UniswapV4 Pool (IXS/ETH via Arrakis)
IXS_POOL_ID = "0xd54a5e98dc3d0a90a058d4e46b2db9e7d92dbf50598833035e1f27eac4f23a4f"
IXS_POOL_ID_BYTES = bytes.fromhex(
    "d54a5e98dc3d0a90a058d4e46b2db9e7d92dbf50598833035e1f27eac4f23a4f"
)
# Discovered and verified via poolKey hash: keccak256(encode(c0, c1, fee, ts, hooks)) == pool_id
IXS_FEE = 7000  # 0.7% (lpFee in V4 ppm: 7000/1_000_000 = 0.7%)
IXS_TICK_SPACING = 50
IXS_HOOKS = "0x0000000000000000000000000000000000000000"

# Arrakis Vault
ARRAKIS_VAULT = "0x90bde935ce7feb6636afd5a1a0340af45eeae600"
ARRAKIS_MODULE = "0xC56d93dD1D48f93814901cF685C3cD0eAc0E849D"

# Chainlink Price Feeds
CHAINLINK_ETH_USD = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"

# Sampling parameters
BLOCKS_PER_DAY = 7200  # ~12s block time

# ─── API Endpoints ───
UNISWAP_GRAPHQL_URL = "https://interface.gateway.uniswap.org/v1/graphql"
