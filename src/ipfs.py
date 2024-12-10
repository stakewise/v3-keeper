from src.clients import ipfs_fetch_client, ipfs_upload_client


async def distribute_json_hash(origin_ipfs_hash: str) -> None:
    if not origin_ipfs_hash:
        return
    if not origin_ipfs_hash.startswith('bafkr'):
        raise ValueError('Only v1 version ipfs hashes can be distributed')
    ipfs_data = await ipfs_fetch_client.fetch_json(origin_ipfs_hash)
    ipfs_hash = await ipfs_upload_client.upload_json(ipfs_data)
    if ipfs_hash != origin_ipfs_hash:
        raise ValueError(
            f'Different IPFS hashes: origin={origin_ipfs_hash}, distributed={ipfs_hash}'
        )
