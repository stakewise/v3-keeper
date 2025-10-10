from gql import gql
from web3 import Web3
from web3.types import BlockNumber, ChecksumAddress

from src.common.clients import graph_client

from .typings import ExitRequest, LeveragePosition, OsTokenExitRequest

DISABLED_LIQ_THRESHOLD = 2**64 - 1


async def graph_get_leverage_positions(block_number: BlockNumber) -> list[LeveragePosition]:
    query = gql(
        """
        query PositionsQuery($block: Int, $first: Int, $skip: Int) {
          leverageStrategyPositions(
            block: { number: $block },
            orderBy: borrowLtv,
            orderDirection: desc,
            first: $first,
            skip: $skip
          ) {
            user
            proxy
            borrowLtv
            vault {
              id
            }
            exitRequest {
              id
              positionTicket
              timestamp
              receiver
              exitQueueIndex
              isClaimed
              isClaimable
              exitedAssets
              totalAssets
              vault {
                id
              }
            }
          }
        }
        """
    )
    params = {'block': block_number}
    response = await graph_client.fetch_pages(query, params=params)
    result = []
    for data in response:
        position = LeveragePosition(
            vault=Web3.to_checksum_address(data['vault']['id']),
            user=Web3.to_checksum_address(data['user']),
            proxy=Web3.to_checksum_address(data['proxy']),
            borrow_ltv=float(data['borrowLtv']),
        )
        if data['exitRequest']:
            position.exit_request = ExitRequest.from_graph(data['exitRequest'])

        result.append(position)
    return result


async def graph_get_allocators(
    ltv: float, addresses: list[ChecksumAddress], block_number: BlockNumber
) -> list[ChecksumAddress]:
    query = gql(
        """
        query AllocatorsQuery(
          $ltv: String,
          $addresses: [String],
          $block: Int,
          $first: Int,
          $skip: Int
        ) {
          allocators(
            block: { number: $block },
            where: { ltv_gt: $ltv, address_in: $addresses },
            orderBy: ltv,
            orderDirection: desc,
            first: $first,
            skip: $skip
          ) {
            address
            vault {
              osTokenConfig {
                liqThresholdPercent
              }
            }
          }
        }
        """
    )
    params = {
        'ltv': str(ltv),
        'addresses': [address.lower() for address in addresses],
        'block': block_number,
    }
    response = await graph_client.fetch_pages(query, params=params)
    result = []
    for data in response:
        vault_liq_threshold = int(data['vault']['osTokenConfig']['liqThresholdPercent'])
        if vault_liq_threshold != DISABLED_LIQ_THRESHOLD:
            result.append(
                Web3.to_checksum_address(data['address']),
            )
    return result


async def graph_ostoken_exit_requests(
    ltv: float, block_number: BlockNumber
) -> list[OsTokenExitRequest]:
    query = gql(
        """
        query ExitRequestsQuery($ltv: String, $block: Int, $first: Int, $skip: Int) {
          osTokenExitRequests(
            block: { number: $block },
            where: {ltv_gt: $ltv}
            first: $first
            skip: $skip
            ) {
            id
            owner
            ltv
            positionTicket
            osTokenShares
            vault {
              id
            }
          }
        }
        """
    )
    params = {'ltv': str(ltv), 'block': block_number}
    response = await graph_client.fetch_pages(query, params=params)

    if not response:
        return []

    exit_requests = await graph_get_exit_requests_by_ids(
        ids=[item['id'] for item in response], block_number=block_number
    )
    id_to_exit_request = {exit_req.id: exit_req for exit_req in exit_requests}

    result = []
    for data in response:
        exit_request = id_to_exit_request[data['id']]
        if exit_request.is_claimed:
            continue

        result.append(
            OsTokenExitRequest(
                id=data['id'],
                vault=Web3.to_checksum_address(data['vault']['id']),
                owner=Web3.to_checksum_address(data['owner']),
                ltv=data['ltv'],
                exit_request=exit_request,
            )
        )

    return result


async def graph_get_leverage_position_owner(proxy: ChecksumAddress) -> ChecksumAddress:
    query = gql(
        """
        query PositionsQuery($proxy: Bytes) {
          leverageStrategyPositions(where: { proxy: $proxy }) {
            user
          }
        }
        """
    )
    params = {'proxy': proxy.lower()}
    response = await graph_client.run_query(query, params)
    return Web3.to_checksum_address(response['leverageStrategyPositions'][0]['user'])


async def graph_get_exit_requests_by_ids(
    ids: list[str], block_number: BlockNumber
) -> list[ExitRequest]:
    query = gql(
        """
        query exitRequestQuery($ids: [String], $block: Int, $first: Int, $skip: Int) {
          exitRequests(
            block: { number: $block },
            where: { id_in: $ids },
            orderBy: id,
            first: $first,
            skip: $skip
          ) {
            id
            positionTicket
            timestamp
            receiver
            exitQueueIndex
            isClaimed
            isClaimable
            exitedAssets
            totalAssets
            vault {
              id
            }
          }
        }
        """
    )
    params = {'block': block_number, 'ids': ids}
    response = await graph_client.fetch_pages(query, params=params)
    result = []
    for data in response:
        result.append(ExitRequest.from_graph(data))
    return result
