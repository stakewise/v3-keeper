import json
import os
from typing import Dict

from web3.contract import AsyncContract

from src.clients import execution_client
from src.config.settings import NETWORK_CONFIG


def _load_abi(abi_path: str) -> Dict:
    current_dir = os.path.dirname(__file__)
    with open(os.path.join(current_dir, abi_path)) as f:
        return json.load(f)


def get_keeper_contract() -> AsyncContract:
    """:returns instance of `Keeper` contract."""
    abi_path = 'abi/IKeeper.json'
    return execution_client.eth.contract(
        address=NETWORK_CONFIG.KEEPER_CONTRACT_ADDRESS, abi=_load_abi(abi_path)
    )  # type: ignore


def get_oracles_contract() -> AsyncContract:
    """:returns instance of `Oracle` contract."""
    abi_path = 'abi/IOracles.json'
    return execution_client.eth.contract(
        address=NETWORK_CONFIG.ORACLES_CONTRACT_ADDRESS, abi=_load_abi(abi_path)
    )  # type: ignore


keeper_contract = get_keeper_contract()
oracles_contract = get_oracles_contract()
