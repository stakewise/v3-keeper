import asyncio
import logging
import time
from collections import Counter
from typing import Iterable
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientSession
from sw_utils import Oracle, ProtocolConfig
from web3 import Web3
from web3.types import Timestamp

from src.common import aiohttp_fetch
from src.config.settings import NETWORK_CONFIG
from src.contracts import keeper_contract
from src.execution import gas_manager, wait_for_tx_status
from src.metrics import metrics
from src.typings import RewardVote, RewardVoteBody

logger = logging.getLogger(__name__)

REWARD_VOTE_URL_PATH = '/'
DEFAULT_CACHE_SIZE = 100


class RewardsCache:
    """
    Cache solves the problem of oracle synchronization.
    On some networks, oracles fail to synchronize within a specific epoch.
    Storing votes in the cache makes it easier to catch up with synchronization.
    """

    def __init__(self, cache_size: int = DEFAULT_CACHE_SIZE) -> None:
        self.data: dict[Timestamp, list[RewardVote]] = {}
        self.cache_size = cache_size

    def update(self, votes: list[RewardVote]) -> None:
        for vote in votes:
            update_timestamp = vote.body.update_timestamp
            if not self.data.get(update_timestamp):
                self.data[update_timestamp] = []
            if vote not in self.data[update_timestamp]:
                self.data[update_timestamp].append(vote)

        while len(self.data) > self.cache_size:
            oldest_ts = min(self.data.keys())
            del self.data[oldest_ts]

    def rewards(self) -> list[list[RewardVote]]:
        rewards = list(self.data.values())
        rewards.sort(key=lambda item: item[0].body.update_timestamp)
        return rewards

    def clear(self) -> None:
        self.data = {}


async def process_rewards(protocol_config: ProtocolConfig, rewards_cache: RewardsCache) -> None:
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

    rewards_cache.update(votes)

    timestamp_votes, winner = _find_earliest_winner(
        rewards_cache=rewards_cache, rewards_threshold=protocol_config.rewards_threshold
    )
    if winner is None or timestamp_votes is None:
        logger.warning('Not enough oracle votes to update rewards, skipping update...')
        return

    logger.info(
        'Submitting rewards update: '
        'root=%s, ipfs hash=%s, timestamp=%d, avg_reward_per_second=%d',
        winner.root,
        winner.ipfs_hash,
        winner.update_timestamp,
        winner.avg_reward_per_second,
    )

    signatures_count = 0
    signatures = b''
    for vote in sorted(timestamp_votes, key=lambda x: Web3.to_int(hexstr=x.oracle_address)):
        if signatures_count >= protocol_config.rewards_threshold:
            break

        if vote.body == winner:
            signatures += vote.signature
            signatures_count += 1

    await _submit_vote(
        winner,
        signatures=signatures,
    )
    rewards_cache.clear()


def _find_earliest_winner(
    rewards_cache: RewardsCache, rewards_threshold: int
) -> tuple[Iterable[RewardVote], RewardVoteBody] | tuple[None, None]:
    for timestamp_votes in rewards_cache.rewards():
        counter = Counter([vote.body for vote in timestamp_votes])
        winner, winner_vote_count = counter.most_common(1)[0]

        if not _can_submit(winner_vote_count, rewards_threshold):
            logger.warning(
                'Not enough oracle votes for timestamp %s, checking next timestamp...',
                winner.update_timestamp,
            )
            continue
        return timestamp_votes, winner

    return None, None


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


def _can_submit(signatures_count: int, threshold: int) -> bool:
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


async def _submit_vote(
    vote: RewardVoteBody,
    signatures: bytes,
) -> None:
    # trying to submit with basic gas
    attempts_with_basic_gas = 3
    for _ in range(attempts_with_basic_gas):
        try:
            tx_hash = await keeper_contract.update_rewards(vote, signatures)
            break
        except ValueError as e:
            logger.exception(e)
            time.sleep(NETWORK_CONFIG.SECONDS_PER_BLOCK)
    else:
        # use high priority fee
        tx_params = await gas_manager.get_high_priority_tx_params()
        tx_hash = await keeper_contract.update_rewards(vote, signatures, tx_params)

    tx_status = await wait_for_tx_status(tx_hash)

    if tx_status:
        logger.info('Rewards have been successfully updated. Tx hash: %s', tx_hash)
    else:
        logger.error('Rewards transaction failed. Tx hash: %s', tx_hash)
