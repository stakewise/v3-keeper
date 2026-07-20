from eth_typing import BlockNumber
from sw_utils import ProtocolConfig, build_protocol_config

from src.common.clients import execution_client, ipfs_fetch_client
from src.common.contracts import keeper_contract
from src.protocol_config.typings import OraclesCache


async def get_protocol_config() -> ProtocolConfig:
    oracles_cache = OraclesCache()

    # Use the finalized block (not the latest head) so the checkpoint can never
    # advance past a block that could later reorg and drop a ConfigUpdated event.
    # Tradeoff: oracle-set/threshold changes are observed ~2 epochs late; this
    # latency is deliberate, as finalized blocks are safe for the checkpoint cache.
    block = await execution_client.eth.get_block('finalized')
    to_block = block['number']

    if oracles_cache.checkpoint_block is None:
        # Cold cache: full lookup with checkpoint scan and fallback.
        event = await keeper_contract.get_config_update_event(to_block=to_block)
        if not event:
            raise ValueError('Failed to fetch IPFS hash of oracles config')
        config = await ipfs_fetch_client.fetch_json(event['args']['configIpfsHash'])
    else:
        # Warm cache: only scan blocks added since the last checkpoint.
        from_block = BlockNumber(oracles_cache.checkpoint_block + 1)
        event = None
        if from_block <= to_block:
            event = await keeper_contract.get_config_update_event(
                from_block=from_block,
                to_block=to_block,
            )
        if event is not None:
            config = await ipfs_fetch_client.fetch_json(event['args']['configIpfsHash'])
        else:
            config = oracles_cache.config

    rewards_threshold = await keeper_contract.get_rewards_threshold()

    oracles_cache.checkpoint_block = to_block
    oracles_cache.config = config
    oracles_cache.rewards_threshold = rewards_threshold

    return build_protocol_config(
        config_data=config,
        rewards_threshold=rewards_threshold,
    )
