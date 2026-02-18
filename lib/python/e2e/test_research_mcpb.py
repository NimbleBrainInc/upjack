"""E2E tests for the Research Assistant example as an MCPB bundle.

Builds a real MCPB bundle, runs it with `mpak run --local`,
and tests the running server over stdio.
"""

import json
import tempfile
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from .build import build_upjack_bundle
from .conftest import RESEARCH_DIR


@pytest.fixture(scope="module")
def bundle_path():
    """Build the Research Assistant MCPB bundle once for all tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = build_upjack_bundle(RESEARCH_DIR, Path(tmpdir), "research-assistant")
        yield path


def _server_params(bundle_path: Path) -> StdioServerParameters:
    return StdioServerParameters(
        command="mpak",
        args=["run", "--local", str(bundle_path)],
    )


@pytest.mark.asyncio
async def test_tools_list(bundle_path):
    """All 25 tools should be registered (4 entities x 6 + seed_data)."""
    async with stdio_client(_server_params(bundle_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            tool_names = {t.name for t in result.tools}

            for name, plural in [
                ("topic", "topics"),
                ("source", "sources"),
                ("note", "notes"),
                ("report", "reports"),
            ]:
                assert f"create_{name}" in tool_names, f"Missing create_{name}"
                assert f"get_{name}" in tool_names, f"Missing get_{name}"
                assert f"update_{name}" in tool_names, f"Missing update_{name}"
                assert f"list_{plural}" in tool_names, f"Missing list_{plural}"
                assert f"search_{plural}" in tool_names, f"Missing search_{plural}"
                assert f"delete_{name}" in tool_names, f"Missing delete_{name}"

            assert "seed_data" in tool_names
            assert len(tool_names) == 25


@pytest.mark.asyncio
async def test_create_topic(bundle_path):
    """Entity creation should work through the bundled server."""
    async with stdio_client(_server_params(bundle_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "create_topic",
                {"data": {"title": "Test Topic", "priority": "high"}},
            )
            data = json.loads(result.content[0].text)
            assert data["id"].startswith("top_")
            assert data["title"] == "Test Topic"


@pytest.mark.asyncio
async def test_seed_data(bundle_path):
    """Seed loads 2 topics from sample-topics.json."""
    async with stdio_client(_server_params(bundle_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            seed_result = await session.call_tool("seed_data", {})
            seed_data = json.loads(seed_result.content[0].text)
            assert len(seed_data["loaded"]) == 2
            assert seed_data["errors"] == []

            list_result = await session.call_tool("list_topics", {})
            topics = json.loads(list_result.content[0].text)
            assert len(topics) == 2
