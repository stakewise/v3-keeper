import json
import os
from typing import Dict

import backoff
from eth_typing import ChecksumAddress, HexStr
from web3.contract import AsyncContract

from src.clients import execution_client
from src.config.settings import DEFAULT_RETRY_TIME, NETWORK_CONFIG
from src.typings import RewardVoteBody


def _load_abi(abi_path: str) -> Dict:
    current_dir = os.path.dirname(__file__)
    with open(os.path.join(current_dir, abi_path)) as f:
        return json.load(f)


class KeeperContract:
    abi_path = 'abi/IKeeper.json'

    def __init__(self, address: ChecksumAddress):
        self.contract = execution_client.eth.contract(
            address=address, abi=_load_abi(self.abi_path)
        )

    @backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
    async def set_rewards_root(self, vote: RewardVoteBody, signatures: bytes) -> HexStr:
        return await self.contract.functions.setRewardsRoot(
            (
                vote.root,
                vote.avg_reward_per_second,
                vote.update_timestamp,
                vote.ipfs_hash,
                signatures,
            ),
        ).transact()  # type: ignore

    @backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
    async def get_rewards_nonce(self) -> int:
        return await self.contract.functions.rewardsNonce().call()  # type: ignore

    @backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
    async def can_update_rewards(self) -> bool:
        """Checks whether keeper allows next update."""
        return await self.contract.functions.canUpdateRewards().call()  # type: ignore


def get_keeper_contract() -> KeeperContract:
    """:returns instance of `Keeper` contract."""
    return KeeperContract(NETWORK_CONFIG.KEEPER_CONTRACT_ADDRESS)


def get_oracles_contract() -> AsyncContract:
    """:returns instance of `Oracle` contract."""
    abi_path = 'abi/IOracles.json'
    return execution_client.eth.contract(
        address=NETWORK_CONFIG.ORACLES_CONTRACT_ADDRESS, abi=_load_abi(abi_path)
    )  # type: ignore


keeper_contract = get_keeper_contract()
oracles_contract = get_oracles_contract()
