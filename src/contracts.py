import json
import logging
import os
from typing import Dict

from eth_typing import BlockNumber, ChecksumAddress, HexStr
from web3 import Web3
from web3.types import EventData, TxParams

from src.clients import execution_client
from src.config.settings import NETWORK_CONFIG
from src.distributor.typings import DistributorRewardVoteBody
from src.typings import RewardVoteBody

logger = logging.getLogger(__name__)

EVENTS_BLOCKS_RANGE_INTERVAL = 24 * 60 * 60  # 24 hrs


def _load_abi(abi_path: str) -> Dict:
    current_dir = os.path.dirname(__file__)
    with open(os.path.join(current_dir, abi_path)) as f:
        return json.load(f)


class ContractWrapper:
    abi_path: str

    def __init__(self, address: ChecksumAddress):
        self.contract = execution_client.eth.contract(address=address, abi=_load_abi(self.abi_path))

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

    async def update_rewards(
        self, vote: RewardVoteBody, signatures: bytes, tx_params: TxParams | None = None
    ) -> HexStr:
        if not tx_params:
            tx_params = {}
        tx_hash = await self.contract.functions.updateRewards(
            (
                vote.root,
                vote.avg_reward_per_second,
                vote.update_timestamp,
                vote.ipfs_hash,
                signatures,
            ),
        ).transact(tx_params)

        return Web3.to_hex(tx_hash)

    async def get_rewards_nonce(self) -> int:
        return await self.contract.functions.rewardsNonce().call()

    async def can_update_rewards(self) -> bool:
        """Checks whether keeper allows next update."""
        return await self.contract.functions.canUpdateRewards().call()

    async def get_rewards_threshold(self) -> int:
        return await self.contract.functions.rewardsMinOracles().call()

    async def get_validators_threshold(self) -> int:
        return await self.contract.functions.validatorsMinOracles().call()

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
        tx_hash = await self.contract.functions.setRewardsRoot(
            vote.root,
            vote.ipfs_hash,
            b''.join(Web3.to_bytes(hexstr=signature) for signature in signatures),
        ).transact()

        return Web3.to_hex(tx_hash)


merkle_distributor_contract = MerkleDistributorContract(
    NETWORK_CONFIG.MERKLE_DISTRIBUTOR_CONTRACT_ADDRESS
)
keeper_contract = KeeperContract(NETWORK_CONFIG.KEEPER_CONTRACT_ADDRESS)
