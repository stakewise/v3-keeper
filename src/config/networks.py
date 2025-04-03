from dataclasses import asdict, dataclass

from sw_utils.networks import CHIADO, GNOSIS, HOODI, MAINNET
from sw_utils.networks import NETWORKS as BASE_NETWORKS
from sw_utils.networks import BaseNetworkConfig
from web3 import Web3
from web3.types import Wei

ENABLED_NETWORKS = [MAINNET, HOODI, GNOSIS, CHIADO]


@dataclass
class NetworkConfig(BaseNetworkConfig):
    SYMBOL: str
    KEEPER_MIN_BALANCE: Wei


NETWORKS = {
    MAINNET: NetworkConfig(
        **asdict(BASE_NETWORKS[MAINNET]),
        SYMBOL='ETH',
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
    ),
    HOODI: NetworkConfig(
        **asdict(BASE_NETWORKS[HOODI]),
        SYMBOL='HoodiETH',
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
    ),
    GNOSIS: NetworkConfig(
        **asdict(BASE_NETWORKS[GNOSIS]),
        SYMBOL='xDAI',
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
    ),
    CHIADO: NetworkConfig(
        **asdict(BASE_NETWORKS[CHIADO]),
        SYMBOL='xDAI',
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
    ),
}
