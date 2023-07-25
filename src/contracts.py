import json
import logging
import os
from typing import Dict

from eth_typing import ChecksumAddress
from hexbytes import HexBytes
from web3.types import EventData

from src.clients import execution_client
from src.config.settings import NETWORK_CONFIG
from src.typings import RewardVoteBody

logger = logging.getLogger(__name__)


def _load_abi(abi_path: str) -> Dict:
    current_dir = os.path.dirname(__file__)
    with open(os.path.join(current_dir, abi_path)) as f:
        return json.load(f)


class KeeperContract:
    abi_path = 'abi/IKeeper.json'

    def __init__(self, address: ChecksumAddress):
        self.contract = execution_client.eth.contract(address=address, abi=_load_abi(self.abi_path))

    async def update_rewards(self, vote: RewardVoteBody, signatures: bytes) -> HexBytes:
        return await self.contract.functions.updateRewards(
            (
                vote.root,
                vote.avg_reward_per_second,
                vote.update_timestamp,
                vote.ipfs_hash,
                signatures,
            ),
        ).transact()  # type: ignore

    async def get_rewards_nonce(self) -> int:
        return await self.contract.functions.rewardsNonce().call()

    async def can_update_rewards(self) -> bool:
        """Checks whether keeper allows next update."""
        return await self.contract.functions.canUpdateRewards().call()

    async def get_rewards_threshold(self) -> int:
        return await self.contract.functions.rewardsMinOracles().call()

    async def get_validators_threshold(self) -> int:
        return await self.contract.functions.validatorsMinOracles().call()

    async def get_config_update_events(self) -> list[EventData]:
        events = await self.contract.events.ConfigUpdated.get_logs(  # type: ignore
            fromBlock=NETWORK_CONFIG.KEEPER_GENESIS_BLOCK
        )
        return events


keeper_contract = KeeperContract(NETWORK_CONFIG.KEEPER_CONTRACT_ADDRESS)
