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
