import random
from contextlib import contextmanager
from unittest import mock
from unittest.mock import patch

import pytest
from eth_typing import HexStr
from sw_utils.tests.factories import faker, get_mocked_protocol_config
from sw_utils.typings import Oracle
from web3 import Web3
from web3.types import Timestamp

from src.distributor.service import (
    _fetch_distributor_reward_votes,
    _fetch_vote_from_oracle,
    merkle_distributor_contract,
    process_distributor_rewards,
)
from src.distributor.tests.factories import create_distributor_reward_vote
from src.distributor.typings import DistributorRewardVote, DistributorRewardVoteBody
from src.tests.factories import create_oracle


async def test_oracles_did_not_vote():
    with patch(
        'src.distributor.service.aiohttp_fetch',
        return_value=[],
    ), patch('src.distributor.service._submit_distributor_rewards_vote') as submit_mock:
        await process_distributor_rewards(get_mocked_protocol_config(oracles_count=5))
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
            DistributorRewardVote(
                oracle_address=oracle.address,
                nonce=nonce,
                update_timestamp=Timestamp(ts),
                signature=faker.account_signature(),
                body=DistributorRewardVoteBody(
                    root=HexStr(root) if not index % 2 else HexStr(wrong_root),
                    ipfs_hash=ipfs_hash if not index % 2 else wrong_ipfs_hash,
                ),
            )
        )
    signatures = []
    for vote in sorted(votes, key=lambda x: Web3.to_int(hexstr=x.oracle_address)):
        if vote.body.root == root:
            signatures.append(vote.signature)

    with (
        patch_distributor_contract(next_update_ts=ts - 100, nonce=nonce, rewards_min_oracles=3),
        patch(
            'src.distributor.service._fetch_distributor_reward_votes',
            return_value=votes,
        ),
        patch('src.distributor.service._submit_distributor_rewards_vote') as submit_mock,
    ):
        await process_distributor_rewards(
            get_mocked_protocol_config(oracles=oracles, rewards_threshold=3),
        )

        submit_mock.assert_called_once_with(
            DistributorRewardVoteBody(root=root, ipfs_hash=ipfs_hash),
            signatures=signatures,
        )


@contextmanager
def patch_distributor_contract(next_update_ts: Timestamp, nonce: int, rewards_min_oracles: int):
    with (
        patch.object(
            merkle_distributor_contract,
            'get_next_rewards_root_update_timestamp',
            return_value=next_update_ts,
        ),
        patch.object(merkle_distributor_contract, 'nonce', return_value=nonce),
        patch.object(
            merkle_distributor_contract,
            'rewards_min_oracles',
            return_value=rewards_min_oracles,
        ),
        patch.object(
            merkle_distributor_contract,
            'rewards_root',
            return_value=faker.eth_proof(),
        ),
    ):
        yield


class TestFetchDistributorRewardVotes:
    async def test_fetch_distributor_reward_votes(self):
        oracles = [
            Oracle(public_key=faker.ecies_public_key(), endpoints=[f'https://example{i}.com'])
            for i in range(5)
        ]
        vote_1 = create_distributor_reward_vote(oracle=oracles[1])
        vote_2 = create_distributor_reward_vote(oracle=oracles[2])
        vote_3 = create_distributor_reward_vote(oracle=oracles[3])

        with mock.patch(
            'src.distributor.service._fetch_vote_from_endpoint',
            side_effect=[RuntimeError(), vote_1, vote_2, vote_3, RuntimeError()],
        ):
            votes = await _fetch_distributor_reward_votes(oracles)

        assert {v.signature for v in votes} == {v.signature for v in (vote_1, vote_2, vote_3)}


class TestFetchVoteFromOracle:
    async def test_all_endpoints_unavailable(self, client_session):
        oracle = create_oracle(num_endpoints=3)

        with mock.patch(
            'src.distributor.service._fetch_vote_from_endpoint', side_effect=RuntimeError()
        ), pytest.raises(RuntimeError):
            await _fetch_vote_from_oracle(client_session, oracle)

    async def test_single_endpoint_available(self, client_session):
        oracle = create_oracle(num_endpoints=3)
        vote = create_distributor_reward_vote(oracle=oracle)

        with mock.patch(
            'src.distributor.service._fetch_vote_from_endpoint',
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
        vote_1 = create_distributor_reward_vote(oracle=oracle, nonce=5)
        vote_2 = create_distributor_reward_vote(oracle=oracle, nonce=6)
        vote_3 = create_distributor_reward_vote(oracle=oracle, nonce=5)

        with mock.patch(
            'src.distributor.service._fetch_vote_from_endpoint',
            side_effect=[RuntimeError(), vote_1, vote_2, vote_3],
        ):
            fetched_vote = await _fetch_vote_from_oracle(client_session, oracle)

        assert fetched_vote == vote_2
