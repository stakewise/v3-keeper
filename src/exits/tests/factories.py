import random
from dataclasses import dataclass
from typing import Any

from Crypto.Cipher import AES
from eth_typing import ChecksumAddress
from eth_typing.bls import BLSPubkey, BLSSignature
from py_ecc.bls import G2ProofOfPossession as bls
from py_ecc.optimized_bls12_381.optimized_curve import curve_order
from sw_utils import get_exit_message_signing_root
from sw_utils.tests.factories import faker
from sw_utils.vendor.ipfs_unixfs import compute_cid
from web3 import Web3

from src.config.settings import NETWORK_CONFIG
from src.exits.crypto import ECIES_EPHEMERAL_PUBLIC_KEY_LENGTH, ECIES_NONCE_LENGTH
from src.exits.typings import ValidatorExitShare

EXIT_SIGNATURE_SHARD_LENGTH = 193


@dataclass
class ThresholdSignatureSetup:
    validator_index: int
    threshold: int
    public_key: BLSPubkey
    # share secret keys by share_index, used to build poisoned shares
    share_secret_keys: dict[int, int]
    shares: dict[int, BLSSignature]


def create_threshold_signature_setup(
    validator_index: int, oracles_count: int, threshold: int, secret_key: int | None = None
) -> ThresholdSignatureSetup:
    """Shamir-splits a BLS key; share i is evaluated at x = i + 1 to match crypto.py."""
    secret_key = secret_key or random.randint(1, curve_order - 1)
    coefficients = [secret_key] + [random.randint(1, curve_order - 1) for _ in range(threshold - 1)]
    message = _exit_signing_root(validator_index)

    share_secret_keys = {
        share_index: _evaluate_polynomial(coefficients, share_index + 1)
        for share_index in range(oracles_count)
    }
    shares = {
        share_index: BLSSignature(bls.Sign(share_secret_key, message))
        for share_index, share_secret_key in share_secret_keys.items()
    }
    return ThresholdSignatureSetup(
        validator_index=validator_index,
        threshold=threshold,
        public_key=BLSPubkey(bls.SkToPk(secret_key)),
        share_secret_keys=share_secret_keys,
        shares=shares,
    )


@dataclass
class ExitSignaturesUpload:
    ipfs_hash: str
    data: bytes
    # shard keys by (validator_index, share_index)
    shard_keys: dict[tuple[int, int], bytes]


def create_exit_signatures_upload(
    setups: list[ThresholdSignatureSetup], oracles_count: int
) -> ExitSignaturesUpload:
    """Builds exit signatures upload in the oracle format, every shard has its own key."""
    shard_keys: dict[tuple[int, int], bytes] = {}
    data = (
        oracles_count.to_bytes(2, byteorder='big')
        + EXIT_SIGNATURE_SHARD_LENGTH.to_bytes(2, byteorder='big')
        + (0).to_bytes(8, byteorder='big')
    )
    for setup in setups:
        data += setup.public_key + setup.validator_index.to_bytes(8, byteorder='big')
        for share_index in range(oracles_count):
            shard_key = random.randbytes(32)
            shard_keys[setup.validator_index, share_index] = shard_key
            data += encrypt_shard_with_aes_key(shard_key, setup.shares[share_index])
    return ExitSignaturesUpload(ipfs_hash=str(compute_cid(data)), data=data, shard_keys=shard_keys)


def encrypt_shard_with_aes_key(aes_key: bytes, data: bytes) -> bytes:
    """Same layout as eciespy: ephemeral public key + nonce + tag + encrypted data."""
    nonce = random.randbytes(ECIES_NONCE_LENGTH)
    cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
    encrypted_data, tag = cipher.encrypt_and_digest(data)
    return random.randbytes(ECIES_EPHEMERAL_PUBLIC_KEY_LENGTH) + nonce + tag + encrypted_data


def create_exit_shares(
    setup: ThresholdSignatureSetup,
    upload: ExitSignaturesUpload,
    share_indexes: list[int],
    oracle_addresses: dict[int, ChecksumAddress] | None = None,
) -> list[ValidatorExitShare]:
    oracle_addresses = oracle_addresses or {}
    return [
        ValidatorExitShare(
            validator_index=setup.validator_index,
            exit_signature_share=setup.shares[share_index],
            share_index=share_index,
            oracle_address=oracle_addresses.get(share_index) or faker.eth_address(),
            ipfs_hash=upload.ipfs_hash,
            shard_key=upload.shard_keys[setup.validator_index, share_index],
        )
        for share_index in share_indexes
    ]


def poison_exit_share(
    setup: ThresholdSignatureSetup,
    upload: ExitSignaturesUpload,
    share_index: int,
    oracle_address: ChecksumAddress | None = None,
) -> ValidatorExitShare:
    """Signs the share key over another validator's exit message: well-formed but wrong."""
    wrong_message = _exit_signing_root(setup.validator_index + 1)
    poisoned_signature = BLSSignature(bls.Sign(setup.share_secret_keys[share_index], wrong_message))
    share = create_exit_shares(setup, upload, [share_index])[0]
    share.exit_signature_share = poisoned_signature
    share.oracle_address = oracle_address or share.oracle_address
    return share


def create_validator_data(
    validator_index: int, public_key: BLSPubkey, status: str
) -> dict[str, Any]:
    return {
        'index': str(validator_index),
        'status': status,
        'validator': {'pubkey': Web3.to_hex(public_key)},
    }


def _exit_signing_root(validator_index: int) -> bytes:
    return get_exit_message_signing_root(
        validator_index=validator_index,
        genesis_validators_root=NETWORK_CONFIG.GENESIS_VALIDATORS_ROOT,
        fork=NETWORK_CONFIG.SHAPELLA_FORK,
    )


def _evaluate_polynomial(coefficients: list[int], x: int) -> int:
    result = 0
    for coefficient in reversed(coefficients):
        result = (result * x + coefficient) % curve_order
    return result
