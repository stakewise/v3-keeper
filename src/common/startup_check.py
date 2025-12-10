import asyncio
import logging

from aiohttp import ClientSession, ClientTimeout
from sw_utils import IpfsFetchClient
from sw_utils.decorators import retry_aiohttp_errors

from src.common.accounts import keeper_account
from src.common.clients import get_consensus_client, get_execution_client, graph_client
from src.common.execution import check_keeper_balance, get_protocol_config
from src.common.graph import check_for_graph_node_sync_to_block
from src.common.utils import aiohttp_fetch
from src.config.settings import (
    CONSENSUS_ENDPOINTS,
    DEFAULT_RETRY_TIME,
    EXECUTION_ENDPOINTS,
    FORCE_EXITS_SUPPORTED_NETWORKS,
    IPFS_FETCH_ENDPOINTS,
    L2_EXECUTION_ENDPOINTS,
    NETWORK,
    OSETH_PRICE_SUPPORTED_NETWORKS,
    PRICE_MAX_WAITING_TIME,
    PRICE_UPDATE_INTERVAL,
    SKIP_FORCE_EXITS,
    SKIP_OSETH_PRICE_UPDATE,
    SKIP_UPDATE_LTV,
)

logger = logging.getLogger(__name__)

IPFS_HASH_EXAMPLE = 'QmawUdo17Fvo7xa6ARCUSMV1eoVwPtVuzx8L8Crj2xozWm'


# pylint: disable-next=too-many-statements
async def startup_checks() -> None:
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
        consensus_client = get_consensus_client([consensus_endpoint])
        try:
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
        finally:
            await consensus_client.disconnect()

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

    async def _check_l2_execution_nodes() -> None:
        while True:
            nodes_ready = [
                await _check_execution_node(endpoint) for endpoint in L2_EXECUTION_ENDPOINTS
            ]
            if any(nodes_ready):
                return
            logger.warning('Failed to connect to l2 execution nodes. Retrying in 10 seconds...')
            await asyncio.sleep(10)

    async def _check_execution_node(execution_endpoint: str) -> bool:
        execution_client = get_execution_client([execution_endpoint])
        try:
            syncing = await execution_client.eth.syncing
            if syncing is True:
                logger.warning(
                    'The execution node located at %s has not completed synchronization yet.',
                    execution_endpoint,
                )
                return False
            block_number = await execution_client.eth.block_number
            if block_number <= 0:
                # There was a case when `block_number` equals to 0 although `syncing` is False.
                logger.warning(
                    'Execution node %s. Current block number is %s',
                    execution_endpoint,
                    block_number,
                )
                return False
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

        finally:
            await execution_client.provider.disconnect()

    await _check_execution_nodes()

    if NETWORK in OSETH_PRICE_SUPPORTED_NETWORKS and not SKIP_OSETH_PRICE_UPDATE:
        await _check_l2_execution_nodes()
        if PRICE_MAX_WAITING_TIME >= PRICE_UPDATE_INTERVAL:
            raise ValueError(
                f'PRICE_MAX_WAITING_TIME ({PRICE_MAX_WAITING_TIME}) should be less than '
                f'PRICE_UPDATE_INTERVAL ({PRICE_UPDATE_INTERVAL})'
            )
    if _is_graph_used():
        await check_for_graph_node_sync_to_block('finalized')
        logger.info('Connected to graph node at %s.', graph_client.endpoint)
    return
    @retry_aiohttp_errors(delay=DEFAULT_RETRY_TIME)
    async def _check_ipfs_fetch_nodes() -> None:
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
    protocol_config = await get_protocol_config()
    oracles = protocol_config.oracles
    oracle_endpoints = [endpoint for oracle in oracles for endpoint in oracle.endpoints]

    async with ClientSession(timeout=ClientTimeout(60)) as session:
        results = await asyncio.gather(
            *[aiohttp_fetch(session=session, url=endpoint) for endpoint in oracle_endpoints],
            return_exceptions=True,
        )

    healthy_oracles: list[str] = []
    for endpoint, result in zip(oracle_endpoints, results):
        if isinstance(result, Exception):
            logger.error('Error from oracle %s: %s', endpoint, result)
            continue

        healthy_oracles.append(endpoint)

    if healthy_oracles:
        logger.info('Connected to oracles at %s', ', '.join(healthy_oracles))
    else:
        logger.warning("Can't connect to oracles set")


def _is_graph_used() -> bool:
    if NETWORK in FORCE_EXITS_SUPPORTED_NETWORKS and not SKIP_FORCE_EXITS:
        return True
    if not SKIP_UPDATE_LTV:
        return True
    return False
