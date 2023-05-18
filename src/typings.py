from dataclasses import dataclass

from eth_typing import BlockNumber, ChecksumAddress, HexStr
from eth_typing.bls import BLSSignature
from web3.types import Timestamp


@dataclass
class Oracle:
    index: int
    endpoint: str
    address: ChecksumAddress


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


@dataclass
class ChainHead:
    epoch: int
    consensus_block: int
    execution_block: BlockNumber
    execution_ts: Timestamp
