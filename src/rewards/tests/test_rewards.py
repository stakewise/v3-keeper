import random
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock
from unittest.mock import patch

import pytest
from eth_typing import HexStr
from sw_utils.tests.factories import faker, get_mocked_protocol_config
from sw_utils.typings import Oracle
from web3 import Web3
from web3.types import Timestamp

from src.common.tests.factories import create_oracle
from src.rewards.service import (
    RewardsCache,
    _fetch_reward_votes,
    _fetch_vote_from_oracle,
    keeper_contract,
    process_rewards,
)
from src.rewards.tests.factories import create_vote
from src.rewards.typings import RewardVote, RewardVoteBody


async def test_early():
    with patch('src.rewards.service.aiohttp_fetch', return_value=[]), patch.object(
        keeper_contract,
        'can_update_rewards',
        return_value=False,
    ), patch('src.rewards.service._submit_vote') as submit_mock, patch.object(
        RewardsCache(), 'data', {}
    ):
        await process_rewards(get_mocked_protocol_config(oracles_count=5))
        submit_mock.assert_not_called()


async def test_basic():
    nonce = random.randint(100, 1000)
    root, wrong_root = faker.eth_proof(), faker.eth_proof()
    ipfs_hash, wrong_ipfs_hash = faker.ipfs_hash(), faker.ipfs_hash()
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

    with patch('src.rewards.service.aiohttp_fetch', return_value=[]), patch.object(
        keeper_contract,
        'can_update_rewards',
        return_value=True,
    ), patch.object(keeper_contract, 'get_rewards_nonce', return_value=nonce), patch(
        'src.rewards.service._fetch_reward_votes',
        return_value=votes,
    ), patch(
        'src.rewards.service._submit_vote',
    ) as submit_mock, patch.object(
        RewardsCache(), 'data', {}
    ):
        await process_rewards(
            get_mocked_protocol_config(oracles=oracles, rewards_threshold=3),
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
            'src.rewards.service._fetch_vote_from_endpoint',
            side_effect=[RuntimeError(), vote_1, vote_2, vote_3, RuntimeError()],
        ):
            votes = await _fetch_reward_votes(oracles)

        assert {v.signature for v in votes} == {v.signature for v in (vote_1, vote_2, vote_3)}


class TestFetchVoteFromOracle:
    async def test_all_endpoints_unavailable(self, client_session):
        oracle = create_oracle(num_endpoints=3)

        with mock.patch(
            'src.rewards.service._fetch_vote_from_endpoint', side_effect=RuntimeError()
        ), pytest.raises(RuntimeError):
            await _fetch_vote_from_oracle(client_session, oracle)

    async def test_single_endpoint_available(self, client_session):
        oracle = create_oracle(num_endpoints=3)
        vote = create_vote(oracle=oracle)

        with mock.patch(
            'src.rewards.service._fetch_vote_from_endpoint',
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
            'src.rewards.service._fetch_vote_from_endpoint',
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
            'src.rewards.service._fetch_vote_from_endpoint',
            side_effect=[RuntimeError(), vote_1, vote_2, vote_3],
        ):
            fetched_vote = await _fetch_vote_from_oracle(client_session, oracle)

        assert fetched_vote == vote_2


class TestRewardsCache:
    """
    Ordered, stateful test: each method builds on the cache state left by the
    previous one (pytest runs methods top-down). The class-scoped fixture sets
    up a clean, size-limited cache once and restores it when the class finishes,
    so individual methods don't repeat the patching.
    """

    @pytest.fixture(autouse=True, scope='class')
    def ctx(self):
        cache = RewardsCache()
        ts1 = Timestamp(random.randint(100, 10000))
        ts2 = Timestamp(ts1 + 100)
        ts3 = Timestamp(ts2 + 100)
        namespace = SimpleNamespace(
            cache=cache,
            vote1=create_vote(update_timestamp=ts1),
            vote2=create_vote(update_timestamp=ts2),
            vote3=create_vote(update_timestamp=ts1),
            vote4=create_vote(update_timestamp=ts1),
            vote5=create_vote(update_timestamp=ts2),
            vote6=create_vote(update_timestamp=ts2),
            vote7=create_vote(update_timestamp=ts3),
        )
        namespace.vote8 = deepcopy(namespace.vote7)
        with patch.object(cache, 'data', {}), patch.object(cache, 'cache_size', 2):
            yield namespace

    async def test_empty_initially(self, ctx):
        assert not ctx.cache.rewards()

    async def test_first_vote(self, ctx):
        ctx.cache.update([ctx.vote1])
        assert ctx.cache.rewards() == [[ctx.vote1]]

    async def test_new_timestamp_bucket(self, ctx):
        ctx.cache.update([ctx.vote2])
        assert ctx.cache.rewards() == [[ctx.vote1], [ctx.vote2]]

    async def test_same_timestamp_appends(self, ctx):
        ctx.cache.update([ctx.vote3])
        assert ctx.cache.rewards() == [[ctx.vote1, ctx.vote3], [ctx.vote2]]

    async def test_batch_update(self, ctx):
        ctx.cache.update([ctx.vote4, ctx.vote5, ctx.vote6])
        assert ctx.cache.rewards() == [
            [ctx.vote1, ctx.vote3, ctx.vote4],
            [ctx.vote2, ctx.vote5, ctx.vote6],
        ]

    async def test_evicts_oldest_and_dedups(self, ctx):
        # cache_size is 2: adding a third timestamp evicts the oldest bucket,
        # and the duplicate vote8 is not stored twice.
        ctx.cache.update([ctx.vote7, ctx.vote8])
        assert ctx.cache.rewards() == [[ctx.vote2, ctx.vote5, ctx.vote6], [ctx.vote7]]

    async def test_clear(self, ctx):
        ctx.cache.clear()
        assert not ctx.cache.rewards()
