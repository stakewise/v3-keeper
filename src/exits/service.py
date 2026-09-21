import asyncio
import itertools
import logging
from collections import Counter, defaultdict
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientSession
from eth_typing.bls import BLSPubkey, BLSSignature
from pydantic import TypeAdapter
from sw_utils import ValidatorStatus, get_chain_latest_head, is_valid_exit_signature
from sw_utils.typings import Oracle, ProtocolConfig
from web3 import Web3
from web3.types import HexStr

from src.common.clients import consensus_client
from src.common.utils import aiohttp_fetch
from src.config.settings import NETWORK, NETWORK_CONFIG, VALIDATORS_FETCH_CHUNK_SIZE
from src.exits.crypto import (
    decrypt_shard_with_aes_key,
    reconstruct_shared_bls_signature,
)
from src.exits.ipfs import EncryptedExitSignatureShards, fetch_exit_signature_shards
from src.exits.schemas import OracleValidatorExit
from src.exits.typings import ValidatorExitShare
from src.metrics import metrics

logger = logging.getLogger(__name__)

EXIT_VOTE_URL_PATH = '/exits'

EXITING_STATUSES = [
    ValidatorStatus.ACTIVE_EXITING,
    ValidatorStatus.EXITED_UNSLASHED,
    ValidatorStatus.EXITED_SLASHED,
    ValidatorStatus.WITHDRAWAL_POSSIBLE,
    ValidatorStatus.WITHDRAWAL_DONE,
]

oracle_exits_adapter = TypeAdapter(list[OracleValidatorExit])


