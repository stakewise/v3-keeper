import asyncio
import logging
import time

from sw_utils import InterruptHandler

import src
from src.common.clients import execution_client, setup_execution_client
from src.common.execution import get_keeper_balance, get_protocol_config
from src.common.startup_check import startup_checks
from src.config.settings import (
    FORCE_EXITS_SUPPORTED_NETWORKS,
    LOG_LEVEL,
    METRICS_HOST,
    METRICS_PORT,
    NETWORK,
    NETWORK_CONFIG,
    OSETH_PRICE_SUPPORTED_NETWORKS,
    SENTRY_DSN,
    SKIP_DISTRIBUTOR_REWARDS,
    SKIP_FORCE_EXITS,
    SKIP_OSETH_PRICE_UPDATE,
    WEB3_LOG_LEVEL,
)
from src.distributor.service import process_distributor_rewards
from src.exits.service import process_exits
from src.force_exit.service import process_force_exits
from src.metrics import metrics, metrics_server
from src.price.service import process_layer_two_oseth_price
from src.rewards.service import RewardsCache, process_rewards

logging.basicConfig(
    format='%(asctime)s %(name)s %(levelname)-8s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=LOG_LEVEL,
)

logging.getLogger('web3').setLevel(WEB3_LOG_LEVEL)

logger = logging.getLogger(__name__)


def log_start() -> None:
    logger.info('Starting keeper service, version %s', src.__version__)


async def main() -> None:
    log_start()
    await setup_execution_client(execution_client)
    await startup_checks()

    logger.info('Starting metrics server: %s:%i', METRICS_HOST, METRICS_PORT)
    await metrics_server()
    logger.info('Started keeper service...')

    rewards_cache = RewardsCache()
    with InterruptHandler() as interrupt_handler:
        while not interrupt_handler.exit:
            start_time = time.time()
            try:
                protocol_config = await get_protocol_config()

                if not protocol_config.oracles:
                    logger.error('Empty oracles set')
                    await interrupt_handler.sleep(60)
                    continue

                tasks = [
                    process_rewards(
                        protocol_config=protocol_config,
                        rewards_cache=rewards_cache,
                    ),
                    process_exits(
                        protocol_config=protocol_config,
                    ),
                ]

                # distributor
                if not SKIP_DISTRIBUTOR_REWARDS:
                    tasks.append(
                        process_distributor_rewards(
                            protocol_config=protocol_config,
                        )
                    )

                # update price
                if NETWORK in OSETH_PRICE_SUPPORTED_NETWORKS and not SKIP_OSETH_PRICE_UPDATE:
                    tasks.append(process_layer_two_oseth_price())

                # force position exits
                if NETWORK in FORCE_EXITS_SUPPORTED_NETWORKS and not SKIP_FORCE_EXITS:
                    tasks.append(process_force_exits())

                results = await asyncio.gather(
                    *tasks,
                    return_exceptions=True,
                )

                for result in results:
                    if isinstance(result, Exception):
                        logger.exception('', exc_info=result)

                metrics.keeper_balance.set(await get_keeper_balance())
            except Exception as exc:
                logger.exception(exc)

            block_processing_time = time.time() - start_time
            sleep_time = max(float(NETWORK_CONFIG.SECONDS_PER_BLOCK) - block_processing_time, 0)
            await interrupt_handler.sleep(sleep_time)


if __name__ == '__main__':
    if SENTRY_DSN:
        import sentry_sdk

        sentry_sdk.init(
            SENTRY_DSN,
            traces_sample_rate=0.1,
            environment=NETWORK,
        )
        sentry_sdk.set_tag('network', NETWORK)
        sentry_sdk.set_tag('project_version', src.__version__)

    asyncio.run(main())
