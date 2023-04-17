import logging

from aiohttp import ClientSession
from eth_typing import HexStr
from sw_utils.decorators import backoff_aiohttp_errors

from src.clients import consensus_client
from src.config.settings import CONSENSUS_ENDPOINT, DEFAULT_RETRY_TIME

logger = logging.getLogger(__name__)


@backoff_aiohttp_errors(max_time=DEFAULT_RETRY_TIME)
async def submit_voluntary_exit(epoch: int, validator_index: int, signature: HexStr) -> None:
    endpoint = f'{CONSENSUS_ENDPOINT}/eth/v1/beacon/pool/voluntary_exits'
    data = {
        'message': {
            'epoch': str(epoch),
            'validator_index': str(validator_index)
        },
        'signature': signature
    }
    async with ClientSession() as session:
        async with session.post(endpoint, json=data) as response:
            response.raise_for_status()


@backoff_aiohttp_errors(max_time=DEFAULT_RETRY_TIME)
async def get_finality_epoch() -> int:
    checkpoints = await consensus_client.get_finality_checkpoint()
    return int(checkpoints['data']['finalized']['epoch'])
