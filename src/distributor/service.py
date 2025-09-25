import asyncio
import logging
from collections import Counter
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientSession, ClientTimeout
from eth_typing import HexStr
from sw_utils import Oracle, ProtocolConfig

from src.common.contracts import merkle_distributor_contract
from src.common.execution import wait_for_tx_status
from src.common.utils import aiohttp_fetch
from src.config import settings
from src.distributor.typings import DistributorRewardVote, DistributorRewardVoteBody

logger = logging.getLogger(__name__)

DISTRIBUTOR_REWARDS_VOTE_URL_PATH = '/distributor-rewards'


async def process_distributor_rewards(protocol_config: ProtocolConfig) -> None:
    votes = await _fetch_distributor_reward_votes(protocol_config.oracles)
    if not votes:
        logger.warning('No active votes')
        return

    current_nonce = await merkle_distributor_contract.nonce()
    votes = [vote for vote in votes if vote.nonce == current_nonce]
    if not votes:
        logger.info('No votes with nonce %d', current_nonce)
        return

    next_update_timestamp = (
        await merkle_distributor_contract.get_next_rewards_root_update_timestamp()
    )
    votes = [vote for vote in votes if vote.update_timestamp > next_update_timestamp]
    if not votes:
        logger.info('No votes with timestamp > next update timestamp')
        return

    counter = Counter([vote.body for vote in votes])
    winner, winner_vote_count = counter.most_common(1)[0]

    rewards_min_oracles = await merkle_distributor_contract.rewards_min_oracles()
    if winner_vote_count < rewards_min_oracles:
        logger.warning('Not enough oracle votes, skipping distributor rewards update...')
        return

    if winner.root == await merkle_distributor_contract.rewards_root():
        logger.info('Distributor rewards root is already up to date')
        return

    logger.info(
        'Submitting distributor rewards update: root=%s, ipfs hash=%s',
        winner.root,
        winner.ipfs_hash,
    )

    # Sort votes by oracle address.
    # Address must be lowered to match Solidity address collation.
    votes.sort(key=lambda x: x.oracle_address.lower())

    signatures: list[HexStr] = []

    for vote in votes:
        if len(signatures) >= rewards_min_oracles:
            break

        if vote.body == winner:
            signatures.append(vote.signature)

    await _submit_distributor_rewards_vote(
        winner,
        signatures=signatures,
    )


async def _fetch_distributor_reward_votes(oracles: list[Oracle]) -> list[DistributorRewardVote]:
    async with aiohttp.ClientSession(timeout=ClientTimeout(settings.ORACLE_TIMEOUT)) as session:
        results = await asyncio.gather(
            *[_fetch_vote_from_oracle(session=session, oracle=oracle) for oracle in oracles],
            return_exceptions=True,
        )

    votes: list[DistributorRewardVote] = []
    for result in results:
        if isinstance(result, Exception):
            logger.warning(result)
            continue

        votes.append(result)

    return votes


async def _fetch_vote_from_oracle(session: ClientSession, oracle: Oracle) -> DistributorRewardVote:
    results: list[DistributorRewardVote | Exception] = await asyncio.gather(
        *(_fetch_vote_from_endpoint(session, oracle, endpoint) for endpoint in oracle.endpoints),
        return_exceptions=True,
    )
    votes: list[DistributorRewardVote] = []
    for endpoint, result in zip(oracle.endpoints, results):
        if isinstance(result, Exception):
            logger.warning('%r from %s', result, endpoint)
            continue
        votes.append(result)

    if not votes:
        raise RuntimeError(f'All endpoints are unavailable for oracle {oracle.public_key}')

    max_nonce = max(v.nonce for v in votes)
    votes = [v for v in votes if v.nonce == max_nonce]

    return votes[0]


async def _fetch_vote_from_endpoint(
    session: ClientSession, oracle: Oracle, endpoint: str
) -> DistributorRewardVote:
    url = urljoin(endpoint, DISTRIBUTOR_REWARDS_VOTE_URL_PATH)
    data = await aiohttp_fetch(session, url)

    if not data:
        logger.warning('Empty response from oracle')
        raise RuntimeError(f'Invalid response from endpoint {endpoint}')

    for key in [
        'nonce',
        'signature',
        'root',
        'ipfs_hash',
    ]:
        if key not in data.keys():
            logger.warning(
                'Invalid response from oracle'
            )
            raise RuntimeError(f'Invalid response from endpoint {endpoint}')

    vote = DistributorRewardVote(
        oracle_address=oracle.address,
        nonce=data['nonce'],
        update_timestamp=data['update_timestamp'],
        signature=data['signature'],
        body=DistributorRewardVoteBody(
            root=data['root'],
            ipfs_hash=data['ipfs_hash'],
        ),
    )
    return vote


async def _submit_distributor_rewards_vote(
    vote: DistributorRewardVoteBody,
    signatures: list[HexStr],
) -> None:
    tx_hash = await merkle_distributor_contract.set_rewards_root(vote, signatures)
    tx_status = await wait_for_tx_status(tx_hash)

    if tx_status:
        logger.info('Distributor rewards has been successfully updated. Tx hash: %s', tx_hash)
    else:
        logger.error('Distributor rewards transaction failed. Tx hash: %s', tx_hash)
