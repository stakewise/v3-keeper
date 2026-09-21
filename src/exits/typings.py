from dataclasses import dataclass

from eth_typing import ChecksumAddress
from eth_typing.bls import BLSSignature


@dataclass
class ValidatorExitShare:
    validator_index: int
    exit_signature_share: BLSSignature
    # Position of the shard in the IPFS upload, as reported by the oracle.
    share_index: int
    # Oracle that served the shard. Not derivable from `share_index`: the upload
    # position is historical and the serving oracle may sit elsewhere in the
    # current config, or hold the shard through a legacy key.
    oracle_address: ChecksumAddress
    # IPFS upload holding the encrypted shard.
    ipfs_hash: str
    # One-time AES key of the shard, not the oracle private key.
    # Lets the keeper decrypt the shard from the IPFS upload.
    shard_key: bytes
