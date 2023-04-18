from dataclasses import dataclass
from decimal import Decimal

from ens.constants import EMPTY_ADDR_HEX
from eth_typing import ChecksumAddress
from web3 import Web3
from web3.types import Wei

MAINNET = 'mainnet'
GOERLI = 'goerli'
GNOSIS = 'gnosis'

ETH_NETWORKS = [MAINNET, GOERLI]
GNO_NETWORKS = [GNOSIS]


@dataclass
class NetworkConfig:
    SYMBOL: str
    KEEPER_CONTRACT_ADDRESS: ChecksumAddress
    ORACLES_CONTRACT_ADDRESS: ChecksumAddress
    SECONDS_PER_BLOCK: Decimal
    SLOTS_PER_EPOCH: int
    SECONDS_PER_SLOT: int
    IS_POA: bool
    KEEPER_MIN_BALANCE: Wei


NETWORKS = {
    MAINNET: NetworkConfig(
        SYMBOL='ETH',
        KEEPER_CONTRACT_ADDRESS=Web3.to_checksum_address(EMPTY_ADDR_HEX),
        ORACLES_CONTRACT_ADDRESS=Web3.to_checksum_address(EMPTY_ADDR_HEX),
        SECONDS_PER_BLOCK=Decimal(12),
        SLOTS_PER_EPOCH=32,
        SECONDS_PER_SLOT=12,
        IS_POA=False,
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
    ),
    GOERLI: NetworkConfig(
        SYMBOL='GoerliETH',
        KEEPER_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0x1833E7Ba555A6abc99B8299e662AfEec88167805'
        ),
        ORACLES_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0xDF43F5dBB585C6b38AeC413685aa67CD1dD47091'
        ),
        SECONDS_PER_BLOCK=Decimal(12),
        SLOTS_PER_EPOCH=32,
        SECONDS_PER_SLOT=12,
        IS_POA=True,
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
    ),
    GNOSIS: NetworkConfig(
        SYMBOL='xDAI',
        KEEPER_CONTRACT_ADDRESS=Web3.to_checksum_address(EMPTY_ADDR_HEX),
        ORACLES_CONTRACT_ADDRESS=Web3.to_checksum_address(EMPTY_ADDR_HEX),
        SECONDS_PER_BLOCK=Decimal('6.8'),
        SLOTS_PER_EPOCH=16,
        SECONDS_PER_SLOT=5,
        IS_POA=False,
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
    ),
}
