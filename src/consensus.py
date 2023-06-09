from aiohttp import ClientResponseError, ClientSession
from eth_typing import BlockNumber, HexStr
from sw_utils.decorators import backoff_aiohttp_errors
from web3.types import Timestamp

from src.clients import consensus_client
from src.config.settings import CONSENSUS_ENDPOINT, DEFAULT_RETRY_TIME, NETWORK_CONFIG
from src.typings import ChainHead


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
async def get_chain_finalized_head() -> ChainHead:
    """Fetches the fork safe chain head."""
    checkpoints = await consensus_client.get_finality_checkpoint()
    epoch: int = int(checkpoints['data']['finalized']['epoch'])
    last_slot_id: int = (
        (epoch * NETWORK_CONFIG.SLOTS_PER_EPOCH) + NETWORK_CONFIG.SLOTS_PER_EPOCH - 1
    )
    for i in range(NETWORK_CONFIG.SLOTS_PER_EPOCH):
        try:
            slot = await consensus_client.get_block(last_slot_id - i)
        except ClientResponseError as e:
            if hasattr(e, 'status') and e.status == 404:
                # slot was not proposed, try the previous one
                continue
            raise e

        execution_payload = slot['data']['message']['body']['execution_payload']
        return ChainHead(
            epoch=epoch,
            consensus_block=last_slot_id - i,
            execution_block=BlockNumber(int(execution_payload['block_number'])),
            execution_ts=Timestamp(int(execution_payload['timestamp'])),
        )

    raise RuntimeError(f'Failed to fetch slot for epoch {epoch}')