async def process_exits(protocol_config: ProtocolConfig) -> None:
    chain_head = await get_chain_latest_head(
        consensus_client=consensus_client, slots_per_epoch=NETWORK_CONFIG.SLOTS_PER_EPOCH
    )

    metrics.epoch.labels(network=NETWORK).set(chain_head.epoch)
    metrics.consensus_block.labels(network=NETWORK).set(chain_head.slot)
    metrics.execution_block.labels(network=NETWORK).set(chain_head.block_number)
    metrics.execution_ts.labels(network=NETWORK).set(chain_head.execution_ts)

    validator_exits = await _fetch_validator_exits(protocol_config.oracles)
    validator_indexes = [str(x) for x in validator_exits.keys()]
    exited_statuses = [x.value for x in EXITING_STATUSES]

    validator_pubkeys: dict[int, BLSPubkey] = {}
    for validator_index_batch in itertools.batched(validator_indexes, VALIDATORS_FETCH_CHUNK_SIZE):
        validators_batch = await consensus_client.get_validators_by_ids(
            validator_ids=validator_index_batch,
            state_id=str(chain_head.slot),
        )
        for validator in validators_batch['data']:
            index = int(validator['index'])
            if validator['status'] in exited_statuses:
                validator_exits.pop(index, None)
                continue
            validator_pubkeys[index] = BLSPubkey(
                Web3.to_bytes(hexstr=HexStr(validator['validator']['pubkey']))
            )

    if not validator_exits:
        return

    validator_exits = {
        validator_index: _filter_by_winning_ipfs_hash(validator_index, shares)
        for validator_index, shares in validator_exits.items()
    }
    # One upload covers many validators: fetch each of them once
    # todo rename and rework to (ipfs hash, pub key)
    ipfs_hashes = {share.ipfs_hash for shares in validator_exits.values() for share in shares}
    encrypted_shares = await fetch_exit_signature_shards(ipfs_hashes)

    submitted_count = 0
    for validator_index, shares in validator_exits.items():
        logger.info('Exiting %s validator', validator_index)
        try:
            submitted = await _process_validator_exit_shares(
                validator_index=validator_index,
                shares=shares,
                protocol_config=protocol_config,
                public_key=validator_pubkeys.get(validator_index),
                encrypted_shares=encrypted_shares,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.exception('Failed to process exit for validator %s: %s', validator_index, e)
            continue
        if submitted:
            submitted_count += 1

    logger.info('Processed %s validator exits, %s submitted', len(validator_exits), submitted_count)


async def _process_validator_exit_shares(
    validator_index: int,
    shares: list[ValidatorExitShare],
    protocol_config: ProtocolConfig,
    public_key: BLSPubkey | None,
    encrypted_shares: dict[str, EncryptedExitSignatureShards],
) -> bool:
    if public_key is None:
        logger.warning(
            'Missing consensus validator pubkey for validator %s, skipping...', validator_index
        )
        return False

    verified_shares = _verify_exit_shares(
        validator_index=validator_index,
        shares=shares,
        public_key=public_key,
        encrypted_shares=encrypted_shares,
    )
    if len(verified_shares) < protocol_config.exit_signature_recover_threshold:
        logger.warning(
            'Not enough exit signature shares for validator %s, skipping...', validator_index
        )
        return False

    exit_signature = reconstruct_shared_bls_signature(verified_shares)
    # Verified shares can still be wrong if oracles collude on a fake upload
    if not _is_valid_exit_signature(validator_index, public_key, exit_signature):
        logger.error('Failed to recover a valid exit signature for validator %s', validator_index)
        return False

    submitted = await _submit_signature(
        validator_index=validator_index,
        exit_signature=Web3.to_hex(exit_signature),
    )
    if submitted:
        logger.info('Validator %s exit successfully initiated', validator_index)
    return submitted


async def _fetch_validator_exits(oracles: list[Oracle]) -> dict[int, list[ValidatorExitShare]]:
    async with ClientSession() as session:
        results = await asyncio.gather(
            *[_fetch_exit_shares_from_oracle(session=session, oracle=oracle) for oracle in oracles],
            return_exceptions=True,
        )
    validator_exits = defaultdict(list)
    for result in results:
        if isinstance(result, Exception):
            logger.warning(result)
            continue
        if isinstance(result, BaseException):
            # Re-raise system-exiting exceptions
            raise result

        if result:
            for validator_exit in result:
                validator_exits[validator_exit.validator_index].append(validator_exit)

    return validator_exits


async def _fetch_exit_shares_from_oracle(
    session: ClientSession, oracle: Oracle
) -> list[ValidatorExitShare]:
    results = await asyncio.gather(
        *(
            _fetch_exit_shares_from_endpoint(session, oracle, endpoint)
            for endpoint in oracle.endpoints
        ),
        return_exceptions=True,
    )
    for endpoint, result in zip(oracle.endpoints, results):
        if isinstance(result, Exception):
            logger.warning('%s from %s', repr(result), endpoint)
            continue
        if isinstance(result, BaseException):
            # Re-raise system-exiting exceptions
            raise result
        if result:
            return result
    return []


async def _fetch_exit_shares_from_endpoint(
    session: ClientSession, oracle: Oracle, endpoint: str
) -> list[ValidatorExitShare]:
    url = urljoin(endpoint, EXIT_VOTE_URL_PATH)
    data = await aiohttp_fetch(session, url)
    if not data:
        return []

    # Malformed responses raise `pydantic.ValidationError`, rejecting the whole response.
    oracle_exits = oracle_exits_adapter.validate_python(data)

    exits: list[ValidatorExitShare] = []
    seen_validator_indexes: set[int] = set()
    duplicates_found = False
    for oracle_exit in oracle_exits:
        if oracle_exit.validator_index in seen_validator_indexes:
            duplicates_found = True
            continue
        seen_validator_indexes.add(oracle_exit.validator_index)

        exits.append(
            ValidatorExitShare(
                validator_index=oracle_exit.validator_index,
                exit_signature_share=oracle_exit.exit_signature_share,
                share_index=oracle_exit.share_index,
                oracle_address=oracle.address,
                ipfs_hash=oracle_exit.ipfs_hash,
                shard_key=oracle_exit.shard_key,
            )
        )

    if duplicates_found:
        logger.warning(
            'Duplicate validator exit shares in oracle response', extra={'oracle': oracle.address}
        )

    metrics.processed_exits.labels(network=NETWORK).inc(len(exits))

    return exits


def _filter_by_winning_ipfs_hash(
    validator_index: int, shares: list[ValidatorExitShare]
) -> list[ValidatorExitShare]:
    """
    Keeps shares of the IPFS upload served by the most oracles.
    """
    hash_counter = Counter(share.ipfs_hash for share in shares)
    if len(hash_counter) <= 1:
        return shares

    selected_hash, _ = hash_counter.most_common(1)[0]
    logger.warning(
        'Exit signature shares for validator %s come from different IPFS uploads: %s, using %s',
        validator_index,
        dict(hash_counter),
        selected_hash,
    )
    return [share for share in shares if share.ipfs_hash == selected_hash]


def _verify_exit_shares(
    validator_index: int,
    shares: list[ValidatorExitShare],
    public_key: BLSPubkey,
    encrypted_shares: dict[str, EncryptedExitSignatureShards],
) -> dict[int, BLSSignature]:
    """
    Decrypts every share from its IPFS upload with the shard key served by the oracle.
    Drops shares that can't be decrypted or differ from the oracle response.
    Returns verified shares by share index.
    """
    verified_shares: dict[int, BLSSignature] = {}
    for share in shares:
        error = _get_exit_share_verification_error(
            share=share,
            upload_shards=encrypted_shares.get(share.ipfs_hash),
            public_key=public_key,
        )
        if error:
            logger.warning(
                'Dropped exit signature share for validator %s at share index %s '
                'from oracle %s: %s, ipfs hash %s',
                validator_index,
                share.share_index,
                share.oracle_address,
                error,
                share.ipfs_hash,
            )
            continue
        # Shares with the same share index decrypt to the same shard
        verified_shares[share.share_index] = share.exit_signature_share

    return verified_shares


def _get_exit_share_verification_error(
    share: ValidatorExitShare,
    upload_shards: EncryptedExitSignatureShards | None,
    public_key: BLSPubkey,
) -> str | None:
    if upload_shards is None:
        return 'IPFS upload is unavailable'

    encrypted_shards = upload_shards.get(public_key)
    if encrypted_shards is None:
        return 'validator is missing in IPFS upload'
    if share.share_index >= len(encrypted_shards):
        return 'share index is missing in IPFS upload'

    try:
        decrypted_share = decrypt_shard_with_aes_key(
            aes_key=share.shard_key,
            encrypted_shard=encrypted_shards[share.share_index],
        )
    except ValueError:
        return 'failed to decrypt shard with AES key'

    if decrypted_share != share.exit_signature_share:
        return 'decrypted shard differs from exit signature share'
    return None


def _is_valid_exit_signature(
    validator_index: int, public_key: BLSPubkey, signature: BLSSignature
) -> bool:
    return is_valid_exit_signature(
        validator_index=validator_index,
        public_key=public_key,
        signature=signature,
        genesis_validators_root=NETWORK_CONFIG.GENESIS_VALIDATORS_ROOT,
        fork=NETWORK_CONFIG.SHAPELLA_FORK,
    )


async def _submit_signature(validator_index: int, exit_signature: HexStr) -> bool:
    try:
        await consensus_client.submit_voluntary_exit(
            epoch=NETWORK_CONFIG.SHAPELLA_EPOCH,
            validator_index=validator_index,
            signature=exit_signature,
        )
        return True
    except aiohttp.ClientResponseError as e:
        logger.exception('Failed to process validator %s exit: %s', validator_index, e)
        return False
