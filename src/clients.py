from sw_utils import GasManager, get_consensus_client, get_execution_client
from sw_utils.ipfs import IpfsFetchClient
from web3 import AsyncWeb3
from web3.middleware.signing import async_construct_sign_and_send_raw_middleware

from src.accounts import keeper_account
from src.config import settings
from src.config.settings import (
    MAX_FEE_PER_GAS_GWEI,
    PRIORITY_FEE_NUM_BLOCKS,
    PRIORITY_FEE_PERCENTILE,
)


def build_execution_client() -> AsyncWeb3:
    w3 = get_execution_client(
        settings.EXECUTION_ENDPOINTS,
        settings.NETWORK_CONFIG.IS_POA,
        retry_timeout=settings.DEFAULT_RETRY_TIME,
    )

    return w3


async def setup_execution_client(w3: AsyncWeb3) -> None:
    """Setup keeper private key"""
    w3.middleware_onion.add(await async_construct_sign_and_send_raw_middleware(keeper_account))
    w3.eth.default_account = keeper_account.address


def build_gas_manager() -> GasManager:
    return GasManager(
        execution_client=execution_client,
        max_fee_per_gas_gwei=MAX_FEE_PER_GAS_GWEI,
        priority_fee_num_blocks=PRIORITY_FEE_NUM_BLOCKS,
        priority_fee_percentile=PRIORITY_FEE_PERCENTILE,
    )


execution_client = build_execution_client()
consensus_client = get_consensus_client(
    settings.CONSENSUS_ENDPOINTS, retry_timeout=settings.DEFAULT_RETRY_TIME
)
gas_manager = build_gas_manager()


ipfs_fetch_client = IpfsFetchClient(
    settings.IPFS_FETCH_ENDPOINTS,
    timeout=settings.IPFS_CLIENT_TIMEOUT,
    retry_timeout=settings.IPFS_CLIENT_RETRY_TIMEOUT,
)
