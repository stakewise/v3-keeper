from decouple import Choices, Csv, config

from src.config.networks import ENABLED_NETWORKS, NETWORKS, NetworkConfig

# connections
EXECUTION_ENDPOINTS: list[str] = config('EXECUTION_ENDPOINTS', cast=Csv())
CONSENSUS_ENDPOINTS: list[str] = config('CONSENSUS_ENDPOINTS', cast=Csv())

# keeper
PRIVATE_KEY: str = config('PRIVATE_KEY')

# common
LOG_LEVEL: str = config('LOG_LEVEL', default='INFO')
WEB3_LOG_LEVEL: str = config('WEB3_LOG_LEVEL', default='INFO')

# network
NETWORK: str = config('NETWORK', cast=Choices(ENABLED_NETWORKS))
NETWORK_CONFIG: NetworkConfig = NETWORKS[NETWORK]

# IPFS fetch
IPFS_FETCH_ENDPOINTS = config(
    'IPFS_FETCH_ENDPOINTS',
    cast=Csv(),
    default='https://stakewise-v3.infura-ipfs.io/,' 'https://gateway.pinata.cloud,https://ipfs.io',
)
IPFS_CLIENT_TIMEOUT: int = config('IPFS_CLIENT_TIMEOUT', default=60, cast=int)
IPFS_CLIENT_RETRY_TIMEOUT: int = config('IPFS_CLIENT_RETRY_TIMEOUT', default=120, cast=int)

# IPFS upload
# Local
IPFS_LOCAL_CLIENT_ENDPOINT: str = config('IPFS_LOCAL_CLIENT_ENDPOINT', default='')

# infura
IPFS_INFURA_CLIENT_ENDPOINT: str = config(
    'IPFS_LOCAL_CLIENT_ENDPOINT', default='/dns/ipfs.infura.io/tcp/5001/https'
)
IPFS_INFURA_CLIENT_USERNAME: str = config('IPFS_INFURA_CLIENT_USERNAME', default='')
IPFS_INFURA_CLIENT_PASSWORD: str = config('IPFS_INFURA_CLIENT_PASSWORD', default='')

# pinata
IPFS_PINATA_ENDPOINT: str = 'https://api.pinata.cloud/pinning/pinJSONToIPFS'
IPFS_PINATA_API_KEY: str = config('IPFS_PINATA_API_KEY', default='')
IPFS_PINATA_SECRET_KEY: str = config('IPFS_PINATA_SECRET_KEY', default='')

# Filebase
IPFS_FILEBASE_API_TOKEN: str = config('IPFS_FILEBASE_API_TOKEN', default='')

# Quicknode
IPFS_QUICKNODE_API_TOKEN: str = config('IPFS_QUICKNODE_API_TOKEN', default='')


DEFAULT_RETRY_TIME = 30
VALIDATORS_FETCH_CHUNK_SIZE: int = config('VALIDATORS_FETCH_CHUNK_SIZE', default=100, cast=int)

# sentry config
SENTRY_DSN: str = config('SENTRY_DSN', default='')

# Prometheus
METRICS_HOST: str = config('METRICS_HOST', default='127.0.0.1')
METRICS_PORT: int = config('METRICS_PORT', default=9100, cast=int)

EXECUTION_TRANSACTION_TIMEOUT: int = config('EXECUTION_TRANSACTION_TIMEOUT', default=60, cast=int)

# ignore holesky broken vaults validators
IGNORED_EXIT_INDEXES: list[int] = config('IGNORED_EXIT_INDEXES', cast=Csv(int), default='')

# temporary check for genesis vault APY smoothing transactions
GENESIS_FEE_CHECK_ENABLED: bool = config('GENESIS_FEE_CHECK_ENABLED', default=False, cast=bool)
