import random

from eth_typing import HexStr
from sw_utils.tests.factories import faker
from sw_utils.typings import Oracle
from web3.types import Timestamp

from src.distributor.typings import DistributorRewardVote, DistributorRewardVoteBody
from src.tests.factories import create_oracle


def create_distributor_reward_vote(
    oracle: Oracle | None = None,
    nonce: int | None = None,
    update_timestamp: Timestamp | None = None,
    root: HexStr | None = None,
    ipfs_hash: str | None = None,
) -> DistributorRewardVote:
    oracle = oracle or create_oracle()
    nonce = nonce or random.randint(1, 1000)
    update_timestamp = update_timestamp or Timestamp(random.randint(100, 10000))

    return DistributorRewardVote(
        oracle_address=oracle.address,
        nonce=nonce,
        update_timestamp=update_timestamp,
        signature=faker.account_signature(),
        body=DistributorRewardVoteBody(
            root=root or faker.eth_proof(),
            ipfs_hash=ipfs_hash or faker.ipfs_hash(),
        ),
    )
