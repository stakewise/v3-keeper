import logging
from collections import Counter
from urllib.parse import urljoin

import aiohttp
from eth_typing import ChecksumAddress
from web3 import Web3
from web3.types import Timestamp

from src.config.settings import NETWORK_CONFIG
from src.execution import (
    get_last_rewards_update,
    get_latest_block,
    get_oracles,
    get_oracles_threshold,
    submit_vote,
)
from src.typings import RewardVote

logger = logging.getLogger(__name__)

REWARD_VOTE_URL_PATH = '/'


async def process_votes():
    current_block = await get_latest_block()
    last_update_timestamp = await get_last_rewards_update(current_block['number'])
    if last_update_timestamp is None:
        last_update_timestamp = NETWORK_CONFIG.KEEPER_GENESIS_TIMESTAMP

    missed_seconds: int = (
        (current_block['timestamp'] - last_update_timestamp) // NETWORK_CONFIG.SYNC_PERIOD
    ) * NETWORK_CONFIG.SYNC_PERIOD
    if missed_seconds <= 0:
        # skip updating vote if too early
        return

    update_timestamp: Timestamp = Timestamp(last_update_timestamp + missed_seconds)
    update_timestamp_boundary: Timestamp = Timestamp(
        last_update_timestamp + NETWORK_CONFIG.SYNC_PERIOD
    )

    oracles = await get_oracles()
    if not oracles:
        logger.error('Empty oracles set')
        return

    votes = await fetch_reward_votes(oracles)
    votes = [vote for vote in votes if vote.update_timestamp >= update_timestamp_boundary]

    counter = Counter(
        [
            (
                vote.root,
                vote.ipfs_hash,
            )
            for vote in votes
        ]
    )

    most_voted = counter.most_common(1)
    threshold = await get_oracles_threshold()
    if not can_submit(most_voted[0][1], threshold):
        logger.error('Not enough oracle votes, skipping update...')
        return
    root, ipfs_hash = most_voted[0][0]
    logger.info(
        'Submitting rewards update: rewards ipfs hash=%s at %s',
        ipfs_hash,
        update_timestamp,
    )

    signatures = b''
    for vote in sorted(votes, key=lambda x: Web3.to_int(hexstr=x.oracle_address)):
        if vote.root == root:
            signatures += vote.signature

    await submit_vote(
        rewards_root=root,
        update_timestamp=update_timestamp,
        rewards_ipfs_hash=ipfs_hash,
        signatures=signatures,
    )
    logger.info('Rewards has been successfully updated')


async def fetch_reward_votes(oracles: dict[ChecksumAddress, str]) -> list[RewardVote]:
    votes: list[RewardVote] = []
    async with aiohttp.ClientSession() as session:
        for address, endpoint in oracles.items():
            data = await _aiohttp_fetch(session, url=urljoin(endpoint, REWARD_VOTE_URL_PATH))
            votes.append(
                RewardVote(
                    oracle_address=address,
                    nonce=data['nonce'],
                    update_timestamp=Timestamp(data['update_timestamp']),
                    signature=Web3.to_bytes(hexstr=data['signature']),
                    root=data['root'],
                    ipfs_hash=data['ipfs_hash'],
                )
            )
    return votes


async def can_submit(signatures_count: int, threshold) -> bool:
    return signatures_count >= threshold


async def _aiohttp_fetch(session, url):
    async with session.get(url=url) as response:
        response.raise_for_status()
        data = await response.json()
    return data
