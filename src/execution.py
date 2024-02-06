import logging

from sw_utils import ProtocolConfig, build_protocol_config
from web3 import Web3
from web3.types import Wei

from src.accounts import keeper_account
from src.clients import execution_client, ipfs_fetch_client
from src.config.settings import DEFAULT_RETRY_TIME, NETWORK_CONFIG
from src.contracts import keeper_contract
from src.typings import RewardVoteBody

logger = logging.getLogger(__name__)

SECONDS_PER_MONTH: int = 2628000
APPROX_BLOCKS_PER_MONTH: int = int(SECONDS_PER_MONTH // NETWORK_CONFIG.SECONDS_PER_BLOCK)


async def get_protocol_config() -> ProtocolConfig:
    events = await keeper_contract.get_config_update_events()
    if not events:
        raise ValueError('Failed to fetch IPFS hash of oracles config')

    # fetch IPFS record
    ipfs_hash = events[-1]['args']['configIpfsHash']
    config = await ipfs_fetch_client.fetch_json(ipfs_hash)

    rewards_threshold = await keeper_contract.get_rewards_threshold()

    return build_protocol_config(
        config_data=config,
        rewards_threshold=rewards_threshold,
    )


async def get_keeper_balance() -> Wei:
    return await execution_client.eth.get_balance(keeper_account.address)


async def check_keeper_balance() -> None:
    keeper_min_balance = NETWORK_CONFIG.KEEPER_MIN_BALANCE
    symbol = NETWORK_CONFIG.SYMBOL

    if keeper_min_balance <= 0:
        return

    if (await get_keeper_balance()) < keeper_min_balance:
        logger.warning(
            'Keeper balance is too low. At least %s %s is recommended.',
            Web3.from_wei(keeper_min_balance, 'ether'),
            symbol,
        )


async def submit_vote(
    vote: RewardVoteBody,
    signatures: bytes,
) -> None:
    tx = await keeper_contract.update_rewards(vote, signatures)
    await execution_client.eth.wait_for_transaction_receipt(tx, timeout=DEFAULT_RETRY_TIME)
    logger.info('Rewards has been successfully updated. Tx hash: %s', Web3.to_hex(tx))
