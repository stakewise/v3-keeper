import logging

from eth_typing import BlockIdentifier, BlockNumber, ChecksumAddress
from gql import gql

from src.common.clients import execution_client, graph_client
from src.common.typings import Vault

logger = logging.getLogger(__name__)


async def check_for_graph_node_sync_to_block(
    block_identifier: BlockIdentifier,
) -> None:
    """
    Check if graph node is available and synced to the specified block number of execution node.
    Useful for checking against latest block.
    """
    try:
        graph_block_number = await graph_get_latest_block()
    except Exception as e:
        raise ConnectionError(
            f'The graph node located at {graph_client.endpoint} ' f'is not available: {str(e)}',
        ) from e

    if isinstance(block_identifier, int):
        # Fixed block number
        execution_block_number = block_identifier
    else:
        # Example: block_identifier = 'finalized'
        # Block number is changing on each iteration,
        # so we need to fetch it from execution client
        execution_block_number = (await execution_client.eth.get_block(block_identifier))['number']

    if graph_block_number >= execution_block_number:
        return
    raise ConnectionError(
        f'The graph node located at {graph_client.endpoint} '
        f'is not synced to block: {execution_block_number}',
    )


async def graph_get_vaults(
    vaults: list[ChecksumAddress] | None = None,
    is_meta_vault: bool | None = None,
) -> dict[ChecksumAddress, Vault]:
    """
    Returns mapping from vault address to Vault object
    """
    where_conditions: list[str] = []
    params: dict = {}

    if vaults == []:
        return {}

    if vaults:
        where_conditions.append('id_in: $vaults')
        params['vaults'] = [v.lower() for v in vaults]

    if is_meta_vault is not None:
        where_conditions.append('isMetaVault: $isMetaVault')
        params['isMetaVault'] = is_meta_vault

    where_conditions_str = '\n'.join(where_conditions)
    where_clause = f'where: {{ {where_conditions_str} }}' if where_conditions else ''

    filters = ['first: $first', 'skip: $skip']

    if where_clause:
        filters.append(where_clause)

    query = f"""
        query VaultQuery($first: Int, $skip: Int, $vaults: [String], $isMetaVault: Boolean) {{
            vaults(
                {', '.join(filters)}
            ) {{
                id
                isMetaVault
                subVaults {{
                    subVault
                }}
                canHarvest
                proof
                proofReward
                proofUnlockedMevReward
                rewardsRoot
            }}
        }}
        """

    response = await graph_client.fetch_pages(gql(query), params)

    graph_vaults_map: dict[ChecksumAddress, Vault] = {}

    for vault_item in response:
        vault = Vault.from_graph(vault_item)
        graph_vaults_map[vault.address] = vault

    return graph_vaults_map


async def graph_get_latest_block() -> BlockNumber:
    """
    Returns the last synced block number of the graph node.
    """
    query = gql(
        '''
        query Meta {
          _meta {
            block {
              number
            }
          }
        }
    '''
    )
    response = await graph_client.run_query(query)
    graph_block_number = response['_meta']['block']['number']
    return BlockNumber(graph_block_number)
