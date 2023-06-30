import json
import logging
import os
from typing import Dict

import backoff
from eth_typing import ChecksumAddress
from hexbytes import HexBytes
from web3 import Web3
from web3.types import EventData

from src.clients import execution_client
from src.config.settings import DEFAULT_RETRY_TIME, NETWORK_CONFIG
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

    @backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
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

    @backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
    async def submit_vote(
        self,
        vote: RewardVoteBody,
        signatures: bytes,
    ) -> None:
        tx = await self.contract.update_rewards(vote, signatures)
        await execution_client.eth.wait_for_transaction_receipt(
            tx, timeout=DEFAULT_RETRY_TIME
        )  # type: ignore
        logger.info('Rewards has been successfully updated. Tx hash: %s', Web3.to_hex(tx))

    @backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
    async def get_rewards_nonce(self) -> int:
        return await self.contract.functions.rewardsNonce().call()  # type: ignore

    @backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
    async def can_update_rewards(self) -> bool:
        """Checks whether keeper allows next update."""
        return await self.contract.functions.canUpdateRewards().call()  # type: ignore

    @backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
    async def get_rewards_threshold(self) -> int:
        return await self.contract.functions.rewardsMinOracles().call()

    @backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
    async def get_validators_threshold(self) -> int:
        return await self.contract.functions.validatorsMinOracles().call()

    @backoff.on_exception(backoff.expo, Exception, max_time=DEFAULT_RETRY_TIME)
    async def get_config_update_events(self) -> list[EventData]:
        events = await self.contract.events.ConfigUpdated.get_logs(  # type: ignore
            fromBlock=NETWORK_CONFIG.KEEPER_GENESIS_BLOCK
        )
        return events


def get_keeper_contract() -> KeeperContract:
    """:returns instance of `Keeper` contract."""
    return KeeperContract(NETWORK_CONFIG.KEEPER_CONTRACT_ADDRESS)


keeper_contract = get_keeper_contract()
