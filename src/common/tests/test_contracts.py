from unittest.mock import AsyncMock, patch

from eth_typing import BlockNumber
from web3.types import EventData

from src.common.contracts import keeper_contract


class TestGetConfigUpdateEvent:
    async def test_returns_recent_event(self):
        """When _get_last_event finds an event, return it directly."""
        expected_event = EventData(
            event='ConfigUpdated',
            args={'foo': 'bar'},
            blockNumber=BlockNumber(99999),
        )

        with patch.object(
            keeper_contract, '_get_last_event', new_callable=AsyncMock, return_value=expected_event
        ) as mock_last_event, patch('src.common.contracts.execution_client') as mock_client, patch(
            'src.common.contracts.NETWORK_CONFIG'
        ) as mock_config:
            mock_client.eth.get_block_number = AsyncMock(return_value=BlockNumber(100000))
            mock_config.CONFIG_UPDATED_CHECKPOINT_BLOCK = BlockNumber(90000)
            mock_config.CONFIG_UPDATED_EVENT_BLOCK = BlockNumber(80000)

            result = await keeper_contract.get_config_update_event()

        assert result is expected_event
        mock_last_event.assert_awaited_once_with(
            event_name='ConfigUpdated',
            from_block=BlockNumber(90001),
            to_block=BlockNumber(100000),
        )

    async def test_falls_back_to_cached_block(self):
        """When _get_last_event returns None, query the cached event block."""
        cached_event = EventData(
            event='ConfigUpdated',
            args={'foo': 'cached'},
            blockNumber=BlockNumber(80000),
        )

        mock_get_logs = AsyncMock(return_value=[cached_event])

        with patch.object(
            keeper_contract, '_get_last_event', new_callable=AsyncMock, return_value=None
        ), patch.object(
            keeper_contract.contract.events.ConfigUpdated, 'get_logs', mock_get_logs
        ), patch(
            'src.common.contracts.execution_client'
        ) as mock_client, patch(
            'src.common.contracts.NETWORK_CONFIG'
        ) as mock_config:
            mock_client.eth.get_block_number = AsyncMock(return_value=BlockNumber(100000))
            mock_config.CONFIG_UPDATED_CHECKPOINT_BLOCK = BlockNumber(90000)
            mock_config.CONFIG_UPDATED_EVENT_BLOCK = BlockNumber(80000)

            result = await keeper_contract.get_config_update_event()

        assert result is cached_event
        mock_get_logs.assert_awaited_once_with(
            from_block=BlockNumber(80000),
            to_block=BlockNumber(80000),
        )

    async def test_returns_none_when_no_events(self):
        """When neither _get_last_event nor cached block has events, return None."""
        with patch.object(
            keeper_contract, '_get_last_event', new_callable=AsyncMock, return_value=None
        ), patch.object(
            keeper_contract.contract.events.ConfigUpdated,
            'get_logs',
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            'src.common.contracts.execution_client'
        ) as mock_client, patch(
            'src.common.contracts.NETWORK_CONFIG'
        ) as mock_config:
            mock_client.eth.get_block_number = AsyncMock(return_value=BlockNumber(100000))
            mock_config.CONFIG_UPDATED_CHECKPOINT_BLOCK = BlockNumber(90000)
            mock_config.CONFIG_UPDATED_EVENT_BLOCK = BlockNumber(80000)

            result = await keeper_contract.get_config_update_event()

        assert result is None

    async def test_cached_block_returns_last_event(self):
        """When multiple events exist at the cached block, return the last one."""
        event1 = EventData(event='ConfigUpdated', args={'v': 1}, blockNumber=BlockNumber(80000))
        event2 = EventData(event='ConfigUpdated', args={'v': 2}, blockNumber=BlockNumber(80000))

        with patch.object(
            keeper_contract, '_get_last_event', new_callable=AsyncMock, return_value=None
        ), patch.object(
            keeper_contract.contract.events.ConfigUpdated,
            'get_logs',
            new_callable=AsyncMock,
            return_value=[event1, event2],
        ), patch(
            'src.common.contracts.execution_client'
        ) as mock_client, patch(
            'src.common.contracts.NETWORK_CONFIG'
        ) as mock_config:
            mock_client.eth.get_block_number = AsyncMock(return_value=BlockNumber(100000))
            mock_config.CONFIG_UPDATED_CHECKPOINT_BLOCK = BlockNumber(90000)
            mock_config.CONFIG_UPDATED_EVENT_BLOCK = BlockNumber(80000)

            result = await keeper_contract.get_config_update_event()

        assert result is event2
