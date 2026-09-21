from annotated_types import Ge, MinLen
from pydantic import BaseModel, Field
from typing_extensions import Annotated

from src.common.fields import BLSSignatureField, Bytes32Field


class OracleValidatorExit(BaseModel):
    """Single item of the oracle `/exits` response."""

    validator_index: Annotated[int, Ge(0)] = Field(alias='index')
    exit_signature_share: BLSSignatureField
    # Position of the shard in the IPFS upload
    share_index: Annotated[int, Ge(0)]
    # IPFS upload holding the encrypted shard
    ipfs_hash: Annotated[str, MinLen(1)]
    # AES key of the shard: the keeper decrypts the shard itself instead of trusting the oracle
    shard_key: Bytes32Field
