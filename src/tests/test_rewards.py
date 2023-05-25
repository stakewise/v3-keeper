import random
import string
from unittest.mock import patch

import pytest
from eth_typing import HexStr
from sw_utils.tests import faker
from web3 import Web3
from web3.types import Timestamp

from src.rewards import keeper_contract, process_rewards
from src.typings import Oracle, RewardVote, RewardVoteBody

pytestmark = pytest.mark.asyncio


async def test_early():
    oracles = [
        Oracle(address=faker.eth_address(), endpoint='https://example{i}.com', index=i)
        for i in range(5)
    ]
    with patch(
        'src.rewards.aiohttp_fetch',
        return_value=[],
    ), patch.object(
        keeper_contract, 'can_update_rewards',
        return_value=False,
    ), patch('src.rewards.submit_vote') as submit_mock:
        await process_rewards(oracles, 3)
        submit_mock.assert_not_called()


async def test_basic():
    nonce = random.randint(100, 1000)
    root, wrong_root = faker.eth_proof(), faker.eth_proof()
    ipfs_hash, wrong_ipfs_hash = _get_random_ipfs_hash(), _get_random_ipfs_hash
    ts = Timestamp(random.randint(1600000000, 1700000000))
    oracles = [
        Oracle(address=faker.eth_address(), endpoint='https://example{i}.com', index=i)
        for i in range(5)
    ]
    votes = []
    for oracle in oracles:
        votes.append(
            RewardVote(
                oracle_address=oracle.address,
                nonce=nonce,
                signature=random.randbytes(16),
                body=RewardVoteBody(
                    update_timestamp=Timestamp(ts),
                    root=HexStr(root) if not oracle.index % 2 else HexStr(wrong_root),
                    ipfs_hash=ipfs_hash if not oracle.index % 2 else wrong_ipfs_hash,
                    avg_reward_per_second=1000,
                )
            )
        )
    signatures = b''
    for vote in sorted(votes, key=lambda x: Web3.to_int(hexstr=x.oracle_address)):
        if vote.body.root == root:
            signatures += vote.signature

    with patch(
        'src.rewards.aiohttp_fetch', return_value=[]
    ), patch.object(
        keeper_contract, 'can_update_rewards', return_value=True,
    ), patch.object(
        keeper_contract, 'get_rewards_nonce', return_value=nonce
    ), patch(
        'src.rewards._fetch_reward_votes', return_value=votes,
    ), patch(
        'src.rewards.submit_vote', return_value=None,
    ) as submit_mock:
        await process_rewards(oracles, 3)

        submit_mock.assert_called_once_with(
            RewardVoteBody(
                root=root,
                avg_reward_per_second=1000,
                update_timestamp=ts,
                ipfs_hash=ipfs_hash
            ),
            signatures=signatures,
        )


def _get_random_ipfs_hash():
    return ''.join(
        random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits)
        for _ in range(46)
    )
