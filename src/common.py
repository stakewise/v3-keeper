async def aiohttp_fetch(session, url) -> dict:
    async with session.get(url=url) as response:
        response.raise_for_status()
        data = await response.json()
    return data
