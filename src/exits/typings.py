from dataclasses import dataclass

from eth_typing.bls import BLSSignature


@dataclass
class ValidatorExitShare:
    validator_index: int
    exit_signature_share: BLSSignature
    share_index: int
