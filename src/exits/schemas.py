from annotated_types import Ge
from pydantic import BaseModel, Field
from typing_extensions import Annotated

from src.common.fields import BLSSignatureField


class OracleValidatorExit(BaseModel):
    """Single item of the oracle `/exits` response."""

    validator_index: Annotated[int, Ge(0)] = Field(alias='index')
    exit_signature_share: BLSSignatureField
    share_index: Annotated[int, Ge(0)]
