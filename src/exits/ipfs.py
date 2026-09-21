import asyncio
import logging

from eth_typing.bls import BLSPubkey

from src.common.clients import ipfs_fetch_client

logger = logging.getLogger(__name__)

METADATA_LENGTH = 12
PUBLIC_KEY_LENGTH = 48
VALIDATOR_INDEX_LENGTH = 8

# Encrypted exit signature shards keyed by validator public key, ordered by share index
EncryptedExitSignatureShards = dict[BLSPubkey, list[bytes]]


async def fetch_exit_signature_shards(
    ipfs_hashes: set[str],
) -> dict[str, EncryptedExitSignatureShards]:
    """
    Fetches and parses exit signature uploads.
    Uploads that fail to fetch, fail CID verification or can't be parsed are omitted.
    """
    sorted_hashes = sorted(ipfs_hashes)
    results = await asyncio.gather(
        *(_fetch_and_parse_exit_signature_shards(ipfs_hash) for ipfs_hash in sorted_hashes),
        return_exceptions=True,
    )
    exit_signature_shards: dict[str, EncryptedExitSignatureShards] = {}
    for ipfs_hash, result in zip(sorted_hashes, results):
        if isinstance(result, Exception):
            logger.warning(
                'Failed to fetch exit signatures from IPFS %s: %s', ipfs_hash, repr(result)
            )
            continue
        if isinstance(result, BaseException):
            # Re-raise system-exiting exceptions
            raise result
        exit_signature_shards[ipfs_hash] = result
    return exit_signature_shards


async def _fetch_and_parse_exit_signature_shards(ipfs_hash: str) -> EncryptedExitSignatureShards:
    # The fetch client verifies the content against the CID
    data = await ipfs_fetch_client.fetch_bytes(ipfs_hash)
    return parse_exit_signature_shards(data)


def parse_exit_signature_shards(data: bytes) -> EncryptedExitSignatureShards:
    """
    Parses exit signatures upload:
    shards count (2) + shard length (2) + oracles config epoch (8),
    then per validator: public key (48) + [validator index (8)] + shards.
    """
    shards_count = int.from_bytes(data[:2], byteorder='big')
    shard_length = int.from_bytes(data[2:4], byteorder='big')
    body_length = len(data) - METADATA_LENGTH

    length_per_validator = PUBLIC_KEY_LENGTH + shard_length * shards_count
    shards_offset = PUBLIC_KEY_LENGTH
    if body_length % length_per_validator != 0:
        # newer format also contains validator index
        length_per_validator += VALIDATOR_INDEX_LENGTH
        shards_offset += VALIDATOR_INDEX_LENGTH

    if body_length < 0 or body_length % length_per_validator != 0:
        raise ValueError('Unknown exit signatures IPFS data format')

    shards: EncryptedExitSignatureShards = {}
    for validator_start in range(METADATA_LENGTH, len(data), length_per_validator):
        public_key = BLSPubkey(data[validator_start : validator_start + PUBLIC_KEY_LENGTH])
        shards_start = validator_start + shards_offset
        shards_end = validator_start + length_per_validator
        shards[public_key] = [
            data[shard_start : shard_start + shard_length]
            for shard_start in range(shards_start, shards_end, shard_length)
        ]
    return shards
