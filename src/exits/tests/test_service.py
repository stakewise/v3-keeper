import logging
import random
from unittest.mock import AsyncMock, patch

import pytest
from eth_typing import BlockNumber
from eth_typing.bls import BLSSignature
from sw_utils import ChainHead, is_valid_exit_signature
from sw_utils.tests.factories import get_mocked_protocol_config
from sw_utils.typings import ProtocolConfig
from web3 import Web3
from web3.types import Timestamp

from src.common.clients import consensus_client
from src.common.tests.factories import create_oracle
from src.config.settings import NETWORK, NETWORK_CONFIG
from src.exits.crypto import reconstruct_shared_bls_signature
from src.exits.service import (
    _fetch_exit_shares_from_endpoint,
    _recover_exit_signature,
    process_exits,
)
from src.exits.tests.factories import (
    create_exit_shares,
    create_threshold_signature_setup,
    create_validator_data,
    poison_exit_share,
)
from src.exits.typings import ValidatorExitShare
from src.metrics import metrics

CHAIN_HEAD = ChainHead(
    epoch=1, slot=32, block_number=BlockNumber(100), execution_ts=Timestamp(1700000000)
)


async def test_four_of_five_honest_shares_submits_valid_signature():
    validator_index = 100
    protocol_config = get_mocked_protocol_config(
        oracles_count=5, exit_signature_recover_threshold=4
    )
    setup = create_threshold_signature_setup(
        validator_index=validator_index, oracles_count=5, threshold=4
    )
    validator_exits = {validator_index: create_exit_shares(setup, share_indexes=[0, 1, 2, 3])}
    validators_data = [create_validator_data(validator_index, setup.public_key, 'active_ongoing')]

    submit_mock = await _run_process_exits(protocol_config, validator_exits, validators_data)

    submit_mock.assert_called_once()
    assert submit_mock.call_args.kwargs['validator_index'] == validator_index
    assert _signature_is_valid(validator_index, setup.public_key, submit_mock)


async def test_one_poisoned_share_recovered_from_honest_subset(caplog):
    validator_index = 101
    protocol_config = get_mocked_protocol_config(
        oracles_count=5, exit_signature_recover_threshold=4
    )
    setup = create_threshold_signature_setup(
        validator_index=validator_index, oracles_count=5, threshold=4
    )
    honest_shares = create_exit_shares(setup, share_indexes=[0, 1, 2, 3])
    poisoned_share = poison_exit_share(setup, share_index=4)
    validator_exits = {validator_index: honest_shares + [poisoned_share]}
    validators_data = [create_validator_data(validator_index, setup.public_key, 'active_ongoing')]

    with caplog.at_level(logging.WARNING):
        submit_mock = await _run_process_exits(protocol_config, validator_exits, validators_data)

    submit_mock.assert_called_once()
    assert _signature_is_valid(validator_index, setup.public_key, submit_mock)
    poisoned_oracle_address = protocol_config.oracles[4].address
    assert poisoned_oracle_address in caplog.text


async def test_non_curve_share_recovered_from_honest_subset(caplog):
    validator_index = 108
    protocol_config = get_mocked_protocol_config(
        oracles_count=5, exit_signature_recover_threshold=4
    )
    setup = create_threshold_signature_setup(
        validator_index=validator_index, oracles_count=5, threshold=4
    )
    honest_shares = create_exit_shares(setup, share_indexes=[1, 2, 3, 4])
    non_curve_share = ValidatorExitShare(
        validator_index=validator_index,
        exit_signature_share=BLSSignature(bytes([0x00]) + random.randbytes(95)),
        share_index=0,
    )
    validator_exits = {validator_index: honest_shares + [non_curve_share]}
    validators_data = [create_validator_data(validator_index, setup.public_key, 'active_ongoing')]

    with caplog.at_level(logging.WARNING):
        submit_mock = await _run_process_exits(protocol_config, validator_exits, validators_data)

    submit_mock.assert_called_once()
    assert _signature_is_valid(validator_index, setup.public_key, submit_mock)
    non_curve_oracle_address = protocol_config.oracles[0].address
    assert non_curve_oracle_address in caplog.text


