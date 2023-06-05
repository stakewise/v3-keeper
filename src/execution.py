import logging

import backoff
from web3 import Web3
from web3.types import Wei

from src.accounts import keeper_account
from src.clients import execution_client, ipfs_fetch_client
from src.config.settings import DEFAULT_RETRY_TIME, NETWORK_CONFIG
from src.contracts import keeper_contract, oracles_contract
from src.typings import Oracle, RewardVoteBody

logger = logging.getLogger(__name__)

SECONDS_PER_MONTH: int = 2628000
APPROX_BLOCKS_PER_MONTH: int = int(SECONDS_PER_MONTH // NETWORK_CONFIG.SECONDS_PER_BLOCK)


@backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
async def get_oracles_threshold() -> int:
    return await oracles_contract.functions.requiredOracles().call()


@backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
async def get_oracles() -> list[Oracle]:
    events = await oracles_contract.events.ConfigUpdated.get_logs(
        from_block=NETWORK_CONFIG.ORACLES_GENESIS_BLOCK
    )
    if not events:
        raise ValueError('Failed to fetch IPFS hash of oracles config')

    # fetch IPFS record
    ipfs_hash = events[-1]['args']['configIpfsHash']
    config = await ipfs_fetch_client.fetch_json(ipfs_hash)

    oracles = []
    for index, oracle_config in enumerate(config['oracles']):
        oracle = Oracle(
            address=Web3.to_checksum_address(oracle_config['address']),
            endpoint=oracle_config['endpoint'],
            index=index,
        )
        oracles.append(oracle)

    return oracles


@backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
async def submit_vote(
        vote: RewardVoteBody,
        signatures: bytes,
) -> None:
    tx = await keeper_contract.update_rewards(
        vote, signatures
    )
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
