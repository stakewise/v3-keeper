from dataclasses import asdict, dataclass

from ens.constants import EMPTY_ADDR_HEX
from sw_utils.networks import CHIADO, GNOSIS, HOODI, MAINNET
from sw_utils.networks import NETWORKS as BASE_NETWORKS
from sw_utils.networks import BaseNetworkConfig
from web3 import Web3
from web3.types import ChecksumAddress, Wei

SEPOLIA = 'sepolia'

ENABLED_NETWORKS = [MAINNET, HOODI, GNOSIS, CHIADO, SEPOLIA]

ZERO_CHECKSUM_ADDRESS = Web3.to_checksum_address(EMPTY_ADDR_HEX)  # noqa


@dataclass
class NetworkConfig(BaseNetworkConfig):
    SYMBOL: str
    KEEPER_MIN_BALANCE: Wei
    STRATEGY_REGISTRY_CONTRACT_ADDRESS: ChecksumAddress
    OSTOKEN_VAULT_ESCROW_CONTRACT_ADDRESS: ChecksumAddress
    LEVERAGE_STRATEGY_ID: str
    VAULT_USER_LTV_TRACKER_CONTRACT_ADDRESS: ChecksumAddress


NETWORKS = {
    MAINNET: NetworkConfig(
        **asdict(BASE_NETWORKS[MAINNET]),
        SYMBOL='ETH',
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
        LEVERAGE_STRATEGY_ID='0x8b74cefe9f33d72ccd3521e6d331272921607e547c75c914c2c56cfdad9defed',
        STRATEGY_REGISTRY_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0x90b82E4b3aa385B4A02B7EBc1892a4BeD6B5c465'
        ),
        OSTOKEN_VAULT_ESCROW_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0x09e84205DF7c68907e619D07aFD90143c5763605'
        ),
        VAULT_USER_LTV_TRACKER_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0xe0Ae8B04922d6e3fA06c2496A94EF2875EFcC7BB'
        ),
    ),
    HOODI: NetworkConfig(
        **asdict(BASE_NETWORKS[HOODI]),
        SYMBOL='HoodiETH',
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
        LEVERAGE_STRATEGY_ID='0x8b74cefe9f33d72ccd3521e6d331272921607e547c75c914c2c56cfdad9defed',
        STRATEGY_REGISTRY_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0x6A2911F94da08Da01158d645Bf85152b338E015D'
        ),
        OSTOKEN_VAULT_ESCROW_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0xdC1347cC04d4a8945b98A09C3c5585286bbA5C2B'
        ),
        VAULT_USER_LTV_TRACKER_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0xcF619F9Dd8eB483239de953251fd13cB0F977c6C'
        ),
    ),
    GNOSIS: NetworkConfig(
        **asdict(BASE_NETWORKS[GNOSIS]),
        SYMBOL='xDAI',
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
        LEVERAGE_STRATEGY_ID='',
        STRATEGY_REGISTRY_CONTRACT_ADDRESS=ZERO_CHECKSUM_ADDRESS,
        OSTOKEN_VAULT_ESCROW_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0x28F325dD287a5984B754d34CfCA38af3A8429e71'
        ),
        VAULT_USER_LTV_TRACKER_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0xdEa72c54f63470349CE2dC12f8232FE00241abE6'
        ),
    ),
    CHIADO: NetworkConfig(
        **asdict(BASE_NETWORKS[CHIADO]),
        SYMBOL='xDAI',
        KEEPER_MIN_BALANCE=Web3.to_wei('0.01', 'ether'),
        LEVERAGE_STRATEGY_ID='',
        STRATEGY_REGISTRY_CONTRACT_ADDRESS=ZERO_CHECKSUM_ADDRESS,
        OSTOKEN_VAULT_ESCROW_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0x00aa8A78d88a9865b5b0F4ce50c3bB018c93FBa7'
        ),
        VAULT_USER_LTV_TRACKER_CONTRACT_ADDRESS=Web3.to_checksum_address(
            '0xe0Ae8B04922d6e3fA06c2496A94EF2875EFcC7BB'
        ),
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
