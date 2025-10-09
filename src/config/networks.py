from dataclasses import asdict, dataclass

from sw_utils.networks import CHIADO, GNOSIS, HOODI, MAINNET
from sw_utils.networks import NETWORKS as BASE_NETWORKS
from sw_utils.networks import BaseNetworkConfig
from web3 import Web3
from web3.types import ChecksumAddress, Wei

SEPOLIA = 'sepolia'

ENABLED_NETWORKS = [MAINNET, HOODI, GNOSIS, CHIADO, SEPOLIA]


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


@dataclass
class PriceNetworkConfig:
    # TARGET_CHAIN is not what eth_chainId returns.
    # It is internal id used in PriceFeedSender contract.
    TARGET_CHAIN: int
    # PriceFeedReceiver contract address on target network
    TARGET_ADDRESS: ChecksumAddress
    # PriceFeed contract address on target network
    TARGET_PRICE_FEED_CONTRACT_ADDRESS: ChecksumAddress
    # PriceFeedSender contract address on sender network
    PRICE_FEED_SENDER_CONTRACT_ADDRESS: ChecksumAddress


PRICE_NETWORKS: dict[str, PriceNetworkConfig | None] = {
    MAINNET: PriceNetworkConfig(
        # TARGET_CHAIN is not what eth_chainId returns.
        # It is internal id used in PriceFeedSender contract.
        TARGET_CHAIN=23,
        # PriceFeedReceiver contract address on Arbitrum
        TARGET_ADDRESS=Web3.to_checksum_address('0xbd335c16c94be8c4dd073ae376ddf78bec1858df'),
        # PriceFeed contract address on Arbitrum
        TARGET_PRICE_FEED_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0xba74737a078c05500dd98c970909e4a3b90c35c6'
        ),
        # PriceFeedSender contract address on Mainnet
        PRICE_FEED_SENDER_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0xf7d4e7273e5015c96728a6b02f31c505ee184603'
        ),
    ),
    HOODI: None,
    GNOSIS: None,
    CHIADO: None,
    SEPOLIA: PriceNetworkConfig(
        # TARGET_CHAIN is not what eth_chainId returns.
        # It is internal id used in PriceFeedSender contract.
        TARGET_CHAIN=10003,
        # PriceFeedReceiver contract address on Arbitrum Sepolia
        TARGET_ADDRESS=Web3.to_checksum_address('0x744836a91f5151c6ef730eb7e07c232997debaaa'),
        # PriceFeed contract address on Arbitrum Sepolia
        TARGET_PRICE_FEED_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0x4026affabd9032bcc87fa05c02f088905f3dc09b'
        ),
        # PriceFeedSender contract address on Sepolia
        PRICE_FEED_SENDER_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0xe572a8631a49ec4c334812bb692beecf934ac4e9'
        ),
    ),
}