async def test_two_poisoned_shares_not_recoverable(caplog):
    validator_index = 102
    protocol_config = get_mocked_protocol_config(
        oracles_count=5, exit_signature_recover_threshold=4
    )
    setup = create_threshold_signature_setup(
        validator_index=validator_index, oracles_count=5, threshold=4
    )
    honest_shares = create_exit_shares(setup, share_indexes=[0, 1, 2])
    poisoned_shares = [
        poison_exit_share(setup, share_index=3),
        poison_exit_share(setup, share_index=4),
    ]
    validator_exits = {validator_index: honest_shares + poisoned_shares}
    validators_data = [create_validator_data(validator_index, setup.public_key, 'active_ongoing')]

    with caplog.at_level(logging.ERROR):
        submit_mock = await _run_process_exits(protocol_config, validator_exits, validators_data)

    submit_mock.assert_not_called()
    assert 'Failed to recover a valid exit signature' in caplog.text


async def test_below_threshold_not_submitted():
    validator_index = 103
    protocol_config = get_mocked_protocol_config(
        oracles_count=5, exit_signature_recover_threshold=4
    )
    setup = create_threshold_signature_setup(
        validator_index=validator_index, oracles_count=5, threshold=4
    )
    validator_exits = {validator_index: create_exit_shares(setup, share_indexes=[0, 1, 2])}
    validators_data = [create_validator_data(validator_index, setup.public_key, 'active_ongoing')]

    submit_mock = await _run_process_exits(protocol_config, validator_exits, validators_data)

    submit_mock.assert_not_called()


async def test_duplicate_share_index_not_counted_toward_threshold():
    validator_index = 104
    protocol_config = get_mocked_protocol_config(
        oracles_count=5, exit_signature_recover_threshold=4
    )
    setup = create_threshold_signature_setup(
        validator_index=validator_index, oracles_count=5, threshold=4
    )
    # 4 shares, but two of them share the same share_index (same oracle) so only 3 are distinct
    shares = create_exit_shares(setup, share_indexes=[0, 1, 2])
    shares.append(create_exit_shares(setup, share_indexes=[2])[0])
    validator_exits = {validator_index: shares}
    validators_data = [create_validator_data(validator_index, setup.public_key, 'active_ongoing')]

    submit_mock = await _run_process_exits(protocol_config, validator_exits, validators_data)

    submit_mock.assert_not_called()


async def test_exiting_validator_skipped():
    validator_index = 105
    protocol_config = get_mocked_protocol_config(
        oracles_count=5, exit_signature_recover_threshold=4
    )
    setup = create_threshold_signature_setup(
        validator_index=validator_index, oracles_count=5, threshold=4
    )
    validator_exits = {validator_index: create_exit_shares(setup, share_indexes=[0, 1, 2, 3])}
    validators_data = [create_validator_data(validator_index, setup.public_key, 'active_exiting')]

    submit_mock = await _run_process_exits(protocol_config, validator_exits, validators_data)

    submit_mock.assert_not_called()


async def test_validator_missing_from_beacon_skipped(caplog):
    validator_index = 106
    protocol_config = get_mocked_protocol_config(
        oracles_count=5, exit_signature_recover_threshold=4
    )
    setup = create_threshold_signature_setup(
        validator_index=validator_index, oracles_count=5, threshold=4
    )
    validator_exits = {validator_index: create_exit_shares(setup, share_indexes=[0, 1, 2, 3])}

    with caplog.at_level(logging.WARNING):
        submit_mock = await _run_process_exits(protocol_config, validator_exits, validators_data=[])

    submit_mock.assert_not_called()
    assert 'Missing consensus validator pubkey' in caplog.text


async def test_process_exits_tolerates_malformed_oracle_response(caplog):
    validator_index = 107
    protocol_config = get_mocked_protocol_config(
        oracles_count=1, exit_signature_recover_threshold=1
    )
    malformed_share = Web3.to_hex(random.randbytes(64))
    data = [{'index': str(validator_index), 'exit_signature_share': malformed_share}]

    with patch('src.exits.service.get_chain_latest_head', return_value=CHAIN_HEAD), patch(
        'src.exits.service.aiohttp_fetch', return_value=data
    ), patch.object(consensus_client, 'get_validators_by_ids', return_value={'data': []}), patch(
        'src.exits.service._submit_signature'
    ) as submit_mock, caplog.at_level(
        logging.WARNING
    ):
        await process_exits(protocol_config)

    submit_mock.assert_not_called()
    assert 'Malformed' in caplog.text


