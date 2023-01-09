import asyncio
import logging

from sw_utils import InterruptHandler

from src.config.settings import LOG_LEVEL, NETWORK, NETWORK_CONFIG, SENTRY_DSN

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    datefmt='%m-%d %H:%M',
    level=LOG_LEVEL,
)
logging.getLogger('backoff').addHandler(logging.StreamHandler())

logger = logging.getLogger(__name__)


async def main() -> None:
    # start operator tasks
    interrupt_handler = InterruptHandler()

    while not interrupt_handler.exit:
        await asyncio.sleep(int(NETWORK_CONFIG.SECONDS_PER_BLOCK))


if __name__ == '__main__':
    if SENTRY_DSN:
        import sentry_sdk
        from sentry_sdk.integrations.logging import ignore_logger

        sentry_sdk.init(SENTRY_DSN, traces_sample_rate=0.1)
        sentry_sdk.set_tag('network', NETWORK)
        ignore_logger('backoff')

    asyncio.run(main())
