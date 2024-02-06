import asyncio
import logging
from collections import Counter
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientSession
from sw_utils import Oracle, ProtocolConfig
from web3 import Web3
from web3.types import Timestamp

from src.common import aiohttp_fetch
from src.contracts import keeper_contract
from src.execution import submit_vote
from src.metrics import metrics
from src.typings import RewardVote, RewardVoteBody

logger = logging.getLogger(__name__)

REWARD_VOTE_URL_PATH = '/'


async def process_rewards(protocol_config: ProtocolConfig) -> None:
    if not await keeper_contract.can_update_rewards():
        return

    votes = await _fetch_reward_votes(protocol_config.oracles)
    if not votes:
        logger.warning('No active votes')
        return

    current_nonce = await keeper_contract.get_rewards_nonce()
    votes = [vote for vote in votes if vote.nonce == current_nonce]
    if not votes:
        logger.info('No votes with nonce %d', current_nonce)
        return

    counter = Counter([vote.body for vote in votes])

    winner, winner_vote_count = counter.most_common(1)[0]

    if not await _can_submit(winner_vote_count, protocol_config.rewards_threshold):
        logger.warning('Not enough oracle votes, skipping update...')
        return

    logger.info(
        'Submitting rewards update: root=%s, ipfs hash=%s, timestamp=%d, avg_reward_per_second=%d',
        winner.root,
        winner.ipfs_hash,
        winner.update_timestamp,
        winner.avg_reward_per_second,
    )

    signatures_count = 0
    signatures = b''
    for vote in sorted(votes, key=lambda x: Web3.to_int(hexstr=x.oracle_address)):
        if signatures_count >= protocol_config.rewards_threshold:
            break

        if vote.body == winner:
            signatures += vote.signature
            signatures_count += 1

    await submit_vote(
        winner,
        signatures=signatures,
    )


async def _fetch_reward_votes(oracles: list[Oracle]) -> list[RewardVote]:
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(
            *[_fetch_vote_from_oracle(session=session, oracle=oracle) for oracle in oracles],
            return_exceptions=True,
        )

    votes: list[RewardVote] = []
    for result in results:
        if isinstance(result, Exception):
            logger.warning(result)
            continue

        votes.append(result)

    return votes


async def _can_submit(signatures_count: int, threshold) -> bool:
    return signatures_count >= threshold


async def _fetch_vote_from_oracle(session: ClientSession, oracle: Oracle) -> RewardVote:
    results: list[RewardVote | Exception] = await asyncio.gather(
        *(_fetch_vote_from_endpoint(session, oracle, endpoint) for endpoint in oracle.endpoints),
        return_exceptions=True,
    )
    votes: list[RewardVote] = []
    for endpoint, result in zip(oracle.endpoints, results):
        if isinstance(result, Exception):
            logger.warning('%s from %s', repr(result), endpoint)
            continue
        votes.append(result)

    if not votes:
        raise RuntimeError(f'All endpoints are unavailable for oracle {oracle.public_key}')

    max_nonce = max(v.nonce for v in votes)
    votes = [v for v in votes if v.nonce == max_nonce]
    if len(votes) == 1:
        return votes[0]

    votes.sort(key=lambda v: v.body.update_timestamp)

    return votes[-1]


async def _fetch_vote_from_endpoint(
    session: ClientSession, oracle: Oracle, endpoint: str
) -> RewardVote:
    url = urljoin(endpoint, REWARD_VOTE_URL_PATH)
    data = await aiohttp_fetch(session, url)

    if not data:
        logger.warning('Empty response from oracle', extra={'endpoint': endpoint, 'response': data})
        raise RuntimeError(f'Invalid response from endpoint {endpoint}')

    for key in [
        'nonce',
        'update_timestamp',
        'signature',
        'root',
        'ipfs_hash',
        'avg_reward_per_second',
    ]:
        if key not in data.keys():
            logger.warning(
                'Invalid response from oracle', extra={'endpoint': endpoint, 'response': data}
            )
            raise RuntimeError(f'Invalid response from endpoint {endpoint}')

    metrics.oracle_avg_rewards_per_second.labels(oracle_address=endpoint).set(
        data['avg_reward_per_second']
    )
    metrics.oracle_update_timestamp.labels(oracle_address=endpoint).set(data['update_timestamp'])

    vote = RewardVote(
        oracle_address=oracle.address,
        nonce=data['nonce'],
        signature=Web3.to_bytes(hexstr=data['signature']),
        body=RewardVoteBody(
            root=data['root'],
            ipfs_hash=data['ipfs_hash'],
            avg_reward_per_second=data['avg_reward_per_second'],
            update_timestamp=Timestamp(data['update_timestamp']),
        ),
    )
    return vote
