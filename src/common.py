import aiohttp


async def aiohttp_fetch(session: aiohttp.ClientSession, url: str) -> dict:
    async with session.get(url=url) as response:
        response.raise_for_status()
        data = await response.json()
    return data
