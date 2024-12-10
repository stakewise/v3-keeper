import random
import string
from unittest import mock
from unittest.mock import patch

import pytest
from eth_typing import HexStr
from sw_utils.tests.factories import faker, get_mocked_protocol_config
from sw_utils.typings import Oracle
from web3 import Web3
from web3.types import Timestamp

from src.rewards import (
    RewardsCache,
    _fetch_reward_votes,
    _fetch_vote_from_oracle,
    keeper_contract,
    process_rewards,
)
from src.tests.factories import create_oracle, create_vote
from src.typings import RewardVote, RewardVoteBody

pytestmark = pytest.mark.asyncio


async def test_early():
    with patch(
        'src.rewards.aiohttp_fetch',
        return_value=[],
    ), patch.object(
        keeper_contract,
        'can_update_rewards',
        return_value=False,
    ), patch('src.rewards.submit_vote') as submit_mock:
        await process_rewards(
            get_mocked_protocol_config(oracles_count=5), rewards_cache=RewardsCache()
        )
        submit_mock.assert_not_called()


async def test_basic():
    nonce = random.randint(100, 1000)
    root, wrong_root = faker.eth_proof(), faker.eth_proof()
    ipfs_hash, wrong_ipfs_hash = _get_random_ipfs_hash(), _get_random_ipfs_hash
    ts = Timestamp(random.randint(1600000000, 1700000000))
    oracles = [
        Oracle(public_key=faker.ecies_public_key(), endpoints=[f'https://example{i}.com'])
        for i in range(5)
    ]
    votes = []
    for index, oracle in enumerate(oracles):
        votes.append(
            RewardVote(
                oracle_address=oracle.address,
                nonce=nonce,
                signature=random.randbytes(16),
                body=RewardVoteBody(
                    update_timestamp=Timestamp(ts),
                    root=HexStr(root) if not index % 2 else HexStr(wrong_root),
                    ipfs_hash=ipfs_hash if not index % 2 else wrong_ipfs_hash,
                    avg_reward_per_second=1000,
                ),
            )
        )
    signatures = b''
    for vote in sorted(votes, key=lambda x: Web3.to_int(hexstr=x.oracle_address)):
        if vote.body.root == root:
            signatures += vote.signature

    with patch('src.rewards.aiohttp_fetch', return_value=[]), patch.object(
        keeper_contract,
        'can_update_rewards',
        return_value=True,
    ), patch.object(keeper_contract, 'get_rewards_nonce', return_value=nonce), patch(
        'src.rewards._fetch_reward_votes',
        return_value=votes,
    ), patch(
        'src.rewards.distribute_json_hash', return_value=None
    ), patch(
        'src.rewards.submit_vote',
    ) as submit_mock:
        await process_rewards(
            get_mocked_protocol_config(oracles=oracles, rewards_threshold=3),
            rewards_cache=RewardsCache(),
        )

        submit_mock.assert_called_once_with(
            RewardVoteBody(
                root=root, avg_reward_per_second=1000, update_timestamp=ts, ipfs_hash=ipfs_hash
            ),
            signatures=signatures,
        )


class TestFetchRewardVotes:
    async def test_fetch_reward_votes(self):
        oracles = [
            Oracle(public_key=faker.ecies_public_key(), endpoints=[f'https://example{i}.com'])
            for i in range(5)
        ]
        vote_1 = create_vote(oracle=oracles[1])
        vote_2 = create_vote(oracle=oracles[2])
        vote_3 = create_vote(oracle=oracles[3])

        with mock.patch(
            'src.rewards._fetch_vote_from_endpoint',
            side_effect=[RuntimeError(), vote_1, vote_2, vote_3, RuntimeError()],
        ):
            votes = await _fetch_reward_votes(oracles)

        assert {v.signature for v in votes} == {v.signature for v in (vote_1, vote_2, vote_3)}


class TestFetchVoteFromOracle:
    async def test_all_endpoints_unavailable(self, client_session):
        oracle = create_oracle(num_endpoints=3)

        with mock.patch(
            'src.rewards._fetch_vote_from_endpoint', side_effect=RuntimeError()
        ), pytest.raises(RuntimeError):
            await _fetch_vote_from_oracle(client_session, oracle)

    async def test_single_endpoint_available(self, client_session):
        oracle = create_oracle(num_endpoints=3)
        vote = create_vote(oracle=oracle)

        with mock.patch(
            'src.rewards._fetch_vote_from_endpoint',
            side_effect=[
                RuntimeError(),
                RuntimeError(),
                vote,
            ],
        ):
            fetched_vote = await _fetch_vote_from_oracle(client_session, oracle)

        assert fetched_vote == vote

    async def test_max_nonce(self, client_session):
        oracle = create_oracle(num_endpoints=4)
        vote_1 = create_vote(oracle=oracle, nonce=5)
        vote_2 = create_vote(oracle=oracle, nonce=6)
        vote_3 = create_vote(oracle=oracle, nonce=5)

        with mock.patch(
            'src.rewards._fetch_vote_from_endpoint',
            side_effect=[RuntimeError(), vote_1, vote_2, vote_3],
        ):
            fetched_vote = await _fetch_vote_from_oracle(client_session, oracle)

        assert fetched_vote == vote_2

    async def test_max_nonce_max_timestamp(self, client_session):
        oracle = create_oracle(num_endpoints=4)
        vote_1 = create_vote(oracle=oracle, nonce=5)
        vote_2 = create_vote(
            oracle=oracle, nonce=5, update_timestamp=Timestamp(vote_1.body.update_timestamp + 1)
        )
        vote_3 = create_vote(oracle=oracle, nonce=5, update_timestamp=vote_1.body.update_timestamp)

        with mock.patch(
            'src.rewards._fetch_vote_from_endpoint',
            side_effect=[RuntimeError(), vote_1, vote_2, vote_3],
        ):
            fetched_vote = await _fetch_vote_from_oracle(client_session, oracle)

        assert fetched_vote == vote_2


def _get_random_ipfs_hash():
    return ''.join(
        random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits)
        for _ in range(46)
    )
