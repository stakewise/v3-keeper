import asyncio
import logging
import time

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
from src.execution import get_keeper_balance, get_oracle_config
from src.exits import process_exits
from src.metrics import metrics, metrics_server
from src.rewards import process_rewards
from src.startup_check import startup_checks

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=LOG_LEVEL,
)

logger = logging.getLogger(__name__)


def log_start() -> None:
    logger.info('Starting keeper service, version %s', src.__version__)


async def main() -> None:
    log_start()

    await startup_checks()

    logger.info('Starting metrics server: %s:%i', METRICS_HOST, METRICS_PORT)
    await metrics_server()
    logger.info('Started keeper service...')

    with InterruptHandler() as interrupt_handler:
        while not interrupt_handler.exit:
            start_time = time.time()
            try:
                oracle_config = await get_oracle_config()

                if not oracle_config.oracles:
                    logger.error('Empty oracles set')
                    await asyncio.sleep(60)
                    continue

                results = await asyncio.gather(
                    process_rewards(
                        oracles=oracle_config.oracles, threshold=oracle_config.rewards_threshold
                    ),
                    process_exits(
                        oracles=oracle_config.oracles,
                        threshold=oracle_config.exit_signature_recover_threshold,
                    ),
                    return_exceptions=True,
                )

                for result in results:
                    if isinstance(result, Exception):
                        raise result

                metrics.keeper_balance.set(await get_keeper_balance())
            except Exception as exc:
                logger.exception(exc)

            block_processing_time = time.time() - start_time
            sleep_time = max(float(NETWORK_CONFIG.SECONDS_PER_BLOCK) - block_processing_time, 0)
            await asyncio.sleep(sleep_time)


if __name__ == '__main__':
    if SENTRY_DSN:
        import sentry_sdk

        sentry_sdk.init(SENTRY_DSN, traces_sample_rate=0.1)
        sentry_sdk.set_tag('network', NETWORK)

    asyncio.run(main())
