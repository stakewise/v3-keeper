import logging

from web3 import Web3
from web3.types import Wei

from src.common.accounts import keeper_account
from src.common.clients import execution_client
from src.config.settings import NETWORK_CONFIG

logger = logging.getLogger(__name__)


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