async def test_validator_exit_failure_isolated_from_other_validators(caplog):
    protocol_config = get_mocked_protocol_config(
        oracles_count=5, exit_signature_recover_threshold=4
    )
    validator_exits = {111: [], 112: []}
    validators_data = [
        {
            'index': '111',
            'status': 'active_ongoing',
            'validator': {'pubkey': Web3.to_hex(random.randbytes(48))},
        },
        {
            'index': '112',
            'status': 'active_ongoing',
            'validator': {'pubkey': Web3.to_hex(random.randbytes(48))},
        },
    ]

    with patch('src.exits.service.get_chain_latest_head', return_value=CHAIN_HEAD), patch(
        'src.exits.service._fetch_validator_exits', return_value=validator_exits
    ), patch.object(
        consensus_client, 'get_validators_by_ids', return_value={'data': validators_data}
    ), patch(
        'src.exits.service._process_validator_exit_shares',
        side_effect=[RuntimeError('boom'), True],
    ), caplog.at_level(
        logging.INFO
    ):
        await process_exits(protocol_config)

    assert 'Failed to process exit for validator 111' in caplog.text
    assert 'Processed 2 validator exits, 1 submitted' in caplog.text


class TestFetchExitSharesFromEndpoint:
    async def test_duplicate_validator_index_deduplicated(self, client_session, caplog):
        oracle = create_oracle(num_endpoints=1)
        setup = create_threshold_signature_setup(validator_index=5, oracles_count=1, threshold=1)
        valid_share = Web3.to_hex(setup.shares[0])
        data = [{'index': '5', 'exit_signature_share': valid_share} for _ in range(4)]

        with patch('src.exits.service.aiohttp_fetch', return_value=data), caplog.at_level(
            logging.WARNING
        ):
            shares = await _fetch_exit_shares_from_endpoint(
                session=client_session, oracle=oracle, endpoint=oracle.endpoints[0], oracle_index=2
            )

        assert len(shares) == 1
        assert shares[0].validator_index == 5
        assert shares[0].share_index == 2
        assert 'Duplicate' in caplog.text

    async def test_malformed_share_rejects_whole_response(self, client_session, caplog):
        oracle = create_oracle(num_endpoints=1)
        malformed_share = Web3.to_hex(random.randbytes(64))
        data = [{'index': '7', 'exit_signature_share': malformed_share}]

        with patch('src.exits.service.aiohttp_fetch', return_value=data), caplog.at_level(
            logging.WARNING
        ), pytest.raises(RuntimeError):
            await _fetch_exit_shares_from_endpoint(
                session=client_session, oracle=oracle, endpoint=oracle.endpoints[0], oracle_index=0
            )

        assert 'Malformed' in caplog.text


