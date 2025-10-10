import logging

from eth_typing import ChecksumAddress
from gql import gql
from web3 import Web3

from src.common.clients import graph_client

logger = logging.getLogger(__name__)


async def graph_get_ostoken_vaults() -> list[ChecksumAddress]:
    query = gql(
        """
        query OsTokenVaultsIds {
          networks {
            osTokenVaultIds
          }
        }
        """
    )

    response = await graph_client.run_query(query)
    vaults = response['networks'][0]['osTokenVaultIds']  # pylint: disable=unsubscriptable-object
    return [Web3.to_checksum_address(vault) for vault in vaults]


async def graph_get_vault_max_ltv_allocator(vault_address: str) -> ChecksumAddress | None:
    query = gql(
        """
        query AllocatorsQuery($vault: String) {
          allocators(
            first: 1
            orderBy: ltv
            orderDirection: desc
            where: { vault: $vault }
          ) {
            address
          }
        }
        """
    )
    params = {
        'vault': vault_address.lower(),
    }

    response = await graph_client.run_query(query, params)
    allocators = response['allocators']  # pylint: disable=unsubscriptable-object

    if not allocators:
        return None

    return Web3.to_checksum_address(allocators[0]['address'])
