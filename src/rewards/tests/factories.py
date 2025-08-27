import random

from eth_typing import HexStr
from sw_utils.typings import Oracle
from web3.types import Timestamp

from src.common.tests.factories import create_oracle
from src.rewards.typings import RewardVote, RewardVoteBody


def create_vote(
    oracle: Oracle | None = None,
    nonce: int | None = None,
    update_timestamp: Timestamp | None = None,
) -> RewardVote:
    oracle = oracle or create_oracle()
    nonce = nonce or random.randint(1, 1000)
    update_timestamp = update_timestamp or Timestamp(random.randint(100, 10000))

    return RewardVote(
        oracle_address=oracle.address,
        nonce=nonce,
        signature=random.randbytes(16),
        body=RewardVoteBody(
            update_timestamp=update_timestamp,
            root=HexStr('0x00'),
            ipfs_hash='ipfs_hash',
            avg_reward_per_second=1000,
        ),
    )
