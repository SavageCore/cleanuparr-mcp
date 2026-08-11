"""Opt-in smoke tests for a live Cleanuparr instance."""

import os

import pytest
from fastmcp import Client

import cleanuparr_mcp

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("CLEANUPARR_URL"),
        reason="requires CLEANUPARR_URL (and normally CLEANUPARR_API_KEY)",
    ),
]


@pytest.fixture(autouse=True)
def configure_client():
    cleanuparr_mcp._client = cleanuparr_mcp.build_client(
        os.environ["CLEANUPARR_URL"], os.environ.get("CLEANUPARR_API_KEY")
    )
    yield


async def call(name, **kwargs):
    async with Client(cleanuparr_mcp.mcp) as client:
        return await client.call_tool(name, kwargs)


async def test_health():
    result = await call("cleanuparr_health")
    assert result.data is not None


async def test_status_and_jobs():
    assert (await call("cleanuparr_get_status")).data is not None
    assert (await call("cleanuparr_list_jobs")).data is not None
