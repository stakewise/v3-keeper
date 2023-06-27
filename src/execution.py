import logging

import backoff
from eth_keys.datatypes import PublicKey
from web3 import Web3
from web3.types import Wei

from src.accounts import keeper_account
from src.clients import execution_client, ipfs_fetch_client
from src.config.settings import DEFAULT_RETRY_TIME, NETWORK_CONFIG
from src.contracts import keeper_contract
from src.typings import Oracle

logger = logging.getLogger(__name__)

SECONDS_PER_MONTH: int = 2628000
APPROX_BLOCKS_PER_MONTH: int = int(SECONDS_PER_MONTH // NETWORK_CONFIG.SECONDS_PER_BLOCK)


async def get_oracles() -> list[Oracle]:
    events = await keeper_contract.get_config_update_events()
    if not events:
        raise ValueError('Failed to fetch IPFS hash of oracles config')

    # fetch IPFS record
    ipfs_hash = events[-1]['args']['configIpfsHash']
    config = await _fetch_ipfs_config(ipfs_hash)

    oracles = []
    for index, oracle_config in enumerate(config['oracles']):
        public_key = PublicKey(Web3.to_bytes(hexstr=oracle_config['public_key']))
        oracle = Oracle(
            address=public_key.to_checksum_address(),
            endpoint=oracle_config['endpoint'],
            index=index,
        )
        oracles.append(oracle)

    return oracles


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
            symbol,
        )


@backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
async def _fetch_ipfs_config(ipfs_hash) -> dict:
    return await ipfs_fetch_client.fetch_json(ipfs_hash)
