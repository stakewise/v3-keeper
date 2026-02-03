from web3 import AsyncWeb3

from src.common.clients import get_execution_client
from src.config.settings import L2_EXECUTION_ENDPOINTS

l2_execution_client: AsyncWeb3 | None

if L2_EXECUTION_ENDPOINTS:
    l2_execution_client = get_execution_client(L2_EXECUTION_ENDPOINTS)
else:
    l2_execution_client = None
