from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from ens.constants import EMPTY_ADDR_HEX
from eth_typing import BlockNumber, ChecksumAddress, HexStr
from web3 import Web3
from web3.types import Timestamp

MAINNET = 'mainnet'
GOERLI = 'goerli'
GNOSIS = 'gnosis'

ETH_NETWORKS = [MAINNET, GOERLI]
GNO_NETWORKS = [GNOSIS]


@dataclass
class NetworkConfig:
    GENESIS_TIMESTAMP: Timestamp
    GENESIS_FORK_VERSION: bytes
    KEEPER_CONTRACT_ADDRESS: ChecksumAddress
    KEEPER_GENESIS_BLOCK: BlockNumber
    KEEPER_GENESIS_TIMESTAMP: Timestamp
    ORACLES_CONTRACT_ADDRESS: ChecksumAddress
    DAO_ENS_ORACLES_KEY: str
    SYNC_PERIOD: int
    SECONDS_PER_BLOCK: Decimal
    CONFIRMATION_BLOCKS: int
    CHAIN_ID: int
    IS_POA: bool


NETWORKS = {
    MAINNET: NetworkConfig(
        GENESIS_TIMESTAMP=Timestamp(1606824023),
        GENESIS_FORK_VERSION=Web3.to_bytes(hexstr=HexStr('0x00000000')),
        KEEPER_CONTRACT_ADDRESS=Web3.to_checksum_address(EMPTY_ADDR_HEX),
        KEEPER_GENESIS_BLOCK=BlockNumber(0),
        KEEPER_GENESIS_TIMESTAMP=Timestamp(0),
        ORACLES_CONTRACT_ADDRESS=Web3.to_checksum_address(EMPTY_ADDR_HEX),
        DAO_ENS_ORACLES_KEY='eth_oracles_config',
        SYNC_PERIOD=int(timedelta(days=1).total_seconds()),
        SECONDS_PER_BLOCK=Decimal(12),
        CONFIRMATION_BLOCKS=64,
        CHAIN_ID=1,
        IS_POA=False,
    ),
    GOERLI: NetworkConfig(
        KEEPER_CONTRACT_ADDRESS=Web3.to_checksum_address(EMPTY_ADDR_HEX),
        KEEPER_GENESIS_BLOCK=BlockNumber(0),
        KEEPER_GENESIS_TIMESTAMP=Timestamp(0),
        ORACLES_CONTRACT_ADDRESS=Web3.to_checksum_address(EMPTY_ADDR_HEX),
        GENESIS_TIMESTAMP=Timestamp(1616508000),
        GENESIS_FORK_VERSION=Web3.to_bytes(hexstr=HexStr('0x00001020')),
        DAO_ENS_ORACLES_KEY='eth_oracles_config',
        SYNC_PERIOD=int(timedelta(hours=1).total_seconds()),
        SECONDS_PER_BLOCK=Decimal(12),
        CONFIRMATION_BLOCKS=64,
        CHAIN_ID=5,
        IS_POA=True,
    ),
    GNOSIS: NetworkConfig(
        KEEPER_CONTRACT_ADDRESS=Web3.to_checksum_address(EMPTY_ADDR_HEX),
        KEEPER_GENESIS_BLOCK=BlockNumber(0),
        KEEPER_GENESIS_TIMESTAMP=Timestamp(0),
        ORACLES_CONTRACT_ADDRESS=Web3.to_checksum_address(EMPTY_ADDR_HEX),
        GENESIS_TIMESTAMP=Timestamp(1638993340),
        GENESIS_FORK_VERSION=Web3.to_bytes(hexstr=HexStr('0x00000064')),
        DAO_ENS_ORACLES_KEY='gno_oracles_config',
        SYNC_PERIOD=int(timedelta(days=1).total_seconds()),
        SECONDS_PER_BLOCK=Decimal('6.8'),
        CONFIRMATION_BLOCKS=24,
        CHAIN_ID=100,
        IS_POA=False,
    ),
}
