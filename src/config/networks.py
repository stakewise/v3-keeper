from dataclasses import dataclass
from decimal import Decimal

from ens.constants import EMPTY_ADDR_HEX
from eth_typing import ChecksumAddress
from web3 import Web3
from web3.types import BlockNumber, Wei

MAINNET = 'mainnet'
GOERLI = 'goerli'
GNOSIS = 'gnosis'

ETH_NETWORKS = [MAINNET, GOERLI]
GNO_NETWORKS = [GNOSIS]


@dataclass
class NetworkConfig:
    SYMBOL: str
    KEEPER_CONTRACT_ADDRESS: ChecksumAddress
    KEEPER_GENESIS_BLOCK: BlockNumber
    SECONDS_PER_BLOCK: Decimal
    SLOTS_PER_EPOCH: int
    SECONDS_PER_SLOT: int
    IS_POA: bool
    KEEPER_MIN_BALANCE: Wei


NETWORKS = {
    MAINNET: NetworkConfig(
        SYMBOL='ETH',
        KEEPER_CONTRACT_ADDRESS=Web3.to_checksum_address(EMPTY_ADDR_HEX),
        KEEPER_GENESIS_BLOCK=BlockNumber(0),
        SECONDS_PER_BLOCK=Decimal(12),
        SLOTS_PER_EPOCH=32,
        SECONDS_PER_SLOT=12,
        IS_POA=False,
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
    ),
    GOERLI: NetworkConfig(
        SYMBOL='GoerliETH',
        KEEPER_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0xDbb29280c1561F44C02a9cB91AC3B8B5B3b45752'
        ),
        KEEPER_GENESIS_BLOCK=BlockNumber(9234813),
        SECONDS_PER_BLOCK=Decimal(12),
        SLOTS_PER_EPOCH=32,
        SECONDS_PER_SLOT=12,
        IS_POA=True,
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
    ),
    GNOSIS: NetworkConfig(
        SYMBOL='xDAI',
        KEEPER_CONTRACT_ADDRESS=Web3.to_checksum_address(EMPTY_ADDR_HEX),
        KEEPER_GENESIS_BLOCK=BlockNumber(0),
        SECONDS_PER_BLOCK=Decimal('6.8'),
        SLOTS_PER_EPOCH=16,
        SECONDS_PER_SLOT=5,
        IS_POA=False,
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
    ),
}
