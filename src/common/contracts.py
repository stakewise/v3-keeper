import asyncio
import json
import logging
import os
from typing import Dict

from eth_typing import BlockNumber, ChecksumAddress, HexStr
from hexbytes import HexBytes
from web3 import AsyncWeb3, Web3
from web3.contract.async_contract import AsyncContractFunction, AsyncContractFunctions
from web3.types import EventData, TxParams, Wei

from src.common.clients import execution_client, gas_manager
from src.config.settings import (
    ATTEMPTS_WITH_DEFAULT_GAS,
    NETWORK_CONFIG,
    PRICE_NETWORK_CONFIG,
)
from src.distributor.typings import DistributorRewardVoteBody
from src.ltv.typings import HarvestParams
from src.price.clients import l2_execution_client
from src.rewards.typings import RewardVoteBody

logger = logging.getLogger(__name__)

EVENTS_BLOCKS_RANGE_INTERVAL = 24 * 60 * 60  # 24 hrs


def _load_abi(abi_path: str) -> Dict:
    current_dir = os.path.dirname(__file__)
    with open(os.path.join(current_dir, abi_path)) as f:
        return json.load(f)


class ContractWrapper:
    abi_path: str

    def __init__(self, address: ChecksumAddress, client: AsyncWeb3 | None = None) -> None:
        self.address = address
        client = client or execution_client
        self.contract = client.eth.contract(address=address, abi=_load_abi(self.abi_path))

    @property
    def functions(self) -> AsyncContractFunctions:
        return self.contract.functions

    def encode_abi(self, fn_name: str, args: list | None = None) -> HexStr:
        return self.contract.encodeABI(fn_name=fn_name, args=args)

    @staticmethod
    def _get_zero_harvest_params() -> HarvestParams:
        return HarvestParams(
            rewards_root=HexBytes(b'\x00' * 32), reward=Wei(0), unlocked_mev_reward=Wei(0), proof=[]
        )

    async def _get_last_event(
        self,
        event_name: str,
        from_block: BlockNumber,
        to_block: BlockNumber,
    ) -> EventData | None:
        blocks_range = int(EVENTS_BLOCKS_RANGE_INTERVAL // NETWORK_CONFIG.SECONDS_PER_BLOCK)
        event_cls = getattr(self.contract.events, event_name)
        while to_block >= from_block:
            events = await event_cls.get_logs(
                fromBlock=BlockNumber(max(to_block - blocks_range, from_block)),
                toBlock=to_block,
            )
            if events:
                return events[-1]
            to_block = BlockNumber(to_block - blocks_range - 1)
        return None


class KeeperContract(ContractWrapper):
    abi_path = 'abi/IKeeper.json'

    async def update_rewards(self, vote: RewardVoteBody, signatures: bytes) -> HexStr:
        tx_function = self.contract.functions.updateRewards(
            (
                vote.root,
                vote.avg_reward_per_second,
                vote.update_timestamp,
                vote.ipfs_hash,
                signatures,
            ),
        )

        tx_hash = await transaction_gas_wrapper(tx_function=tx_function)
        return Web3.to_hex(tx_hash)

    async def get_rewards_nonce(self) -> int:
        return await self.contract.functions.rewardsNonce().call()

    async def can_update_rewards(self) -> bool:
        """Checks whether keeper allows next update."""
        return await self.contract.functions.canUpdateRewards().call()

    async def get_rewards_threshold(self) -> int:
        return await self.contract.functions.rewardsMinOracles().call()

    async def can_harvest(
        self, vault: ChecksumAddress, block_number: BlockNumber | None = None
    ) -> bool:
        return await self.contract.functions.canHarvest(vault).call(block_identifier=block_number)

    async def get_config_update_event(self) -> EventData | None:
        to_block = await execution_client.eth.get_block_number()

        event = await self._get_last_event(
            event_name='ConfigUpdated',
            from_block=NETWORK_CONFIG.KEEPER_GENESIS_BLOCK,
            to_block=to_block,
        )
        return event


class MerkleDistributorContract(ContractWrapper):
    abi_path = 'abi/IMerkleDistributor.json'

    async def rewards_root(self) -> HexStr:
        rewards_root = await self.contract.functions.rewardsRoot().call()
        return Web3.to_hex(rewards_root)

    async def nonce(self) -> int:
        return await self.contract.functions.nonce().call()

    async def rewards_min_oracles(self) -> int:
        return await self.contract.functions.rewardsMinOracles().call()

    async def get_next_rewards_root_update_timestamp(self) -> int:
        return await self.contract.functions.getNextRewardsRootUpdateTimestamp().call()

    async def set_rewards_root(
        self, vote: DistributorRewardVoteBody, signatures: list[HexStr]
    ) -> HexStr:
        tx_function = self.contract.functions.setRewardsRoot(
            vote.root,
            vote.ipfs_hash,
            b''.join(Web3.to_bytes(hexstr=signature) for signature in signatures),
        )

        tx_hash = await transaction_gas_wrapper(tx_function=tx_function)
        return Web3.to_hex(tx_hash)


class MulticallContract(ContractWrapper):
    abi_path = 'abi/Multicall.json'

    async def aggregate(
        self,
        data: list[tuple[ChecksumAddress, HexStr]],
        block_number: BlockNumber | None = None,
    ) -> tuple[BlockNumber, list]:
        return await self.contract.functions.aggregate(data).call(block_identifier=block_number)


class PriceFeedContract(ContractWrapper):
    abi_path = 'abi/IPriceFeed.json'


class PriceFeedSenderContract(ContractWrapper):
    abi_path = 'abi/IPriceFeedSender.json'


class VaultUserLTVTrackerContract(ContractWrapper):
    abi_path = 'abi/IVaultUserLtvTracker.json'

    async def get_max_ltv_user(self, vault: ChecksumAddress) -> ChecksumAddress:
        user = await self.contract.functions.vaultToUser(vault).call()
        return Web3.to_checksum_address(user)

    async def get_vault_max_ltv(
        self, vault: ChecksumAddress, harvest_params: HarvestParams | None
    ) -> int:
        # Create zero harvest params in case the vault has no rewards yet
        if harvest_params is None:
            harvest_params = self._get_zero_harvest_params()

        return await self.contract.functions.getVaultMaxLtv(
            vault,
            (
                harvest_params.rewards_root,
                harvest_params.reward,
                harvest_params.unlocked_mev_reward,
                harvest_params.proof,
            ),
        ).call()

    async def update_vault_max_ltv_user(
        self, vault: ChecksumAddress, user: ChecksumAddress, harvest_params: HarvestParams | None
    ) -> HexBytes:
        # Create zero harvest params in case the vault has no rewards yet
        if harvest_params is None:
            harvest_params = self._get_zero_harvest_params()

        tx_function = self.contract.functions.updateVaultMaxLtvUser(
            vault,
            user,
            (
                harvest_params.rewards_root,
                harvest_params.reward,
                harvest_params.unlocked_mev_reward,
                harvest_params.proof,
            ),
        )
        return await transaction_gas_wrapper(tx_function=tx_function)


class LeverageStrategyContract(ContractWrapper):
    abi_path = 'abi/ILeverageStrategy.json'


class StrategyProxyContract(ContractWrapper):
    abi_path = 'abi/IStrategyProxy.json'

    async def get_owner(self) -> ChecksumAddress:
        owner = await self.contract.functions.owner().call()
        return Web3.to_checksum_address(owner)


class OsTokenVaultEscrowContract(ContractWrapper):
    abi_path = 'abi/IOsTokenVaultEscrow.json'

    async def liq_threshold_percent(self) -> int:
        return await self.contract.functions.liqThresholdPercent().call()


class StrategiesRegistryContract(ContractWrapper):
    abi_path = 'abi/IStrategyRegistry.json'

    async def get_vault_ltv_percent(self, strategy_id: str) -> int:
        value = await self.contract.functions.getStrategyConfig(
            strategy_id, 'vaultForceExitLtvPercent'
        ).call()
        return Web3.to_int(value)

    async def get_borrow_ltv_percent(self, strategy_id: str) -> int:
        value = await self.contract.functions.getStrategyConfig(
            strategy_id, 'borrowForceExitLtvPercent'
        ).call()
        return Web3.to_int(value)


target_price_feed_contract = PriceFeedContract(
    address=PRICE_NETWORK_CONFIG.TARGET_PRICE_FEED_CONTRACT_ADDRESS,
    client=l2_execution_client,
)

price_feed_sender_contract = PriceFeedSenderContract(
    PRICE_NETWORK_CONFIG.PRICE_FEED_SENDER_CONTRACT_ADDRESS
)

merkle_distributor_contract = MerkleDistributorContract(
    NETWORK_CONFIG.MERKLE_DISTRIBUTOR_CONTRACT_ADDRESS
)
keeper_contract = KeeperContract(NETWORK_CONFIG.KEEPER_CONTRACT_ADDRESS)

multicall_contract = MulticallContract(
    address=NETWORK_CONFIG.MULTICALL_CONTRACT_ADDRESS,
)

vault_user_ltv_tracker_contract = VaultUserLTVTrackerContract(
    address=NETWORK_CONFIG.VAULT_USER_LTV_TRACKER_CONTRACT_ADDRESS,
)

strategy_registry_contract = StrategiesRegistryContract(
    address=NETWORK_CONFIG.STRATEGY_REGISTRY_CONTRACT_ADDRESS,
)

ostoken_vault_escrow_contract = OsTokenVaultEscrowContract(
    address=NETWORK_CONFIG.OSTOKEN_VAULT_ESCROW_CONTRACT_ADDRESS,
)


async def get_strategy_proxy_contract(proxy: ChecksumAddress) -> StrategyProxyContract:
    return StrategyProxyContract(
        address=proxy,
    )


async def get_leverage_strategy_contract(proxy: ChecksumAddress) -> LeverageStrategyContract:
    proxy_contract = await get_strategy_proxy_contract(proxy)
    leverage_strategy_address = await proxy_contract.get_owner()
    return LeverageStrategyContract(
        address=leverage_strategy_address,
    )


async def transaction_gas_wrapper(
    tx_function: AsyncContractFunction, tx_params: TxParams | None = None
) -> HexBytes:
    """Handles periods with high gas in the network."""
    if not tx_params:
        tx_params = {}

    # trying to submit with basic gas
    for i in range(ATTEMPTS_WITH_DEFAULT_GAS):
        try:
            return await tx_function.transact(tx_params)
        except ValueError as e:
            # Handle only FeeTooLow error
            code = None
            if e.args and isinstance(e.args[0], dict):
                code = e.args[0].get('code')
            if not code or code != -32010:
                raise e
            logger.warning(e)
            if i < ATTEMPTS_WITH_DEFAULT_GAS - 1:  # skip last sleep
                await asyncio.sleep(NETWORK_CONFIG.SECONDS_PER_BLOCK)

    # use high priority fee
    tx_params = tx_params | await gas_manager.get_high_priority_tx_params()
    return await tx_function.transact(tx_params)
