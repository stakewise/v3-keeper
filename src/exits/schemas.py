from annotated_types import Ge
from pydantic import BaseModel, Field
from typing_extensions import Annotated

from src.common.fields import BLSSignatureField

# `share_index` is absent from the response: an explicit null is rejected as malformed.
SHARE_INDEX_UNSET = -1


class OracleValidatorExit(BaseModel):
    """Single item of the oracle `/exits` response."""

    validator_index: Annotated[int, Ge(0)] = Field(alias='index')
    exit_signature_share: BLSSignatureField
    # TODO: make `share_index` mandatory once every oracle in every network
    # serves it, and drop the fallback to the oracle's config position.
    share_index: Annotated[int, Ge(0)] = SHARE_INDEX_UNSET
