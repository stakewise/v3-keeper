from decouple import Choices, Csv, config

from src.config.networks import HOLESKY, MAINNET, NETWORKS, NetworkConfig

# connections
EXECUTION_ENDPOINTS = config('EXECUTION_ENDPOINTS', cast=Csv())
CONSENSUS_ENDPOINTS = config('CONSENSUS_ENDPOINTS', cast=Csv())

# keeper
PRIVATE_KEY = config('PRIVATE_KEY')

# common
LOG_LEVEL = config('LOG_LEVEL', default='INFO')

# network
NETWORK = config('NETWORK', cast=Choices([MAINNET, HOLESKY]))
NETWORK_CONFIG: NetworkConfig = NETWORKS[NETWORK]

# remote IPFS
IPFS_FETCH_ENDPOINTS = config(
    'IPFS_FETCH_ENDPOINTS',
    cast=Csv(),
    default='https://stakewise-v3.infura-ipfs.io/,'
    'http://cloudflare-ipfs.com,'
    'https://gateway.pinata.cloud,https://ipfs.io',
)
IPFS_CLIENT_TIMEOUT: int = config('IPFS_CLIENT_TIMEOUT', default=60, cast=int)
IPFS_CLIENT_RETRY_TIMEOUT: int = config('IPFS_CLIENT_RETRY_TIMEOUT', default=120, cast=int)

DEFAULT_RETRY_TIME = 30
VALIDATORS_FETCH_CHUNK_SIZE = config('VALIDATORS_FETCH_CHUNK_SIZE', default=100, cast=int)

# sentry config
SENTRY_DSN = config('SENTRY_DSN', default='')

# Prometheus
METRICS_HOST = config('METRICS_HOST', default='127.0.0.1')
METRICS_PORT = config('METRICS_PORT', default=9100)
