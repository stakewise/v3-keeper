from typing import cast

from decouple import Choices, Csv, config

from src.config.networks import (
    ENABLED_NETWORKS,
    MAINNET,
    NETWORKS,
    PRICE_NETWORKS,
    SEPOLIA,
    NetworkConfig,
    PriceNetworkConfig,
)

# network
NETWORK: str = config('NETWORK', cast=Choices(ENABLED_NETWORKS))
NETWORK_CONFIG: NetworkConfig = NETWORKS[NETWORK]

# connections
EXECUTION_ENDPOINTS: list[str] = config('EXECUTION_ENDPOINTS', cast=Csv())
CONSENSUS_ENDPOINTS: list[str] = config('CONSENSUS_ENDPOINTS', cast=Csv())

# keeper
PRIVATE_KEY: str = config('PRIVATE_KEY')

SKIP_DISTRIBUTOR_REWARDS: bool = config('SKIP_DISTRIBUTOR_REWARDS', default=False, cast=bool)
SKIP_OSETH_PRICE_UPDATE: bool = config('SKIP_OSETH_PRICE_UPDATE', default=False, cast=bool)

# Oseth price
L2_EXECUTION_ENDPOINTS: list[str] = config('L2_EXECUTION_ENDPOINTS', cast=Csv())
PRICE_NETWORK_CONFIG = cast(PriceNetworkConfig, PRICE_NETWORKS[NETWORK])
OSETH_PRICE_SUPPORTED_NETWORKS = [MAINNET, SEPOLIA]

# LTV
SKIP_LTV_UPDATE: bool = config('SKIP_LTV_UPDATE', default=False, cast=bool)

# FORCE EXIT
SKIP_FORCE_EXITS: bool = config('SKIP_FORCE_EXITS', default=False, cast=bool)
LTV_PERCENT_DELTA: float = config('LTV_PERCENT_DELTA', default='0.0002', cast=float)

# graph
GRAPH_API_URL: str = config('GRAPH_API_URL')
GRAPH_API_TIMEOUT: int = config('GRAPH_API_TIMEOUT', default='10', cast=int)
GRAPH_API_RETRY_TIMEOUT: int = config('GRAPH_API_RETRY_TIMEOUT', default='60', cast=int)
GRAPH_PAGE_SIZE: int = config('GRAPH_PAGE_SIZE', default=100, cast=int)

# common
LOG_LEVEL: str = config('LOG_LEVEL', default='INFO')
WEB3_LOG_LEVEL: str = config('WEB3_LOG_LEVEL', default='INFO')


# IPFS fetch
IPFS_FETCH_ENDPOINTS = config(
    'IPFS_FETCH_ENDPOINTS',
    cast=Csv(),
    default=','.join(
        ['https://stakewise-v3.infura-ipfs.io/', 'https://gateway.pinata.cloud', 'https://ipfs.io']
    ),
)
IPFS_CLIENT_TIMEOUT: int = config('IPFS_CLIENT_TIMEOUT', default=60, cast=int)
IPFS_CLIENT_RETRY_TIMEOUT: int = config('IPFS_CLIENT_RETRY_TIMEOUT', default=120, cast=int)

DEFAULT_RETRY_TIME = 30
VALIDATORS_FETCH_CHUNK_SIZE: int = config('VALIDATORS_FETCH_CHUNK_SIZE', default=100, cast=int)

# sentry config
SENTRY_DSN: str = config('SENTRY_DSN', default='')

# Prometheus
METRICS_HOST: str = config('METRICS_HOST', default='127.0.0.1')
METRICS_PORT: int = config('METRICS_PORT', default=9100, cast=int)

EXECUTION_TRANSACTION_TIMEOUT: int = config('EXECUTION_TRANSACTION_TIMEOUT', default=60, cast=int)

ORACLE_TIMEOUT: int = config('ORACLE_TIMEOUT', default=60, cast=int)

# gas settings
MAX_FEE_PER_GAS_GWEI: int = config('MAX_FEE_PER_GAS_GWEI', default=100, cast=int)
PRIORITY_FEE_NUM_BLOCKS: int = config('PRIORITY_FEE_NUM_BLOCKS', default=10, cast=int)
PRIORITY_FEE_PERCENTILE: float = config('PRIORITY_FEE_PERCENTILE', default=80.0, cast=float)
ATTEMPTS_WITH_DEFAULT_GAS: int = config('ATTEMPTS_WITH_DEFAULT_GAS', default=5, cast=int)
