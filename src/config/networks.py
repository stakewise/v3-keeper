from dataclasses import dataclass
from decimal import Decimal

from ens.constants import EMPTY_ADDR_HEX
from eth_typing import ChecksumAddress
from web3 import Web3
from web3.types import BlockNumber, Wei

MAINNET = 'mainnet'
GOERLI = 'goerli'
HOLESKY = 'holesky'
GNOSIS = 'gnosis'

ETH_NETWORKS = [MAINNET, GOERLI, HOLESKY]
GNO_NETWORKS = [GNOSIS]


@dataclass
class NetworkConfig:
    SYMBOL: str
    KEEPER_CONTRACT_ADDRESS: ChecksumAddress
    KEEPER_GENESIS_BLOCK: BlockNumber
    SECONDS_PER_BLOCK: Decimal
    SLOTS_PER_EPOCH: int
    IS_POA: bool
    KEEPER_MIN_BALANCE: Wei


NETWORKS = {
    MAINNET: NetworkConfig(
        SYMBOL='ETH',
        KEEPER_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0x6B5815467da09DaA7DC83Db21c9239d98Bb487b5'
        ),
        KEEPER_GENESIS_BLOCK=BlockNumber(18470089),
        SECONDS_PER_BLOCK=Decimal(12),
        SLOTS_PER_EPOCH=32,
        IS_POA=False,
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
    ),
    GOERLI: NetworkConfig(
        SYMBOL='GoerliETH',
        KEEPER_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0x893ceb1cF23475defE3747670EbE4b40e629c6fD'
        ),
        KEEPER_GENESIS_BLOCK=BlockNumber(9583358),
        SECONDS_PER_BLOCK=Decimal(12),
        SLOTS_PER_EPOCH=32,
        IS_POA=True,
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
    ),
    HOLESKY: NetworkConfig(
        SYMBOL='HolETH',
        KEEPER_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0xB580799Bf7d62721D1a523f0FDF2f5Ed7BA4e259'
        ),
        KEEPER_GENESIS_BLOCK=BlockNumber(215379),
        SECONDS_PER_BLOCK=Decimal(12),
        SLOTS_PER_EPOCH=32,
        IS_POA=False,
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
    ),
    GNOSIS: NetworkConfig(
        SYMBOL='xDAI',
        KEEPER_CONTRACT_ADDRESS=Web3.to_checksum_address(EMPTY_ADDR_HEX),
        KEEPER_GENESIS_BLOCK=BlockNumber(0),
        SECONDS_PER_BLOCK=Decimal('6.8'),
        SLOTS_PER_EPOCH=16,
        IS_POA=False,
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
    ),
}
