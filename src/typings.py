from dataclasses import dataclass

from eth_typing import ChecksumAddress, HexStr
from sw_utils.typings import Bytes32
from web3.types import Timestamp


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
