import random

from eth_typing import HexStr
from sw_utils.tests import faker
from web3.types import Timestamp

from src.typings import Oracle, RewardVote, RewardVoteBody


def create_oracle(num_endpoints: int = 1) -> Oracle:
    return Oracle(
        address=faker.eth_address(),
        endpoints=[f'https://example{i}.com' for i in range(num_endpoints)],
        index=1,
    )


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
