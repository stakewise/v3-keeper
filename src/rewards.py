import asyncio
import logging
from collections import Counter
from urllib.parse import urljoin

import aiohttp
from web3 import Web3
from web3.types import Timestamp

from src.common import aiohttp_fetch
from src.execution import can_update_rewards, get_keeper_rewards_nonce, submit_vote
from src.typings import Oracle, RewardVote

logger = logging.getLogger(__name__)

REWARD_VOTE_URL_PATH = '/'


async def process_rewards(oracles: list[Oracle], threshold: int) -> None:
    if not await can_update_rewards():
        return

    votes = await _fetch_reward_votes(oracles)
    if not votes:
        logger.warning('No active votes')
        return

    current_nonce = await get_keeper_rewards_nonce()
    votes = [vote for vote in votes if vote.nonce == current_nonce]
    if not votes:
        logger.info('No votes with nonce %d', current_nonce)
        return

    counter = Counter([(
        vote.root, vote.ipfs_hash, vote.update_timestamp, vote.avg_reward_per_second
    ) for vote in votes])

    most_voted = counter.most_common(1)
    if not await _can_submit(most_voted[0][1], threshold):
        logger.warning('Not enough oracle votes, skipping update...')
        return

    root, ipfs_hash, update_timestamp, avg_reward_per_second = most_voted[0][0]
    logger.info(
        'Submitting rewards update: root=%s, ipfs hash=%s, timestamp=%d, avg_reward_per_second=%d',
        root,
        ipfs_hash,
        update_timestamp,
        avg_reward_per_second,
    )

    signatures_count = 0
    signatures = b''
    for vote in sorted(votes, key=lambda x: Web3.to_int(hexstr=x.oracle_address)):
        if signatures_count >= threshold:
            break

        if (vote.root, vote.ipfs_hash, vote.update_timestamp, vote.avg_reward_per_second) == (
            root,
            ipfs_hash,
            update_timestamp,
            avg_reward_per_second,
        ):
            signatures += vote.signature
            signatures_count += 1

    await submit_vote(
        rewards_root=root,
        avg_reward_per_second=avg_reward_per_second,
        update_timestamp=update_timestamp,
        rewards_ipfs_hash=ipfs_hash,
        signatures=signatures,
    )
    logger.info('Rewards has been successfully updated')


async def _fetch_reward_votes(oracles: list[Oracle]) -> list[RewardVote]:
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(
            *[
                _fetch_vote(
                    session=session, oracle=oracle
                )
                for oracle in oracles
            ],
            return_exceptions=True
        )

    votes: list[RewardVote] = []
    for result in results:
        if isinstance(result, BaseException):
            logger.error(result)
            continue

        if result:
            votes.append(result)

    return votes


async def _can_submit(signatures_count: int, threshold) -> bool:
    return signatures_count >= threshold


async def _fetch_vote(session, oracle) -> RewardVote | None:
    url = urljoin(oracle.endpoint, REWARD_VOTE_URL_PATH)
    data = await aiohttp_fetch(session, url)

    if not data:
        logger.warning(
            'Empty response from oracle',
            extra={'oracle': oracle.address, 'response': data}
        )
        return None

    for key in [
        'nonce', 'update_timestamp', 'signature', 'root', 'ipfs_hash', 'avg_reward_per_second'
    ]:
        if key not in data.keys():
            logger.error(
                'Invalid response from oracle',
                extra={'oracle': oracle.address, 'response': data}
            )
            return None

    vote = RewardVote(
        oracle_address=oracle.address,
        nonce=data['nonce'],
        update_timestamp=Timestamp(data['update_timestamp']),
        signature=Web3.to_bytes(hexstr=data['signature']),
        root=data['root'],
        ipfs_hash=data['ipfs_hash'],
        avg_reward_per_second=data['avg_reward_per_second'],
    )
    return vote
