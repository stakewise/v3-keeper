from sw_utils import GasManager, get_consensus_client, get_execution_client
from sw_utils.graph.client import GraphClient
from sw_utils.ipfs import IpfsFetchClient
from web3 import AsyncWeb3, Web3
from web3.middleware import SignAndSendRawMiddlewareBuilder

from src.common.accounts import keeper_account
from src.config import settings
from src.config.settings import (
    MAX_FEE_PER_GAS_GWEI,
    PRIORITY_FEE_NUM_BLOCKS,
    PRIORITY_FEE_PERCENTILE,
)


def build_execution_client() -> AsyncWeb3:
    w3 = get_execution_client(
        settings.EXECUTION_ENDPOINTS,
        retry_timeout=settings.DEFAULT_RETRY_TIME,
    )

    return w3


async def setup_execution_client(w3: AsyncWeb3) -> None:
    """Setup keeper private key"""
    w3.middleware_onion.inject(
        # pylint: disable-next=no-value-for-parameter
        SignAndSendRawMiddlewareBuilder.build(keeper_account),
        layer=0,
    )
    w3.eth.default_account = keeper_account.address


async def close_clients() -> None:
    await consensus_client.disconnect()
    await execution_client.provider.disconnect()


def build_gas_manager() -> GasManager:
    min_effective_priority_fee_per_gas = settings.NETWORK_CONFIG.MIN_EFFECTIVE_PRIORITY_FEE_PER_GAS
    return GasManager(
        execution_client=execution_client,
        max_fee_per_gas=Web3.to_wei(MAX_FEE_PER_GAS_GWEI, 'gwei'),
        priority_fee_num_blocks=PRIORITY_FEE_NUM_BLOCKS,
        priority_fee_percentile=PRIORITY_FEE_PERCENTILE,
        min_effective_priority_fee_per_gas=min_effective_priority_fee_per_gas,
    )


graph_client = GraphClient(
    endpoint=settings.GRAPH_API_URL,
    request_timeout=settings.GRAPH_API_TIMEOUT,
    retry_timeout=settings.GRAPH_API_RETRY_TIMEOUT,
    page_size=settings.GRAPH_PAGE_SIZE,
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
