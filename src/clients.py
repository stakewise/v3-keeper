from sw_utils import GasManager, get_consensus_client, get_execution_client
from sw_utils.ipfs import (
    BasePinClient,
    BaseUploadClient,
    FilebasePinClient,
    IpfsFetchClient,
    IpfsMultiUploadClient,
    IpfsUploadClient,
    PinataUploadClient,
    QuicknodePinClient,
)
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


def build_ipfs_upload_client(include_pin_clients: bool = True) -> IpfsMultiUploadClient:
    upload_clients: list[BaseUploadClient] = []

    if settings.IPFS_LOCAL_CLIENT_ENDPOINT:
        upload_clients.append(IpfsUploadClient(settings.IPFS_LOCAL_CLIENT_ENDPOINT))

    if settings.IPFS_INFURA_CLIENT_USERNAME and settings.IPFS_INFURA_CLIENT_PASSWORD:
        ipfs_client = IpfsUploadClient(
            settings.IPFS_INFURA_CLIENT_ENDPOINT,
            settings.IPFS_INFURA_CLIENT_USERNAME,
            settings.IPFS_INFURA_CLIENT_PASSWORD,
        )
        upload_clients.append(ipfs_client)

    if settings.IPFS_PINATA_API_KEY and settings.IPFS_PINATA_SECRET_KEY:
        pinata_client = PinataUploadClient(
            settings.IPFS_PINATA_API_KEY, settings.IPFS_PINATA_SECRET_KEY
        )
        upload_clients.append(pinata_client)

    if not upload_clients:
        raise ValueError(
            'No IPFS upload clients settings. '
            'Please provide IPFS_LOCAL_CLIENT_ENDPOINT or third party IPFS services settings.'
        )

    pin_clients: list[BasePinClient] = []

    if include_pin_clients:
        if settings.IPFS_FILEBASE_API_TOKEN:
            filebase_pin_client = FilebasePinClient(api_token=settings.IPFS_FILEBASE_API_TOKEN)
            pin_clients.append(filebase_pin_client)

        if settings.IPFS_QUICKNODE_API_TOKEN:
            quicknode_pin_client = QuicknodePinClient(api_token=settings.IPFS_QUICKNODE_API_TOKEN)
            pin_clients.append(quicknode_pin_client)

    return IpfsMultiUploadClient(upload_clients=upload_clients, pin_clients=pin_clients)


ipfs_upload_client = build_ipfs_upload_client()

ipfs_fetch_client = IpfsFetchClient(
    settings.IPFS_FETCH_ENDPOINTS,
    timeout=settings.IPFS_CLIENT_TIMEOUT,
    retry_timeout=settings.IPFS_CLIENT_RETRY_TIMEOUT,
)
