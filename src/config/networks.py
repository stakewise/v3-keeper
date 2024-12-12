from dataclasses import asdict, dataclass

from ens.constants import EMPTY_ADDR_HEX
from sw_utils.networks import CHIADO, GNOSIS, HOLESKY, MAINNET
from sw_utils.networks import NETWORKS as BASE_NETWORKS
from sw_utils.networks import BaseNetworkConfig
from web3 import Web3
from web3.types import ChecksumAddress, Wei

ENABLED_NETWORKS = [MAINNET, HOLESKY, GNOSIS, CHIADO]


@dataclass
class NetworkConfig(BaseNetworkConfig):
    SYMBOL: str
    KEEPER_MIN_BALANCE: Wei
    V2_FEES_ESCROW_CONTRACT_ADDRESS: ChecksumAddress


NETWORKS = {
    MAINNET: NetworkConfig(
        **asdict(BASE_NETWORKS[MAINNET]),
        SYMBOL='ETH',
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
        V2_FEES_ESCROW_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0x6b333B20fBae3c5c0969dd02176e30802e2fbBdB'
        ),
    ),
    HOLESKY: NetworkConfig(
        **asdict(BASE_NETWORKS[HOLESKY]),
        SYMBOL='HolETH',
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
        V2_FEES_ESCROW_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0x9e75255193289D641E893a28E3474F71200B05e6'
        ),
    ),
    GNOSIS: NetworkConfig(
        **asdict(BASE_NETWORKS[GNOSIS]),
        SYMBOL='xDAI',
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
        V2_FEES_ESCROW_CONTRACT_ADDRESS=Web3.to_checksum_address(EMPTY_ADDR_HEX),
    ),
    CHIADO: NetworkConfig(
        **asdict(BASE_NETWORKS[CHIADO]),
        SYMBOL='xDAI',
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
        V2_FEES_ESCROW_CONTRACT_ADDRESS=Web3.to_checksum_address(EMPTY_ADDR_HEX),
    ),
}
