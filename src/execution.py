import logging

import backoff
from eth_typing import ChecksumAddress, HexStr
from sw_utils.typings import Bytes32
from web3 import Web3
from web3.types import Timestamp, Wei

from src.accounts import keeper_account
from src.clients import execution_client, ipfs_fetch_client
from src.config.settings import DEFAULT_RETRY_TIME, NETWORK_CONFIG
from src.contracts import keeper_contract, oracles_contract
from src.typings import RewardsRootUpdateParams

logger = logging.getLogger(__name__)

SECONDS_PER_MONTH: int = 2628000
APPROX_BLOCKS_PER_MONTH: int = int(SECONDS_PER_MONTH // NETWORK_CONFIG.SECONDS_PER_BLOCK)


@backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
async def get_oracles_threshold() -> int:
    return await oracles_contract.functions.requiredOracles().call()


@backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
async def get_keeper_rewards_nonce() -> int:
    return await keeper_contract.functions.rewardsNonce().call()


@backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
async def can_update_rewards() -> bool:
    """Checks whether keeper allows next update."""
    return await keeper_contract.functions.canUpdateRewards().call()


@backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
async def get_oracles() -> dict[ChecksumAddress, str]:
    events = await oracles_contract.events.ConfigUpdated.get_logs(from_block=0)
    if not events:
        raise ValueError('Failed to fetch IPFS hash of oracles config')

    # fetch IPFS record
    ipfs_hash = events[-1]['args']['configIpfsHash']
    config = await ipfs_fetch_client.fetch_json(ipfs_hash)

    oracles: dict[ChecksumAddress, str] = {}
    for oracle in config:
        oracles[Web3.to_checksum_address(oracle['address'])] = oracle['endpoint']

    return oracles


@backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
async def submit_vote(
        rewards_root: HexStr | Bytes32,
        update_timestamp: Timestamp,
        rewards_ipfs_hash: str,
        signatures: bytes,
) -> None:
    tx_data_params = RewardsRootUpdateParams(
        rewardsRoot=rewards_root,
        updateTimestamp=update_timestamp,
        rewardsIpfsHash=rewards_ipfs_hash,
        signatures=signatures,
    )
    tx = await keeper_contract.functions.setRewardsRoot(
        (
            tx_data_params.rewardsRoot,
            tx_data_params.updateTimestamp,
            tx_data_params.rewardsIpfsHash,
            tx_data_params.signatures,
        ),
    ).transact()  # type: ignore
    await execution_client.eth.wait_for_transaction_receipt(
        tx, timeout=DEFAULT_RETRY_TIME
    )  # type: ignore


@backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
async def get_keeper_balance() -> Wei:
    return await execution_client.eth.get_balance(keeper_account.address)  # type: ignore


async def check_keeper_balance() -> None:
    keeper_min_balance = NETWORK_CONFIG.KEEPER_MIN_BALANCE
    symbol = NETWORK_CONFIG.SYMBOL

    if keeper_min_balance <= 0:
        return

    if (await get_keeper_balance()) < keeper_min_balance:
        logger.warning(
            'Keeper balance is too low. At least %s %s is recommended.',
            Web3.from_wei(keeper_min_balance, 'ether'),
            symbol
        )
