from dataclasses import dataclass

from eth_typing import ChecksumAddress
from eth_typing.bls import BLSSignature


@dataclass
class ValidatorExitShare:
    validator_index: int
    exit_signature_share: BLSSignature
    # Position of the shard in the IPFS blob, as reported by the oracle.
    share_index: int
    # Oracle that served the shard. Not derivable from `share_index`: the blob
    # position is historical and the serving oracle may sit elsewhere in the
    # current config, or hold the shard through a legacy key.
    oracle_address: ChecksumAddress


@dataclass
class SharesCombination:
    # Share indexes taking part in the reconstruction.
    share_indexes: tuple[int, ...]
    # Exit signature shares keyed by share index, as passed to the reconstruction.
    shares_subset: dict[int, BLSSignature]
    # Share indexes left out of this combination.
    excluded_indexes: list[int]
    # Oracles that served the excluded shares.
    excluded_oracles: list[ChecksumAddress]
