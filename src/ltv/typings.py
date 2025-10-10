from dataclasses import dataclass

from web3.types import ChecksumAddress

from src.common.typings import HarvestParams


@dataclass
class VaultMaxLtvUser:
    ltv: int
    address: ChecksumAddress
    prev_address: ChecksumAddress
    vault: ChecksumAddress
    harvest_params: HarvestParams | None
