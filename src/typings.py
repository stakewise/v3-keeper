from dataclasses import dataclass

from eth_typing import ChecksumAddress, HexStr
from eth_typing.bls import BLSSignature
from web3.types import Timestamp


@dataclass
class Oracle:
    index: int
    endpoints: list[str]
    address: ChecksumAddress


@dataclass
class OracleConfig:
    oracles: list[Oracle]
    exit_signature_recover_threshold: int
    rewards_threshold: int


@dataclass
class ValidatorExitShare:
    validator_index: int
    exit_signature_share: BLSSignature
    share_index: int


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
