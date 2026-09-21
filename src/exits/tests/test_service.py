import logging
import random
from unittest.mock import AsyncMock, patch

import pytest
from eth_typing import BlockNumber
from eth_typing.bls import BLSSignature
from pydantic import ValidationError
from sw_utils import ChainHead, is_valid_exit_signature
from sw_utils.tests.factories import faker, get_mocked_protocol_config
from sw_utils.typings import ProtocolConfig
from web3 import Web3
from web3.types import Timestamp

from src.common.clients import consensus_client, ipfs_fetch_client
from src.common.tests.factories import create_oracle
from src.config.settings import NETWORK_CONFIG
from src.exits.crypto import reconstruct_shared_bls_signature
from src.exits.ipfs import fetch_exit_signature_shards
from src.exits.service import _fetch_exit_shares_from_endpoint, process_exits
from src.exits.tests.factories import (
    ExitSignaturesUpload,
    create_exit_shares,
    create_exit_signatures_upload,
    create_threshold_signature_setup,
    create_validator_data,
    poison_exit_share,
)
from src.exits.typings import ValidatorExitShare

CHAIN_HEAD = ChainHead(
    epoch=1, slot=32, block_number=BlockNumber(100), execution_ts=Timestamp(1700000000)
)


class TestProcessExits:
    async def test_four_of_five_verified_shares_reconstructed_once(self):
        validator_index = 100
        protocol_config = get_mocked_protocol_config(
            oracles_count=5, exit_signature_recover_threshold=4
        )
        setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=5, threshold=4
        )
        upload = create_exit_signatures_upload([setup], oracles_count=5)
        shares = create_exit_shares(setup, upload, share_indexes=[0, 1, 2, 3])
        validators_data = [
            create_validator_data(validator_index, setup.public_key, 'active_ongoing')
        ]

        with patch(
            'src.exits.service.reconstruct_shared_bls_signature',
            wraps=reconstruct_shared_bls_signature,
        ) as reconstruct_mock:
            submit_mock = await _run_process_exits(
                protocol_config, {validator_index: shares}, validators_data, uploads=[upload]
            )

        submit_mock.assert_called_once()
        assert submit_mock.call_args.kwargs['validator_index'] == validator_index
        assert _signature_is_valid(validator_index, setup.public_key, submit_mock)
        assert reconstruct_mock.call_count == 1

    async def test_poisoned_share_dropped_before_reconstruction(self, caplog):
        validator_index = 101
        protocol_config = get_mocked_protocol_config(
            oracles_count=5, exit_signature_recover_threshold=4
        )
        setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=5, threshold=4
        )
        upload = create_exit_signatures_upload([setup], oracles_count=5)
        honest_shares = create_exit_shares(setup, upload, share_indexes=[0, 1, 2, 3])
        poisoned_oracle_address = faker.eth_address()
        # Correct shard key, but the share differs from the decrypted shard
        poisoned_share = poison_exit_share(
            setup, upload, share_index=4, oracle_address=poisoned_oracle_address
        )
        validators_data = [
            create_validator_data(validator_index, setup.public_key, 'active_ongoing')
        ]

        with patch(
            'src.exits.service.reconstruct_shared_bls_signature',
            wraps=reconstruct_shared_bls_signature,
        ) as reconstruct_mock, caplog.at_level(logging.WARNING):
            submit_mock = await _run_process_exits(
                protocol_config,
                {validator_index: honest_shares + [poisoned_share]},
                validators_data,
                uploads=[upload],
            )

        submit_mock.assert_called_once()
        assert _signature_is_valid(validator_index, setup.public_key, submit_mock)
        assert reconstruct_mock.call_count == 1
        assert 'decrypted shard differs from exit signature share' in caplog.text
        assert poisoned_oracle_address in caplog.text

    async def test_two_poisoned_shares_not_submitted(self, caplog):
        validator_index = 102
        protocol_config = get_mocked_protocol_config(
            oracles_count=5, exit_signature_recover_threshold=4
        )
        setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=5, threshold=4
        )
        upload = create_exit_signatures_upload([setup], oracles_count=5)
        shares = create_exit_shares(setup, upload, share_indexes=[0, 1, 2]) + [
            poison_exit_share(setup, upload, share_index=3),
            poison_exit_share(setup, upload, share_index=4),
        ]
        validators_data = [
            create_validator_data(validator_index, setup.public_key, 'active_ongoing')
        ]

        with patch(
            'src.exits.service.reconstruct_shared_bls_signature'
        ) as reconstruct_mock, caplog.at_level(logging.WARNING):
            submit_mock = await _run_process_exits(
                protocol_config, {validator_index: shares}, validators_data, uploads=[upload]
            )

        submit_mock.assert_not_called()
        reconstruct_mock.assert_not_called()
        assert 'Not enough exit signature shares' in caplog.text

    @pytest.mark.parametrize(
        'share_index, error',
        [
            (4, 'failed to decrypt shard with AES key'),
            (5, 'share index is missing in IPFS upload'),
        ],
    )
    async def test_unverifiable_share_dropped(self, caplog, share_index, error):
        validator_index = 103
        protocol_config = get_mocked_protocol_config(
            oracles_count=5, exit_signature_recover_threshold=4
        )
        setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=6, threshold=4
        )
        upload = create_exit_signatures_upload([setup], oracles_count=5)
        honest_shares = create_exit_shares(setup, upload, share_indexes=[0, 1, 2, 3])
        bad_oracle_address = faker.eth_address()
        bad_share = ValidatorExitShare(
            validator_index=validator_index,
            exit_signature_share=setup.shares[share_index],
            share_index=share_index,
            oracle_address=bad_oracle_address,
            ipfs_hash=upload.ipfs_hash,
            shard_key=random.randbytes(32),
        )
        validators_data = [
            create_validator_data(validator_index, setup.public_key, 'active_ongoing')
        ]

        with caplog.at_level(logging.WARNING):
            submit_mock = await _run_process_exits(
                protocol_config,
                {validator_index: honest_shares + [bad_share]},
                validators_data,
                uploads=[upload],
            )

        submit_mock.assert_called_once()
        assert _signature_is_valid(validator_index, setup.public_key, submit_mock)
        assert error in caplog.text
        assert bad_oracle_address in caplog.text

    async def test_validator_missing_in_upload_not_submitted(self, caplog):
        validator_index = 104
        protocol_config = get_mocked_protocol_config(
            oracles_count=4, exit_signature_recover_threshold=4
        )
        setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=4, threshold=4
        )
        other_setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=4, threshold=4
        )
        upload = create_exit_signatures_upload([setup], oracles_count=4)
        other_upload = create_exit_signatures_upload([other_setup], oracles_count=4)
        # Shares point to the upload of a validator with another public key
        shares = create_exit_shares(setup, upload, share_indexes=[0, 1, 2, 3])
        for share in shares:
            share.ipfs_hash = other_upload.ipfs_hash
        validators_data = [
            create_validator_data(validator_index, setup.public_key, 'active_ongoing')
        ]

        with caplog.at_level(logging.WARNING):
            submit_mock = await _run_process_exits(
                protocol_config, {validator_index: shares}, validators_data, uploads=[other_upload]
            )

        submit_mock.assert_not_called()
        assert 'validator is missing in IPFS upload' in caplog.text
        assert 'Not enough exit signature shares' in caplog.text

    async def test_unavailable_upload_not_submitted(self, caplog):
        validator_index = 105
        protocol_config = get_mocked_protocol_config(
            oracles_count=4, exit_signature_recover_threshold=4
        )
        setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=4, threshold=4
        )
        upload = create_exit_signatures_upload([setup], oracles_count=4)
        shares = create_exit_shares(setup, upload, share_indexes=[0, 1, 2, 3])
        validators_data = [
            create_validator_data(validator_index, setup.public_key, 'active_ongoing')
        ]

        with caplog.at_level(logging.WARNING):
            # upload is not served by IPFS
            submit_mock = await _run_process_exits(
                protocol_config, {validator_index: shares}, validators_data
            )

        submit_mock.assert_not_called()
        assert 'Failed to fetch exit signatures from IPFS' in caplog.text
        assert 'IPFS upload is unavailable' in caplog.text

    async def test_below_threshold_not_submitted(self):
        validator_index = 106
        protocol_config = get_mocked_protocol_config(
            oracles_count=5, exit_signature_recover_threshold=4
        )
        setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=5, threshold=4
        )
        upload = create_exit_signatures_upload([setup], oracles_count=5)
        shares = create_exit_shares(setup, upload, share_indexes=[0, 1, 2])
        validators_data = [
            create_validator_data(validator_index, setup.public_key, 'active_ongoing')
        ]

        submit_mock = await _run_process_exits(
            protocol_config, {validator_index: shares}, validators_data, uploads=[upload]
        )

        submit_mock.assert_not_called()

    async def test_duplicate_share_index_not_counted_toward_threshold(self):
        validator_index = 107
        protocol_config = get_mocked_protocol_config(
            oracles_count=5, exit_signature_recover_threshold=4
        )
        setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=5, threshold=4
        )
        upload = create_exit_signatures_upload([setup], oracles_count=5)
        # 4 shares, but two of them have the same share_index so only 3 are distinct
        shares = create_exit_shares(setup, upload, share_indexes=[0, 1, 2, 2])
        validators_data = [
            create_validator_data(validator_index, setup.public_key, 'active_ongoing')
        ]

        submit_mock = await _run_process_exits(
            protocol_config, {validator_index: shares}, validators_data, uploads=[upload]
        )

        submit_mock.assert_not_called()

    async def test_historical_share_indexes_recovered(self):
        """Oracles at config positions 0..3 serve shards from an older, larger upload."""
        validator_index = 108
        protocol_config = get_mocked_protocol_config(
            oracles_count=4, exit_signature_recover_threshold=4
        )
        setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=11, threshold=4
        )
        upload = create_exit_signatures_upload([setup], oracles_count=11)
        shares = create_exit_shares(setup, upload, share_indexes=[4, 7, 9, 10])
        validators_data = [
            create_validator_data(validator_index, setup.public_key, 'active_ongoing')
        ]

        submit_mock = await _run_process_exits(
            protocol_config, {validator_index: shares}, validators_data, uploads=[upload]
        )

        submit_mock.assert_called_once()
        assert _signature_is_valid(validator_index, setup.public_key, submit_mock)

    async def test_minority_upload_skipped_without_fetching(self, caplog):
        """A slow oracle serves a shard of the previous upload with another key split."""
        validator_index = 109
        protocol_config = get_mocked_protocol_config(
            oracles_count=5, exit_signature_recover_threshold=4
        )
        secret_key = random.randint(1, 2**64)
        old_setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=5, threshold=4, secret_key=secret_key
        )
        new_setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=5, threshold=4, secret_key=secret_key
        )
        old_upload = create_exit_signatures_upload([old_setup], oracles_count=5)
        new_upload = create_exit_signatures_upload([new_setup], oracles_count=5)
        shares = create_exit_shares(old_setup, old_upload, share_indexes=[4]) + create_exit_shares(
            new_setup, new_upload, share_indexes=[0, 1, 2, 3]
        )
        validators_data = [
            create_validator_data(validator_index, new_setup.public_key, 'active_ongoing')
        ]

        with patch(
            'src.exits.service.fetch_exit_signature_shards', wraps=fetch_exit_signature_shards
        ) as fetch_mock, caplog.at_level(logging.WARNING):
            submit_mock = await _run_process_exits(
                protocol_config,
                {validator_index: shares},
                validators_data,
                uploads=[old_upload, new_upload],
            )

        submit_mock.assert_called_once()
        assert _signature_is_valid(validator_index, new_setup.public_key, submit_mock)
        fetch_mock.assert_called_once_with({new_upload.ipfs_hash})
        assert 'come from different IPFS uploads' in caplog.text

    async def test_fake_upload_rejected_by_signature_check(self, caplog):
        """Colluding oracles serve a consistent upload of a wrong key: the BLS check rejects it."""
        validator_index = 110
        protocol_config = get_mocked_protocol_config(
            oracles_count=5, exit_signature_recover_threshold=4
        )
        setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=5, threshold=4
        )
        fake_setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=5, threshold=4
        )
        fake_setup.public_key = setup.public_key
        fake_upload = create_exit_signatures_upload([fake_setup], oracles_count=5)
        shares = create_exit_shares(fake_setup, fake_upload, share_indexes=[0, 1, 2, 3])
        validators_data = [
            create_validator_data(validator_index, setup.public_key, 'active_ongoing')
        ]

        with caplog.at_level(logging.ERROR):
            submit_mock = await _run_process_exits(
                protocol_config, {validator_index: shares}, validators_data, uploads=[fake_upload]
            )

        submit_mock.assert_not_called()
        assert 'Failed to recover a valid exit signature' in caplog.text

    async def test_upload_fetched_once_for_many_validators(self):
        protocol_config = get_mocked_protocol_config(
            oracles_count=4, exit_signature_recover_threshold=4
        )
        setups = [
            create_threshold_signature_setup(validator_index=i, oracles_count=4, threshold=4)
            for i in (111, 112)
        ]
        upload = create_exit_signatures_upload(setups, oracles_count=4)
        validator_exits = {
            setup.validator_index: create_exit_shares(setup, upload, share_indexes=[0, 1, 2, 3])
            for setup in setups
        }
        validators_data = [
            create_validator_data(setup.validator_index, setup.public_key, 'active_ongoing')
            for setup in setups
        ]

        with patch(
            'src.exits.service.fetch_exit_signature_shards', wraps=fetch_exit_signature_shards
        ) as fetch_mock:
            submit_mock = await _run_process_exits(
                protocol_config, validator_exits, validators_data, uploads=[upload]
            )

        fetch_mock.assert_called_once_with({upload.ipfs_hash})
        assert submit_mock.call_count == 2

    async def test_exiting_validator_skipped(self):
        validator_index = 113
        protocol_config = get_mocked_protocol_config(
            oracles_count=5, exit_signature_recover_threshold=4
        )
        setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=5, threshold=4
        )
        upload = create_exit_signatures_upload([setup], oracles_count=5)
        shares = create_exit_shares(setup, upload, share_indexes=[0, 1, 2, 3])
        validators_data = [
            create_validator_data(validator_index, setup.public_key, 'active_exiting')
        ]

        submit_mock = await _run_process_exits(
            protocol_config, {validator_index: shares}, validators_data, uploads=[upload]
        )

        submit_mock.assert_not_called()

    async def test_validator_missing_from_beacon_skipped(self, caplog):
        validator_index = 114
        protocol_config = get_mocked_protocol_config(
            oracles_count=5, exit_signature_recover_threshold=4
        )
        setup = create_threshold_signature_setup(
            validator_index=validator_index, oracles_count=5, threshold=4
        )
        upload = create_exit_signatures_upload([setup], oracles_count=5)
        shares = create_exit_shares(setup, upload, share_indexes=[0, 1, 2, 3])

        with caplog.at_level(logging.WARNING):
            submit_mock = await _run_process_exits(
                protocol_config, {validator_index: shares}, validators_data=[], uploads=[upload]
            )

        submit_mock.assert_not_called()
        assert 'Missing consensus validator pubkey' in caplog.text

    async def test_tolerates_malformed_oracle_response(self, caplog):
        validator_index = 115
        protocol_config = get_mocked_protocol_config(
            oracles_count=1, exit_signature_recover_threshold=1
        )
        data = [
            {
                **_create_response_item(validator_index),
                'exit_signature_share': Web3.to_hex(random.randbytes(64)),
            }
        ]

        with patch('src.exits.service.get_chain_latest_head', return_value=CHAIN_HEAD), patch(
            'src.exits.service.aiohttp_fetch', return_value=data
        ), patch.object(
            consensus_client, 'get_validators_by_ids', return_value={'data': []}
        ), patch(
            'src.exits.service._submit_signature'
        ) as submit_mock, caplog.at_level(
            logging.WARNING
        ):
            await process_exits(protocol_config)

        submit_mock.assert_not_called()
        assert 'invalid bls signature' in caplog.text

    async def test_validator_exit_failure_isolated_from_other_validators(self, caplog):
        protocol_config = get_mocked_protocol_config(
            oracles_count=5, exit_signature_recover_threshold=4
        )
        validator_exits = {116: [], 117: []}
        validators_data = [
            {
                'index': '116',
                'status': 'active_ongoing',
                'validator': {'pubkey': Web3.to_hex(random.randbytes(48))},
            },
            {
                'index': '117',
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

        assert 'Failed to process exit for validator 116' in caplog.text
        assert 'Processed 2 validator exits, 1 submitted' in caplog.text


class TestFetchExitSharesFromEndpoint:
    async def test_parses_response(self, client_session):
        oracle = create_oracle(num_endpoints=1)
        item = _create_response_item(validator_index=5, share_index=9)

        with patch('src.exits.service.aiohttp_fetch', return_value=[item]):
            shares = await _fetch_exit_shares_from_endpoint(
                session=client_session, oracle=oracle, endpoint=oracle.endpoints[0]
            )

        assert shares == [
            ValidatorExitShare(
                validator_index=5,
                exit_signature_share=BLSSignature(
                    Web3.to_bytes(hexstr=item['exit_signature_share'])
                ),
                share_index=9,
                oracle_address=oracle.address,
                ipfs_hash=item['ipfs_hash'],
                shard_key=Web3.to_bytes(hexstr=item['shard_key']),
            )
        ]

    async def test_duplicate_validator_index_deduplicated(self, client_session, caplog):
        oracle = create_oracle(num_endpoints=1)
        data = [_create_response_item(validator_index=5) for _ in range(4)]

        with patch('src.exits.service.aiohttp_fetch', return_value=data), caplog.at_level(
            logging.WARNING
        ):
            shares = await _fetch_exit_shares_from_endpoint(
                session=client_session, oracle=oracle, endpoint=oracle.endpoints[0]
            )

        assert len(shares) == 1
        assert shares[0].validator_index == 5
        assert 'Duplicate' in caplog.text

    @pytest.mark.parametrize(
        'field, value',
        [
            ('share_index', -1),
            ('share_index', 'abc'),
            ('share_index', None),
            ('exit_signature_share', Web3.to_hex(random.randbytes(64))),
            ('ipfs_hash', ''),
            ('ipfs_hash', None),
            ('shard_key', Web3.to_hex(random.randbytes(31))),
            ('shard_key', 'abc'),
            ('shard_key', None),
        ],
    )
    async def test_malformed_field_rejects_whole_response(self, client_session, field, value):
        oracle = create_oracle(num_endpoints=1)
        data = [
            _create_response_item(validator_index=5),
            {**_create_response_item(validator_index=6), field: value},
        ]

        with patch('src.exits.service.aiohttp_fetch', return_value=data), pytest.raises(
            ValidationError
        ):
            await _fetch_exit_shares_from_endpoint(
                session=client_session, oracle=oracle, endpoint=oracle.endpoints[0]
            )

    @pytest.mark.parametrize(
        'field', ['share_index', 'exit_signature_share', 'ipfs_hash', 'shard_key']
    )
    async def test_missing_field_rejects_whole_response(self, client_session, field):
        oracle = create_oracle(num_endpoints=1)
        item = _create_response_item(validator_index=7)
        del item[field]

        with patch('src.exits.service.aiohttp_fetch', return_value=[item]), pytest.raises(
            ValidationError
        ):
            await _fetch_exit_shares_from_endpoint(
                session=client_session, oracle=oracle, endpoint=oracle.endpoints[0]
            )


def _create_response_item(validator_index: int, share_index: int = 0) -> dict:
    setup = create_threshold_signature_setup(
        validator_index=validator_index, oracles_count=share_index + 1, threshold=1
    )
    upload = create_exit_signatures_upload([setup], oracles_count=share_index + 1)
    return {
        'index': str(validator_index),
        'share_index': share_index,
        'exit_signature_share': Web3.to_hex(setup.shares[share_index]),
        'ipfs_hash': upload.ipfs_hash,
        'shard_key': Web3.to_hex(upload.shard_keys[validator_index, share_index]),
    }


async def _run_process_exits(
    protocol_config: ProtocolConfig,
    validator_exits: dict[int, list[ValidatorExitShare]],
    validators_data: list[dict],
    uploads: list[ExitSignaturesUpload] | None = None,
) -> AsyncMock:
    uploads_data = {upload.ipfs_hash: upload.data for upload in uploads or []}

    async def fetch_bytes(ipfs_hash: str) -> bytes:
        return uploads_data[ipfs_hash]

    with patch('src.exits.service.get_chain_latest_head', return_value=CHAIN_HEAD), patch(
        'src.exits.service._fetch_validator_exits', return_value=validator_exits
    ), patch.object(
        consensus_client, 'get_validators_by_ids', return_value={'data': validators_data}
    ), patch.object(
        ipfs_fetch_client, 'fetch_bytes', side_effect=fetch_bytes
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
