from decouple import Choices, Csv, config

from src.config.networks import GOERLI, NETWORKS, NetworkConfig

# connections
EXECUTION_ENDPOINT = config('EXECUTION_ENDPOINT')
CONSENSUS_ENDPOINT = config('CONSENSUS_ENDPOINT')

# keeper
PRIVATE_KEY = config('PRIVATE_KEY')

# common
LOG_LEVEL = config('LOG_LEVEL', default='INFO')

# network
NETWORK = config('NETWORK', cast=Choices([GOERLI]))
NETWORK_CONFIG: NetworkConfig = NETWORKS[NETWORK]

# remote IPFS
IPFS_FETCH_ENDPOINTS = config(
    'IPFS_FETCH_ENDPOINTS',
    cast=Csv(),
    default='https://stakewise.infura-ipfs.io/,'
    'http://cloudflare-ipfs.com,'
    'https://gateway.pinata.cloud,https://ipfs.io',
)

DEFAULT_RETRY_TIME = 30
VALIDATORS_FETCH_CHUNK_SIZE = config('VALIDATORS_FETCH_CHUNK_SIZE', default=100, cast=int)

# sentry config
SENTRY_DSN = config('SENTRY_DSN', default='')
