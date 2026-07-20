from eth_typing import BlockNumber

from src.common.app_state import Singleton


class OraclesCache(metaclass=Singleton):
    """Process-local, event-driven cache of the oracles protocol config."""

    def __init__(self) -> None:
        self.checkpoint_block: BlockNumber | None = None
        self.config: dict = {}
        self.rewards_threshold: int = 0
