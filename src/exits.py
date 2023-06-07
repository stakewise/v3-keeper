import asyncio
import logging
from collections import defaultdict
from urllib.parse import urljoin

import aiohttp
from eth_typing.bls import BLSSignature
from sw_utils import ValidatorStatus
from web3 import Web3

from src.clients import consensus_client
from src.common import aiohttp_fetch
from src.config.settings import VALIDATORS_FETCH_CHUNK_SIZE
from src.consensus import (
    get_chain_finalized_head,
    submit_voluntary_exit,
)
from src.crypto import reconstruct_shared_bls_signature
from src.typings import Oracle, ValidatorExitShare

logger = logging.getLogger(__name__)

EXIT_VOTE_URL_PATH = '/exits/'

EXITING_STATUSES = [
    ValidatorStatus.ACTIVE_EXITING,
    ValidatorStatus.EXITED_UNSLASHED,
    ValidatorStatus.EXITED_SLASHED,
    ValidatorStatus.WITHDRAWAL_POSSIBLE,
    ValidatorStatus.WITHDRAWAL_DONE,
]


async def process_exits(oracles: list[Oracle], threshold: int) -> None:
    chain_head = await get_chain_finalized_head()
    validator_exits = await _fetch_validator_exits(oracles)
    validator_indexes = [str(x) for x in validator_exits.keys()]
    exited_statuses = [x.value for x in EXITING_STATUSES]
    for i in range(0, len(validator_indexes), VALIDATORS_FETCH_CHUNK_SIZE):
        validators_batch = await consensus_client.get_validators_by_ids(
            validator_ids=validator_indexes[i: i + VALIDATORS_FETCH_CHUNK_SIZE],
            state_id=str(chain_head.consensus_block),
        )
        for validator in validators_batch['data']:
            if validator.get('status') in exited_statuses:
                del validator_exits[int(validator.get('index'))]

    if not validator_exits:
        return

    for validator_index, shares in validator_exits.items():
        logger.info('Exiting %s validator', validator_index)

        if len(shares) < threshold:
            logger.warning(
                'Not enough exit signature shares for validator %s, skipping...',
                validator_index
            )
            return

        signatures = {}
        for share in shares:
            signatures[share.share_index] = share.exit_signature_share
        exit_signature = reconstruct_shared_bls_signature(signatures)

        await submit_voluntary_exit(
            epoch=0,
            validator_index=validator_index,
            signature=Web3.to_hex(exit_signature)
        )
        logger.info('Validator %s exit successfully initiated', validator_index)

    logger.info('Validator exits has been successfully processed')


async def _fetch_validator_exits(oracles: list[Oracle]) -> dict[int, list[ValidatorExitShare]]:
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(
            *[
                _fetch_exit_shares(
                    session=session,  oracle=oracle
                )
                for oracle in oracles
            ],
            return_exceptions=True
        )

    validator_exits = defaultdict(list)
    for result in results:
        if isinstance(result, Exception):
            logger.error(result)
            continue

        if result:
            for validator_exit in result:
                validator_exits[validator_exit.validator_index].append(validator_exit)

    return validator_exits


async def _fetch_exit_shares(session, oracle) -> list[ValidatorExitShare]:
    url = urljoin(oracle.endpoint, EXIT_VOTE_URL_PATH)
    data = await aiohttp_fetch(session, url)
    exits = []
    if not data:
        return []
    for exit_data in data:
        for key in ['index', 'exit_signature_share']:
            if key not in exit_data.keys():
                logger.error(
                    'Invalid response from oracle',
                    extra={'oracle': oracle.account, 'response': data}
                )
                return []

        validator_exit = ValidatorExitShare(
            validator_index=exit_data['index'],
            exit_signature_share=BLSSignature(
                Web3.to_bytes(hexstr=exit_data['exit_signature_share'])
            ),
            share_index=oracle.index,
        )
        exits.append(validator_exit)
    return exits
