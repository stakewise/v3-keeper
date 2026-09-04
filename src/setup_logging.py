import logging

from src.config.settings import GQL_LOG_LEVEL, LOG_LEVEL, WEB3_LOG_LEVEL


def setup_logging() -> None:
    logging.basicConfig(
        format='%(asctime)s %(name)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=LOG_LEVEL,
    )

    logging.getLogger('web3').setLevel(WEB3_LOG_LEVEL)
    logging.getLogger('gql.transport.aiohttp').setLevel(GQL_LOG_LEVEL)