class TestRecoverExitSignature:
    def test_recovers_from_full_honest_set(self):
        validator_index = 200
        setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=5, threshold=4
        )
        protocol_config = get_mocked_protocol_config(
            oracles_count=5, exit_signature_recover_threshold=4
        )

        recovered = _recover_exit_signature(
            validator_index=validator_index,
            shares=dict(setup.shares),
            threshold=4,
            public_key=setup.public_key,
            oracles=protocol_config.oracles,
        )

        assert recovered is not None
        assert is_valid_exit_signature(
            validator_index=validator_index,
            public_key=setup.public_key,
            signature=recovered,
            genesis_validators_root=NETWORK_CONFIG.GENESIS_VALIDATORS_ROOT,
            fork=NETWORK_CONFIG.SHAPELLA_FORK,
        )

    def test_returns_none_when_no_valid_subset_exists(self, caplog):
        validator_index = 201
        setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=5, threshold=4
        )
        protocol_config = get_mocked_protocol_config(
            oracles_count=5, exit_signature_recover_threshold=4
        )
        shares = dict(setup.shares)
        for share_index in (3, 4):
            shares[share_index] = poison_exit_share(setup, share_index).exit_signature_share

        with caplog.at_level(logging.ERROR):
            recovered = _recover_exit_signature(
                validator_index=validator_index,
                shares=shares,
                threshold=4,
                public_key=setup.public_key,
                oracles=protocol_config.oracles,
            )

        assert recovered is None
        assert 'Failed to recover a valid exit signature' in caplog.text

    def test_full_set_equals_threshold_makes_single_reconstruction_attempt(self, caplog):
        validator_index = 202
        setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=4, threshold=4
        )
        protocol_config = get_mocked_protocol_config(
            oracles_count=4, exit_signature_recover_threshold=4
        )
        shares = dict(setup.shares)
        shares[3] = poison_exit_share(setup, share_index=3).exit_signature_share

        with caplog.at_level(logging.ERROR), patch(
            'src.exits.service.reconstruct_shared_bls_signature',
            wraps=reconstruct_shared_bls_signature,
        ) as reconstruct_mock:
            recovered = _recover_exit_signature(
                validator_index=validator_index,
                shares=shares,
                threshold=4,
                public_key=setup.public_key,
                oracles=protocol_config.oracles,
            )

        assert recovered is None
        assert reconstruct_mock.call_count == 1
        assert 'Failed to recover a valid exit signature' in caplog.text

    def test_non_curve_share_recovered_from_honest_subset(self, caplog):
        validator_index = 205
        setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=5, threshold=4
        )
        protocol_config = get_mocked_protocol_config(
            oracles_count=5, exit_signature_recover_threshold=4
        )
        shares = dict(setup.shares)
        shares[0] = BLSSignature(bytes([0x00]) + random.randbytes(95))
        non_curve_address = protocol_config.oracles[0].address

        with caplog.at_level(logging.WARNING):
            recovered = _recover_exit_signature(
                validator_index=validator_index,
                shares=shares,
                threshold=4,
                public_key=setup.public_key,
                oracles=protocol_config.oracles,
            )

        assert recovered is not None
        assert is_valid_exit_signature(
            validator_index=validator_index,
            public_key=setup.public_key,
            signature=recovered,
            genesis_validators_root=NETWORK_CONFIG.GENESIS_VALIDATORS_ROOT,
            fork=NETWORK_CONFIG.SHAPELLA_FORK,
        )
        assert non_curve_address in caplog.text

    def test_poisoned_share_at_index_zero_recovered_and_flagged(self, caplog):
        validator_index = 203
        setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=5, threshold=4
        )
        protocol_config = get_mocked_protocol_config(
            oracles_count=5, exit_signature_recover_threshold=4
        )
        shares = dict(setup.shares)
        shares[0] = poison_exit_share(setup, share_index=0).exit_signature_share
        poisoned_address = protocol_config.oracles[0].address

        with caplog.at_level(logging.WARNING), patch.object(
            metrics, 'invalid_exit_shares'
        ) as invalid_exit_shares_mock:
            recovered = _recover_exit_signature(
                validator_index=validator_index,
                shares=shares,
                threshold=4,
                public_key=setup.public_key,
                oracles=protocol_config.oracles,
            )

        assert recovered is not None
        assert poisoned_address in caplog.text
        invalid_exit_shares_mock.labels.assert_any_call(network=NETWORK, oracle=poisoned_address)

    def test_aborts_after_max_recovery_attempts(self, caplog):
        validator_index = 204
        setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=5, threshold=4
        )
        protocol_config = get_mocked_protocol_config(
            oracles_count=5, exit_signature_recover_threshold=4
        )
        shares = dict(setup.shares)
        for share_index in (3, 4):
            shares[share_index] = poison_exit_share(setup, share_index).exit_signature_share

        with caplog.at_level(logging.ERROR), patch(
            'src.exits.service.MAX_EXIT_SIGNATURE_RECOVERY_ATTEMPTS', 1
        ):
            recovered = _recover_exit_signature(
                validator_index=validator_index,
                shares=shares,
                threshold=4,
                public_key=setup.public_key,
                oracles=protocol_config.oracles,
            )

        assert recovered is None
        assert 'Aborted' in caplog.text


async def _run_process_exits(
    protocol_config: ProtocolConfig,
    validator_exits: dict[int, list[ValidatorExitShare]],
    validators_data: list[dict],
) -> AsyncMock:
    with patch('src.exits.service.get_chain_latest_head', return_value=CHAIN_HEAD), patch(
        'src.exits.service._fetch_validator_exits', return_value=validator_exits
    ), patch.object(
        consensus_client, 'get_validators_by_ids', return_value={'data': validators_data}
    ), patch(
        'src.exits.service._submit_signature', return_value=True
    ) as submit_mock:
        await process_exits(protocol_config)
    return submit_mock


def _signature_is_valid(validator_index: int, public_key: bytes, submit_mock: AsyncMock) -> bool:
    signature = BLSSignature(Web3.to_bytes(hexstr=submit_mock.call_args.kwargs['exit_signature']))
    return is_valid_exit_signature(
        validator_index=validator_index,
        public_key=public_key,
        signature=signature,
        genesis_validators_root=NETWORK_CONFIG.GENESIS_VALIDATORS_ROOT,
        fork=NETWORK_CONFIG.SHAPELLA_FORK,
    )
