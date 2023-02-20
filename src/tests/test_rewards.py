import random
import string
from unittest.mock import patch

import pytest
from eth_typing import HexStr
from sw_utils.tests import faker
from web3.types import Timestamp

from src.oracles import process_votes
from src.typings import RewardVote

pytestmark = pytest.mark.asyncio


async def test_early():
    with patch('src.oracles._aiohttp_fetch', return_value=[],), patch(
        'src.oracles.can_update_rewards',
        return_value=False,
    ), patch('src.oracles.submit_vote') as submit_mock:
        await process_votes()
        submit_mock.assert_not_called()


async def test_basic():
    nonce = random.randint(100, 1000)
    root, wrong_root = faker.eth_proof(), faker.eth_proof()
    ipfs_hash, wrong_ipfs_hash = _get_random_ipfs_hash(), _get_random_ipfs_hash
    ts = random.randint(1600000000, 1700000000)
    oracles = {faker.eth_address(): 'https://example{i}.com' for i in range(5)}
    votes = []
    for i, oracle in enumerate(oracles.keys()):
        votes.append(
            RewardVote(
                oracle_address=oracle,
                nonce=nonce,
                update_timestamp=Timestamp(ts),
                signature=random.randbytes(16),
                root=HexStr(root) if not i % 2 else HexStr(wrong_root),
                ipfs_hash=ipfs_hash if not i % 2 else wrong_ipfs_hash,
            )
        )
    signatures = b''
    for vote in sorted(votes, key=lambda x: x.oracle_address):
        if vote.root == root:
            signatures += vote.signature

    with patch('src.oracles._aiohttp_fetch', return_value=[],), patch(
        'src.oracles.can_update_rewards',
        return_value=True,
    ), patch('src.oracles.get_keeper_rewards_nonce', return_value=nonce,), patch(
        'src.oracles.get_oracles_threshold',
        return_value=3,
    ), patch(
        'src.oracles.get_oracles',
        return_value=oracles,
    ), patch(
        'src.oracles.fetch_reward_votes',
        return_value=votes,
    ), patch(
        'src.oracles.submit_vote',
        return_value=None,
    ) as submit_mock:
        await process_votes()

        submit_mock.assert_called_once_with(
            rewards_root=root,
            update_timestamp=ts,
            rewards_ipfs_hash=ipfs_hash,
            signatures=signatures,
        )


def _get_random_ipfs_hash():
    return ''.join(
        random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits)
        for _ in range(46)
    )
