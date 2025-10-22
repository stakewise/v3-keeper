import logging
import time

from web3.types import TxParams

from src.common.app_state import AppState
from src.common.clients import execution_client, keeper_account
from src.common.contracts import (
    price_feed_sender_contract,
    target_price_feed_contract,
    transaction_gas_wrapper,
)
from src.config.settings import (
    PRICE_MAX_WAITING_TIME,
    PRICE_NETWORK_CONFIG,
    PRICE_UPDATE_INTERVAL,
)

logger = logging.getLogger(__name__)


async def process_layer_two_oseth_price() -> None:
    """
    Update osEth price on Arbitrum chain using Ethereum data.
    Available on Sepolia network for testing.
    """
    # Step 1: Check latest timestamp
    latest_timestamp = await target_price_feed_contract.functions.latestTimestamp().call()
    current_time = int(time.time())

    if current_time - latest_timestamp < PRICE_UPDATE_INTERVAL:
        logger.debug(
            'Less than %d hours since the last update. No action needed.',
            PRICE_UPDATE_INTERVAL // 3600,
        )
        return

    # Step 2: check if transaction is already in progress
    app_state = AppState()
    if app_state.last_price_updated_timestamp:
        if app_state.last_price_updated_timestamp + PRICE_MAX_WAITING_TIME > current_time:
            logger.info('Waiting for the timestamp to update...')
            return

        if latest_timestamp < app_state.last_price_updated_timestamp:
            logger.error(
                'Timestamp did not update on the target chain within %s sec.',
                PRICE_MAX_WAITING_TIME,
            )
        app_state.last_price_updated_timestamp = None

    # Step 3: Get the cost
    target_chain = PRICE_NETWORK_CONFIG.TARGET_CHAIN
    target_address = PRICE_NETWORK_CONFIG.TARGET_ADDRESS

    current_rate = await price_feed_sender_contract.functions.quoteRateSync(target_chain).call()

    # Step 4: Sync the rate
    tx_function = price_feed_sender_contract.functions.syncRate(target_chain, target_address)
    tx_params: TxParams = {
        'from': keeper_account.address,
        'value': current_rate,
    }
    tx = await transaction_gas_wrapper(tx_function=tx_function, tx_params=tx_params)

    logger.info('Sync transaction sent: %s', tx.hex())
    receipt = await execution_client.eth.wait_for_transaction_receipt(tx)

    if not receipt['status']:
        raise RuntimeError(f'Sync transaction failed, tx hash: {tx.hex()}')

    logger.info('Sync transaction confirmed.')
    app_state.last_price_updated_timestamp = int(time.time())
