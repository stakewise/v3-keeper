from eth_account import Account

from src.config.settings import PRIVATE_KEY

keeper_account = Account().from_key(PRIVATE_KEY)
