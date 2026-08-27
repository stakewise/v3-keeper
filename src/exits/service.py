import asyncio
import itertools
import logging
from collections import defaultdict
from collections.abc import Iterator
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientSession
from eth_typing.bls import BLSPubkey, BLSSignature
from py_ecc.bls import G2ProofOfPossession
from sw_utils import ValidatorStatus, get_chain_latest_head, is_valid_exit_signature
from sw_utils.typings import Oracle, ProtocolConfig
from web3 import Web3
from web3.types import ChecksumAddress, HexStr

from src.common.clients import consensus_client
from src.common.utils import aiohttp_fetch
from src.config.settings import NETWORK, NETWORK_CONFIG, VALIDATORS_FETCH_CHUNK_SIZE
from src.exits.crypto import reconstruct_shared_bls_signature
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

# Upper bound on the number of subset-reconstruction attempts per validator when searching
# for a valid signature among poisoned shares; guards against combinatorial blowup.
MAX_EXIT_SIGNATURE_RECOVERY_ATTEMPTS = 500


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
                del validator_exits[index]
                continue
            validator_pubkeys[index] = BLSPubkey(
                Web3.to_bytes(hexstr=HexStr(validator['validator']['pubkey']))
            )

    if not validator_exits:
        return

    submitted_count = 0
    for validator_index, shares in validator_exits.items():
        logger.info('Exiting %s validator', validator_index)
        try:
            submitted = await _process_validator_exit_shares(
                validator_index=validator_index,
                shares=shares,
                protocol_config=protocol_config,
                public_key=validator_pubkeys.get(validator_index),
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.exception('Failed to process exit for validator %s: %s', validator_index, e)
            continue
        if submitted:
            submitted_count += 1

    logger.info('Processed %s validator exits, %s submitted', len(validator_exits), submitted_count)


async def _process_validator_exit_shares(
    validator_index: int,
    shares: dict[int, BLSSignature],
    protocol_config: ProtocolConfig,
    public_key: BLSPubkey | None,
) -> bool:
    if public_key is None:
        logger.warning(
            'Missing consensus validator pubkey for validator %s, skipping...', validator_index
        )
        return False

    if len(shares) < protocol_config.exit_signature_recover_threshold:
        logger.warning(
            'Not enough exit signature shares for validator %s, skipping...', validator_index
        )
        return False

    exit_signature = await asyncio.to_thread(
        _recover_exit_signature,
        validator_index=validator_index,
        shares=shares,
        threshold=protocol_config.exit_signature_recover_threshold,
        public_key=public_key,
        oracles=protocol_config.oracles,
    )
    if exit_signature is None:
        return False

    submitted = await _submit_signature(
        validator_index=validator_index,
        exit_signature=Web3.to_hex(exit_signature),
    )
    if submitted:
        logger.info('Validator %s exit successfully initiated', validator_index)
    return submitted


async def _fetch_validator_exits(oracles: list[Oracle]) -> dict[int, dict[int, BLSSignature]]:
    async with ClientSession() as session:
        results = await asyncio.gather(
            *(_fetch_exit_shares_from_oracle(session=session, oracle=oracle) for oracle in oracles),
            return_exceptions=True,
        )

    validator_exits: dict[int, dict[int, BLSSignature]] = defaultdict(dict)
    for oracle_index, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning(result)
            continue
        if isinstance(result, BaseException):
            # Re-raise system-exiting exceptions
            raise result

        for validator_index, share in result.items():
            validator_exits[validator_index][oracle_index] = share

    return validator_exits


async def _fetch_exit_shares_from_oracle(
    session: ClientSession, oracle: Oracle
) -> dict[int, BLSSignature]:
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
    return {}


async def _fetch_exit_shares_from_endpoint(
    session: ClientSession, oracle: Oracle, endpoint: str
) -> dict[int, BLSSignature]:
    url = urljoin(endpoint, EXIT_VOTE_URL_PATH)
    data = await aiohttp_fetch(session, url)
    exits: dict[int, BLSSignature] = {}
    if not data:
        return exits

    duplicates_found = False
    for exit_data in data:
        for key in ['index', 'exit_signature_share']:
            if key not in exit_data.keys():
                logger.warning(
                    'Invalid response from oracle',
                    extra={'oracle': oracle.address, 'response': data},
                )
                raise RuntimeError(f'Invalid response from endpoint {endpoint}')

        validator_index = int(exit_data['index'])
        share = BLSSignature(Web3.to_bytes(hexstr=exit_data['exit_signature_share']))
        # pylint: disable-next=protected-access
        if not G2ProofOfPossession._is_valid_signature(share):
            logger.warning(
                'Malformed exit signature share in oracle response',
                extra={'oracle': oracle.address, 'validator_index': validator_index},
            )
            _count_invalid_share(oracle.address)
            raise RuntimeError(f'Invalid response from endpoint {endpoint}')

        if validator_index in exits:
            duplicates_found = True
            continue
        exits[validator_index] = share

    if duplicates_found:
        logger.warning(
            'Duplicate validator exit shares in oracle response', extra={'oracle': oracle.address}
        )
        _count_invalid_share(oracle.address)

    metrics.processed_exits.labels(network=NETWORK).inc(len(exits))

    return exits


def _count_invalid_share(oracle_address: ChecksumAddress) -> None:
    metrics.invalid_exit_shares.labels(network=NETWORK, oracle=oracle_address).inc()


def _share_subsets(share_indexes: list[int], threshold: int) -> Iterator[tuple[int, ...]]:
    # Leave-k-out search, largest subsets first: the full share set is tried first (so a
    # single bad oracle is found by the very next size down), and every combination of size
    # >= threshold is eventually tried, so the search is complete. For a single bad oracle
    # this terminates in O(N) attempts instead of enumerating all size-threshold subsets.
    for size in range(len(share_indexes), threshold - 1, -1):
        yield from itertools.combinations(share_indexes, size)


def _reconstruct_and_verify(
    validator_index: int, public_key: BLSPubkey, shares: dict[int, BLSSignature]
) -> BLSSignature | None:
    try:
        candidate_signature = reconstruct_shared_bls_signature(shares)
    except ValueError as e:
        # A non-curve-point share (e.g. malformed bytes with a valid length) makes py_ecc's
        # point decompression raise instead of returning False; treat it the same as a failed
        # verification so leave-k-out excludes it naturally.
        logger.debug(
            'Failed to reconstruct exit signature for validator %s from shares %s: %s',
            validator_index,
            sorted(shares),
            e,
        )
        return None
    if not _is_valid_exit_signature(validator_index, public_key, candidate_signature):
        return None
    return candidate_signature


def _recover_exit_signature(
    validator_index: int,
    shares: dict[int, BLSSignature],
    threshold: int,
    public_key: BLSPubkey,
    oracles: list[Oracle],
) -> BLSSignature | None:
    share_indexes = sorted(shares)

    for combination in itertools.islice(
        _share_subsets(share_indexes, threshold), MAX_EXIT_SIGNATURE_RECOVERY_ATTEMPTS
    ):
        subset = {index: shares[index] for index in combination}
        candidate_signature = _reconstruct_and_verify(validator_index, public_key, subset)
        if candidate_signature is None:
            continue

        excluded_addresses = [
            oracles[index].address for index in share_indexes if index not in combination
        ]
        if excluded_addresses:
            logger.warning(
                'Recovered valid exit signature for validator %s, excluding shares '
                'from oracles %s',
                validator_index,
                excluded_addresses,
            )
            for address in excluded_addresses:
                _count_invalid_share(address)
        return candidate_signature

    logger.error(
        'Failed to recover a valid exit signature for validator %s from %s shares',
        validator_index,
        len(shares),
    )
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
