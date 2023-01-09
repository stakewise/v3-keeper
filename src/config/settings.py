from decouple import Choices, Csv, config

from src.config.networks import GOERLI, NETWORKS, NetworkConfig

# connections
EXECUTION_ENDPOINT = config('EXECUTION_ENDPOINT')
CONSENSUS_ENDPOINT = config('CONSENSUS_ENDPOINT')

# ENS
# used to fetch oracles config from ENS when running on Gnosis
MAINNET_EXECUTION_ENDPOINT = config('MAINNET_EXECUTION_ENDPOINT', default='')
DAO_ENS_NAME = config('DAO_ENS_NAME', default='stakewise.eth')

# keeper
PRIVATE_KEY = config('PRIVATE_KEY')

# common
LOG_LEVEL = config('LOG_LEVEL', default='INFO')

# network
NETWORK = config('NETWORK', cast=Choices([GOERLI]))
NETWORK_CONFIG: NetworkConfig = NETWORKS[NETWORK]

# local IPFS
IPFS_LOCAL_CLIENT_ENDPOINT = config('IPFS_LOCAL_CLIENT_ENDPOINT')

# remote IPFS
IPFS_FETCH_ENDPOINTS = config(
    'IPFS_FETCH_ENDPOINTS',
    cast=Csv(),
    default='https://stakewise.infura-ipfs.io/,'
    'http://cloudflare-ipfs.com,'
    'https://gateway.pinata.cloud,https://ipfs.io',
)

# infura
IPFS_INFURA_CLIENT_ENDPOINT = '/dns/ipfs.infura.io/tcp/5001/https'
IPFS_INFURA_CLIENT_USERNAME = config('IPFS_INFURA_CLIENT_USERNAME', default='')
IPFS_INFURA_CLIENT_PASSWORD = config('IPFS_INFURA_CLIENT_PASSWORD', default='')

# pinata
IPFS_PINATA_API_KEY = config('IPFS_PINATA_API_KEY', default='')
IPFS_PINATA_SECRET_KEY = config('IPFS_PINATA_SECRET_KEY', default='')

# sentry config
SENTRY_DSN = config('SENTRY_DSN', default='')
