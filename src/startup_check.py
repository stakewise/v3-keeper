import asyncio
import logging

from aiohttp import ClientSession, ClientTimeout
from sw_utils import IpfsFetchClient
from sw_utils.decorators import retry_aiohttp_errors

from src.accounts import keeper_account
from src.clients import get_consensus_client, get_execution_client
from src.config.settings import (
    CONSENSUS_ENDPOINTS,
    DEFAULT_RETRY_TIME,
    EXECUTION_ENDPOINTS,
    IPFS_FETCH_ENDPOINTS,
)
from src.execution import check_keeper_balance, get_oracles

logger = logging.getLogger(__name__)

IPFS_HASH_EXAMPLE = 'QmawUdo17Fvo7xa6ARCUSMV1eoVwPtVuzx8L8Crj2xozWm'


# pylint: disable-next=too-many-statements
async def startup_checks():
    logger.info('Checking keeper account %s...', keeper_account.address)
    await check_keeper_balance()

    async def _check_consensus_nodes() -> None:
        while True:
            nodes_ready = [
                await _check_consensus_node(endpoint) for endpoint in CONSENSUS_ENDPOINTS
            ]
            if any(nodes_ready):
                return
            logger.warning('Failed to connect to consensus nodes. Retrying in 10 seconds...')
            await asyncio.sleep(10)

    async def _check_consensus_node(consensus_endpoint: str) -> bool:
        try:
            consensus_client = get_consensus_client([consensus_endpoint])
            syncing = await consensus_client.get_syncing()
            if syncing['data']['is_syncing'] is True:
                logger.warning(
                    'The consensus node located at %s '
                    'has not completed synchronization yet. '
                    'The remaining synchronization distance is %s.',
                    consensus_endpoint,
                    syncing['data']['sync_distance'],
                )
                return False
            data = await consensus_client.get_finality_checkpoint()
            logger.info(
                'Connected to consensus node at %s. Finalized epoch: %s',
                consensus_endpoint,
                data['data']['finalized']['epoch'],
            )
            return True
        except Exception as e:
            logger.warning(
                'Failed to connect to consensus node at %s. %s',
                consensus_endpoint,
                e,
            )
            return False

    await _check_consensus_nodes()

    async def _check_execution_nodes() -> None:
        while True:
            nodes_ready = [
                await _check_execution_node(endpoint) for endpoint in EXECUTION_ENDPOINTS
            ]
            if any(nodes_ready):
                return
            logger.warning('Failed to connect to execution nodes. Retrying in 10 seconds...')
            await asyncio.sleep(10)

    async def _check_execution_node(execution_endpoint: str) -> bool:
        try:
            execution_client = get_execution_client([execution_endpoint])

            syncing = await execution_client.eth.syncing
            if syncing is True:
                logger.warning(
                    'The execution node located at %s has not completed synchronization yet.',
                    execution_endpoint,
                )
                return False
            block_number = await execution_client.eth.block_number  # type: ignore
            logger.info(
                'Connected to execution node at %s. Current block number: %s',
                execution_endpoint,
                block_number,
            )
            return True
        except Exception as e:
            logger.warning(
                'Failed to connect to execution node at %s. %s',
                execution_endpoint,
                e,
            )
            return False

    await _check_execution_nodes()

    @retry_aiohttp_errors(delay=DEFAULT_RETRY_TIME)
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
