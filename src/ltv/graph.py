import logging

from eth_typing import ChecksumAddress
from gql import gql
from web3 import Web3
from web3.types import BlockNumber

from src.common.clients import graph_client

logger = logging.getLogger(__name__)


async def graph_get_ostoken_vaults(block_number: BlockNumber) -> list[ChecksumAddress]:
    query = gql(
        """
        query OsTokenVaultsIds($block: Int) {
          networks(block: { number: $block }) {
            osTokenVaultIds
          }
        }
        """
    )
    params = {'block': block_number}

    response = await graph_client.run_query(query, params)
    vaults = response['networks'][0]['osTokenVaultIds']  # pylint: disable=unsubscriptable-object
    return [Web3.to_checksum_address(vault) for vault in vaults]


async def graph_get_vault_max_ltv_allocator(
    vault_address: str, block_number: BlockNumber
) -> ChecksumAddress | None:
    query = gql(
        """
        query AllocatorsQuery($vault: String, $block: Int) {
          allocators(
            block: { number: $block }
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
        'block': block_number,
    }

    response = await graph_client.run_query(query, params)
    allocators = response['allocators']  # pylint: disable=unsubscriptable-object

    if not allocators:
        return None

    return Web3.to_checksum_address(allocators[0]['address'])
