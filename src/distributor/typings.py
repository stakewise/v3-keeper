from dataclasses import dataclass

from eth_typing import ChecksumAddress, HexStr


@dataclass(frozen=True)
class DistributorRewardVoteBody:
    """
    Represents data sent with set-rewards-root transaction, not including signatures
    """

    root: HexStr
    ipfs_hash: str


@dataclass
class DistributorRewardVote:
    oracle_address: ChecksumAddress
    nonce: int
    signature: HexStr
    body: DistributorRewardVoteBody
