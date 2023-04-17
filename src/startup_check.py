import asyncio
import logging

import backoff
from aiohttp import ClientSession, ClientTimeout
from sw_utils import IpfsFetchClient

from src.accounts import keeper_account
from src.clients import consensus_client, execution_client
from src.config.settings import (
    CONSENSUS_ENDPOINT,
    DEFAULT_RETRY_TIME,
    EXECUTION_ENDPOINT,
    IPFS_FETCH_ENDPOINTS,
)
from src.execution import check_keeper_balance, get_oracles

logger = logging.getLogger(__name__)

IPFS_HASH_EXAMPLE = 'QmawUdo17Fvo7xa6ARCUSMV1eoVwPtVuzx8L8Crj2xozWm'


async def startup_checks():
    logger.info('Checking keeper account %s...', keeper_account.address)
    await check_keeper_balance()

    @backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
    async def _check_execution_node():
        logger.info('Checking connection to execution node...')
        block_number = await execution_client.eth.block_number
        logger.info(
            'Connected to execution node at %s. Current block number: %s',
            EXECUTION_ENDPOINT,
            block_number,
        )

    await _check_execution_node()

    @backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
    async def _check_consensus_node():
        logger.info('Checking connection to consensus node...')
        data = await consensus_client.get_finality_checkpoint()
        logger.info(
            'Connected to consensus node at %s. Finalized epoch: %s',
            CONSENSUS_ENDPOINT,
            data['data']['finalized']['epoch'],
        )

    await _check_consensus_node()

    @backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
    async def _check_ipfs_fetch_nodes():
        logger.info('Checking connection to ipfs fetch nodes...')

        healthy_ipfs_endpoint = []
        for endpoint in IPFS_FETCH_ENDPOINTS:
            client = IpfsFetchClient([endpoint])
            try:
                await client.fetch_json(IPFS_HASH_EXAMPLE)
            except Exception as e:
                logger.warning("Can't connect to ipfs node %s: %s", endpoint, e)
            else:
                healthy_ipfs_endpoint.append(endpoint)
        logger.info('Connected to ipfs nodes at %s.', ', '.join(healthy_ipfs_endpoint))

    await _check_ipfs_fetch_nodes()

    logger.info('Checking connection to oracles set...')
    oracles = await get_oracles()

    async with ClientSession(timeout=ClientTimeout(60)) as session:
        results = await asyncio.gather(
            *[_aiohttp_fetch(session=session, url=oracle.endpoint) for oracle in oracles],
            return_exceptions=True
        )

    healthy_oracles = []
    for result in results:
        if isinstance(result, BaseException):
            logger.error(result)
            continue

        if result:
            healthy_oracles.append(result)

    if healthy_oracles:
        logger.info('Connected to oracles at %s', ', '.join(healthy_oracles))
    else:
        logger.warning("Can't connect to oracles set")


async def _aiohttp_fetch(session, url) -> str:
    async with session.get(url=url) as response:
        response.raise_for_status()
    return url
