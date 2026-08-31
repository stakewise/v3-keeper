from typing import Annotated

from eth_typing.bls import BLSSignature
from pydantic import BeforeValidator

from src.common.validators import to_bls_signature

BLSSignatureField = Annotated[BLSSignature, BeforeValidator(to_bls_signature)]
