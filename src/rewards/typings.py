from dataclasses import dataclass

from eth_typing import ChecksumAddress, HexStr
from web3.types import Timestamp


@dataclass(frozen=True)
class RewardVoteBody:
    """
    Represents data sent with update-rewards-root transaction, not including signatures
    """

    update_timestamp: Timestamp
    root: HexStr
    ipfs_hash: str
    avg_reward_per_second: int


@dataclass
class RewardVote:
    oracle_address: ChecksumAddress
    nonce: int
    signature: bytes
    body: RewardVoteBody
