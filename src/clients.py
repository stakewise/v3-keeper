from sw_utils import (
    IpfsFetchClient,
    construct_async_sign_and_send_raw_middleware,
    get_consensus_client,
    get_execution_client,
)
from web3 import AsyncWeb3

from src.accounts import keeper_account
from src.config.settings import (
    CONSENSUS_ENDPOINTS,
    EXECUTION_ENDPOINTS,
    IPFS_FETCH_ENDPOINTS,
    NETWORK_CONFIG,
)


def build_execution_client() -> AsyncWeb3:
    w3 = get_execution_client(EXECUTION_ENDPOINTS, NETWORK_CONFIG.IS_POA)
    w3.middleware_onion.add(construct_async_sign_and_send_raw_middleware(keeper_account))
    w3.eth.default_account = keeper_account.address
    return w3


execution_client = build_execution_client()
consensus_client = get_consensus_client(CONSENSUS_ENDPOINTS)
ipfs_fetch_client = IpfsFetchClient(IPFS_FETCH_ENDPOINTS)
