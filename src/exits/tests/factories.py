import random
from dataclasses import dataclass
from typing import Any

from eth_typing.bls import BLSPubkey, BLSSignature
from py_ecc.bls import G2ProofOfPossession as bls
from py_ecc.optimized_bls12_381.optimized_curve import curve_order
from sw_utils import get_exit_message_signing_root
from web3 import Web3

from src.config.settings import NETWORK_CONFIG


@dataclass
class ThresholdSignatureSetup:
    validator_index: int
    threshold: int
    public_key: BLSPubkey
    # secret key of each oracle's share, keyed by share_index; used to sign poisoned messages
    share_secret_keys: dict[int, int]
    shares: dict[int, BLSSignature]


def create_threshold_signature_setup(
    validator_index: int, oracles_count: int, threshold: int
) -> ThresholdSignatureSetup:
    """Shamir-splits a random BLS secret key of degree threshold-1, evaluating share i at
    x = i + 1 to match reconstruct_shared_bls_signature's Lagrange coefficient convention."""
    secret_key = random.randint(1, curve_order - 1)
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


def create_exit_shares(
    setup: ThresholdSignatureSetup, share_indexes: list[int]
) -> dict[int, BLSSignature]:
    return {share_index: setup.shares[share_index] for share_index in share_indexes}


def poison_exit_share(setup: ThresholdSignatureSetup, share_index: int) -> BLSSignature:
    """Signs the same share secret key over a different validator's exit message,
    simulating a well-formed share that was signed over the wrong content."""
    wrong_message = _exit_signing_root(setup.validator_index + 1)
    return BLSSignature(bls.Sign(setup.share_secret_keys[share_index], wrong_message))


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
