import asyncio
import logging

from sw_utils import InterruptHandler

import src
from src.config.settings import (
    LOG_LEVEL,
    METRICS_HOST,
    METRICS_PORT,
    NETWORK,
    NETWORK_CONFIG,
    SENTRY_DSN,
)
from src.contracts import keeper_contract
from src.execution import get_keeper_balance, get_oracles
from src.exits import process_exits
from src.metrics import metrics, metrics_server
from src.rewards import process_rewards
from src.startup_check import startup_checks

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    datefmt='%m-%d %H:%M',
    level=LOG_LEVEL,
)
logging.getLogger('backoff').addHandler(logging.StreamHandler())

logger = logging.getLogger(__name__)


def log_start() -> None:
    logger.info('Starting keeper service, version %s', src.__version__)


async def main() -> None:
    log_start()

    await startup_checks()

    logger.info('Starting metrics server: %s:%i', METRICS_HOST, METRICS_PORT)
    await metrics_server()

    interrupt_handler = InterruptHandler()

    while not interrupt_handler.exit:
        oracles = await get_oracles()
        if not oracles:
            logger.error('Empty oracles set')
            await asyncio.sleep(60)
            continue
        threshold = await keeper_contract.get_oracles_threshold()

        keeper_balance = await get_keeper_balance()
        metrics.keeper_balance.set(keeper_balance)

        await process_rewards(oracles=oracles, threshold=threshold)
        await process_exits(oracles=oracles, threshold=threshold)
        await asyncio.sleep(int(NETWORK_CONFIG.SECONDS_PER_BLOCK))


if __name__ == '__main__':
    if SENTRY_DSN:
        import sentry_sdk
        from sentry_sdk.integrations.logging import ignore_logger

        sentry_sdk.init(SENTRY_DSN, traces_sample_rate=0.1)
        sentry_sdk.set_tag('network', NETWORK)
        ignore_logger('backoff')

    asyncio.run(main())
