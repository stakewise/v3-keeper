from unittest.mock import AsyncMock, patch

from eth_typing import BlockNumber
from web3.types import EventData

from src.protocol_config.service import (
    get_protocol_config,
    ipfs_fetch_client,
    keeper_contract,
)
from src.protocol_config.typings import OraclesCache


def _config_event(ipfs_hash: str) -> EventData:
    return EventData(
        event='ConfigUpdated',
        args={'configIpfsHash': ipfs_hash},
        blockNumber=BlockNumber(0),
    )


class TestGetProtocolConfig:
    def setup_method(self) -> None:
        # OraclesCache is a process-wide singleton; reset it between tests.
        oracles_cache = OraclesCache()
        oracles_cache.checkpoint_block = None
        oracles_cache.config = {}
        oracles_cache.rewards_threshold = 0

    async def test_cold_cache_fetches_and_populates(self):
        with patch('src.protocol_config.service.execution_client') as mock_client, patch.object(
            keeper_contract, 'get_config_update_event', new_callable=AsyncMock
        ) as mock_event, patch.object(
            keeper_contract, 'get_rewards_threshold', new_callable=AsyncMock, return_value=7
        ), patch.object(
            ipfs_fetch_client, 'fetch_json', new_callable=AsyncMock, return_value={'k': 'v1'}
        ) as mock_fetch, patch(
            'src.protocol_config.service.build_protocol_config'
        ) as mock_build:
            mock_client.eth.get_block = AsyncMock(return_value={'number': BlockNumber(100)})
            mock_event.return_value = _config_event('hash1')

            await get_protocol_config()

        # Cold path: no from_block, scoped to the finalized block.
        mock_event.assert_awaited_once_with(to_block=BlockNumber(100))
        mock_fetch.assert_awaited_once_with('hash1')
        mock_build.assert_called_once_with(config_data={'k': 'v1'}, rewards_threshold=7)

        oracles_cache = OraclesCache()
        assert oracles_cache.checkpoint_block == BlockNumber(100)
        assert oracles_cache.config == {'k': 'v1'}
        assert oracles_cache.rewards_threshold == 7

    async def test_warm_cache_no_new_event_reuses_config(self):
        oracles_cache = OraclesCache()
        oracles_cache.checkpoint_block = BlockNumber(100)
        oracles_cache.config = {'k': 'cached'}
        oracles_cache.rewards_threshold = 3

        with patch('src.protocol_config.service.execution_client') as mock_client, patch.object(
            keeper_contract, 'get_config_update_event', new_callable=AsyncMock, return_value=None
        ) as mock_event, patch.object(
            keeper_contract, 'get_rewards_threshold', new_callable=AsyncMock, return_value=3
        ), patch.object(
            ipfs_fetch_client, 'fetch_json', new_callable=AsyncMock
        ) as mock_fetch, patch(
            'src.protocol_config.service.build_protocol_config'
        ) as mock_build:
            mock_client.eth.get_block = AsyncMock(return_value={'number': BlockNumber(105)})

            await get_protocol_config()

        # Warm path: incremental scan only, no IPFS fetch when nothing changed.
        mock_event.assert_awaited_once_with(from_block=BlockNumber(101), to_block=BlockNumber(105))
        mock_fetch.assert_not_awaited()
        mock_build.assert_called_once_with(config_data={'k': 'cached'}, rewards_threshold=3)

        assert oracles_cache.checkpoint_block == BlockNumber(105)
        assert oracles_cache.config == {'k': 'cached'}

    async def test_warm_cache_new_event_refetches(self):
        oracles_cache = OraclesCache()
        oracles_cache.checkpoint_block = BlockNumber(100)
        oracles_cache.config = {'k': 'old'}
        oracles_cache.rewards_threshold = 3

        with patch('src.protocol_config.service.execution_client') as mock_client, patch.object(
            keeper_contract, 'get_config_update_event', new_callable=AsyncMock
        ) as mock_event, patch.object(
            keeper_contract, 'get_rewards_threshold', new_callable=AsyncMock, return_value=3
        ), patch.object(
            ipfs_fetch_client, 'fetch_json', new_callable=AsyncMock, return_value={'k': 'new'}
        ) as mock_fetch, patch(
            'src.protocol_config.service.build_protocol_config'
        ):
            mock_client.eth.get_block = AsyncMock(return_value={'number': BlockNumber(110)})
            mock_event.return_value = _config_event('hash2')

            await get_protocol_config()

        mock_event.assert_awaited_once_with(from_block=BlockNumber(101), to_block=BlockNumber(110))
        mock_fetch.assert_awaited_once_with('hash2')

        assert oracles_cache.checkpoint_block == BlockNumber(110)
        assert oracles_cache.config == {'k': 'new'}

    async def test_warm_cache_no_new_block_skips_scan(self):
        oracles_cache = OraclesCache()
        oracles_cache.checkpoint_block = BlockNumber(100)
        oracles_cache.config = {'k': 'cached'}
        oracles_cache.rewards_threshold = 3

        with patch('src.protocol_config.service.execution_client') as mock_client, patch.object(
            keeper_contract, 'get_config_update_event', new_callable=AsyncMock
        ) as mock_event, patch.object(
            keeper_contract, 'get_rewards_threshold', new_callable=AsyncMock, return_value=3
        ), patch.object(
            ipfs_fetch_client, 'fetch_json', new_callable=AsyncMock
        ) as mock_fetch, patch(
            'src.protocol_config.service.build_protocol_config'
        ):
            # Finalized block has not advanced past the checkpoint.
            mock_client.eth.get_block = AsyncMock(return_value={'number': BlockNumber(100)})

            await get_protocol_config()

        mock_event.assert_not_awaited()
        mock_fetch.assert_not_awaited()

        assert oracles_cache.checkpoint_block == BlockNumber(100)
        assert oracles_cache.config == {'k': 'cached'}
