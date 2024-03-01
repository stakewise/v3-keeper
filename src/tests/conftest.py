import os

import aiohttp
import pytest

# set environment variables
os.environ['IPFS_LOCAL_CLIENT_ENDPOINT'] = '/ip4/127.0.0.1/tcp/5001'


@pytest.fixture
async def client_session():
    async with aiohttp.ClientSession() as session:
        yield session
