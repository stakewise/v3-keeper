import aiohttp
import pytest


@pytest.fixture
async def client_session():
    async with aiohttp.ClientSession() as session:
        yield session
