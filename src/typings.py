from dataclasses import dataclass

from eth_typing import BlockNumber, ChecksumAddress, HexStr
from eth_typing.bls import BLSSignature
from sw_utils.typings import Bytes32
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


@dataclass
class RewardVote:
    oracle_address: ChecksumAddress
    nonce: int
    update_timestamp: Timestamp
    signature: bytes
    root: HexStr
    ipfs_hash: str


@dataclass
class RewardsRootUpdateParams:
    rewardsRoot: HexStr | Bytes32
    updateTimestamp: Timestamp
    rewardsIpfsHash: str
    signatures: bytes


@dataclass
class ChainHead:
    epoch: int
    consensus_block: int
    execution_block: BlockNumber
    execution_ts: Timestamp
