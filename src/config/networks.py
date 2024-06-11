from dataclasses import dataclass

from ens.constants import EMPTY_ADDR_HEX
from eth_typing import ChecksumAddress
from web3 import Web3
from web3.types import BlockNumber, Wei

MAINNET = 'mainnet'
HOLESKY = 'holesky'
GNOSIS = 'gnosis'
CHIADO = 'chiado'

ETH_NETWORKS = [MAINNET, HOLESKY]
GNO_NETWORKS = [GNOSIS, CHIADO]
ENABLED_NETWORKS = [MAINNET, HOLESKY, GNOSIS, CHIADO]


@dataclass
class NetworkConfig:
    SYMBOL: str
    KEEPER_CONTRACT_ADDRESS: ChecksumAddress
    KEEPER_GENESIS_BLOCK: BlockNumber
    SECONDS_PER_BLOCK: int
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
        SECONDS_PER_BLOCK=12,
        SLOTS_PER_EPOCH=32,
        IS_POA=False,
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
    ),
    HOLESKY: NetworkConfig(
        SYMBOL='HolETH',
        KEEPER_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0xB580799Bf7d62721D1a523f0FDF2f5Ed7BA4e259'
        ),
        KEEPER_GENESIS_BLOCK=BlockNumber(215379),
        SECONDS_PER_BLOCK=12,
        SLOTS_PER_EPOCH=32,
        IS_POA=False,
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
    ),
    GNOSIS: NetworkConfig(
        SYMBOL='xDAI',
        KEEPER_CONTRACT_ADDRESS=Web3.to_checksum_address(EMPTY_ADDR_HEX),
        KEEPER_GENESIS_BLOCK=BlockNumber(0),
        SECONDS_PER_BLOCK=5,
        SLOTS_PER_EPOCH=16,
        IS_POA=False,
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
    ),
    CHIADO: NetworkConfig(
        SYMBOL='xDAI',
        KEEPER_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0x13Af1266d8664aF3da4c711E7C86725D4779EA72'
        ),
        KEEPER_GENESIS_BLOCK=BlockNumber(10258082),
        SECONDS_PER_BLOCK=5,
        SLOTS_PER_EPOCH=16,
        IS_POA=False,
        KEEPER_MIN_BALANCE=Web3.to_wei('0.1', 'ether'),
    ),
}
