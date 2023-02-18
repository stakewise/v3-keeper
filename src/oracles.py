import asyncio
import logging
from collections import Counter
from urllib.parse import urljoin

import aiohttp
from eth_typing import ChecksumAddress
from web3 import Web3
from web3.types import Timestamp

from src.execution import (
    can_update_rewards,
    get_keeper_rewards_nonce,
    get_oracles,
    get_oracles_threshold,
    submit_vote,
)
from src.typings import RewardVote

logger = logging.getLogger(__name__)

REWARD_VOTE_URL_PATH = '/'


async def process_votes() -> None:
    if not await can_update_rewards():
        return

    oracles = await get_oracles()
    if not oracles:
        logger.error('Empty oracles set')
        return

    votes = await fetch_reward_votes(oracles)
    if not votes:
        logger.warning('No active votes')
        return

    current_nonce = await get_keeper_rewards_nonce()
    votes = [vote for vote in votes if vote.nonce == current_nonce]
    if not votes:
        logger.info('No votes with nonce %d', current_nonce)
        return

    counter = Counter([(vote.root, vote.ipfs_hash, vote.update_timestamp) for vote in votes])

    most_voted = counter.most_common(1)
    threshold = await get_oracles_threshold()
    if not await can_submit(most_voted[0][1], threshold):
        logger.error('Not enough oracle votes, skipping update...')
        return

    root, ipfs_hash, update_timestamp = most_voted[0][0]
    logger.info(
        'Submitting rewards update: root=%s, ipfs hash=%s, timestamp=%d',
        root,
        ipfs_hash,
        update_timestamp,
    )

    signatures = b''
    for vote in sorted(votes, key=lambda x: Web3.to_int(hexstr=x.oracle_address)):
        if (vote.root, vote.ipfs_hash, vote.update_timestamp) == (
            root,
            ipfs_hash,
            update_timestamp,
        ):
            signatures += vote.signature

    await submit_vote(
        rewards_root=root,
        update_timestamp=update_timestamp,
        rewards_ipfs_hash=ipfs_hash,
        signatures=signatures,
    )
    logger.info('Rewards has been successfully updated')


async def fetch_reward_votes(oracles: dict[ChecksumAddress, str]) -> list[RewardVote]:
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(
            *[
                _fetch_vote(
                    session=session, url=urljoin(endpoint, REWARD_VOTE_URL_PATH), account=account
                )
                for account, endpoint in oracles.items()
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


async def can_submit(signatures_count: int, threshold) -> bool:
    return signatures_count >= threshold


async def _fetch_vote(session, url, account) -> RewardVote | None:
    data = await _aiohttp_fetch(session, url)

    if not data:
        logger.warning('Empty response from oracle', extra={'oracle': account, 'response': data})
        return None

    for key in ['nonce', 'update_timestamp', 'signature', 'root', 'ipfs_hash']:
        if key not in data.keys():
            logger.error(
                'Invalid response from oracle', extra={'oracle': account, 'response': data}
            )
            return None

    vote = RewardVote(
        oracle_address=account,
        nonce=data['nonce'],
        update_timestamp=Timestamp(data['update_timestamp']),
        signature=Web3.to_bytes(hexstr=data['signature']),
        root=data['root'],
        ipfs_hash=data['ipfs_hash'],
    )
    return vote


async def _aiohttp_fetch(session, url) -> dict:
    async with session.get(url=url) as response:
        response.raise_for_status()
        data = await response.json()
    return data
