import logging
import random
from unittest.mock import patch

import pytest

from src.common.clients import ipfs_fetch_client
from src.exits.ipfs import fetch_exit_signature_shards, parse_exit_signature_shards
from src.exits.tests.factories import (
    EXIT_SIGNATURE_SHARD_LENGTH,
    create_exit_signatures_upload,
    create_threshold_signature_setup,
)


class TestParseExitSignatureShards:
    def test_parses_format_with_validator_indexes(self):
        setups = [
            create_threshold_signature_setup(validator_index=i, oracles_count=3, threshold=2)
            for i in (10, 11)
        ]
        upload = create_exit_signatures_upload(setups, oracles_count=3)

        shards = parse_exit_signature_shards(upload.data)

        assert list(shards) == [setup.public_key for setup in setups]
        assert all(len(validator_shards) == 3 for validator_shards in shards.values())
        assert all(
            len(shard) == EXIT_SIGNATURE_SHARD_LENGTH
            for validator_shards in shards.values()
            for shard in validator_shards
        )

    def test_parses_format_without_validator_indexes(self):
        public_key = random.randbytes(48)
        validator_shards = [random.randbytes(EXIT_SIGNATURE_SHARD_LENGTH) for _ in range(2)]
        data = (
            (2).to_bytes(2, byteorder='big')
            + EXIT_SIGNATURE_SHARD_LENGTH.to_bytes(2, byteorder='big')
            + (0).to_bytes(8, byteorder='big')
            + public_key
            + b''.join(validator_shards)
        )

        assert parse_exit_signature_shards(data) == {public_key: validator_shards}

    def test_unknown_format_rejected(self):
        setup = create_threshold_signature_setup(validator_index=1, oracles_count=3, threshold=2)
        upload = create_exit_signatures_upload([setup], oracles_count=3)

        with pytest.raises(ValueError):
            parse_exit_signature_shards(upload.data[:-1])


class TestFetchExitSignatureShards:
    async def test_fetches_each_upload(self):
        setup = create_threshold_signature_setup(validator_index=1, oracles_count=3, threshold=2)
        upload = create_exit_signatures_upload([setup], oracles_count=3)

        with patch.object(ipfs_fetch_client, 'fetch_bytes', return_value=upload.data) as fetch_mock:
            shards = await fetch_exit_signature_shards({upload.ipfs_hash})

        fetch_mock.assert_called_once_with(upload.ipfs_hash)
        assert list(shards[upload.ipfs_hash]) == [setup.public_key]

    async def test_fetch_failure_omitted(self, caplog):
        setups = [
            create_threshold_signature_setup(validator_index=i, oracles_count=3, threshold=2)
            for i in (1, 2)
        ]
        upload = create_exit_signatures_upload(setups[:1], oracles_count=3)
        failed_ipfs_hash = create_exit_signatures_upload(setups[1:], oracles_count=3).ipfs_hash

        async def fetch_bytes(ipfs_hash: str) -> bytes:
            if ipfs_hash == failed_ipfs_hash:
                raise RuntimeError('boom')
            return upload.data

        with patch.object(
            ipfs_fetch_client, 'fetch_bytes', side_effect=fetch_bytes
        ), caplog.at_level(logging.WARNING):
            shards = await fetch_exit_signature_shards({upload.ipfs_hash, failed_ipfs_hash})

        assert list(shards) == [upload.ipfs_hash]
        assert failed_ipfs_hash in caplog.text
