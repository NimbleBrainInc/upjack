"""E2E tests for the CRM example as an MCPB bundle.

Builds a real MCPB bundle, runs it with `mpak run --local`,
and tests the running server over stdio — the way a real MCP client connects.
"""

import json
import tempfile
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from .build import build_upjack_bundle
from .conftest import CRM_DIR


@pytest.fixture(scope="module")
def bundle_path():
    """Build the CRM MCPB bundle once for all tests in this module."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = build_upjack_bundle(CRM_DIR, Path(tmpdir), "crm")
        yield path


def _server_params(bundle_path: Path) -> StdioServerParameters:
    return StdioServerParameters(
        command="mpak",
        args=["run", "--local", str(bundle_path)],
    )


@pytest.mark.asyncio
async def test_tools_list(bundle_path):
    """All 31 tools should be registered (5 entities x 6 + seed_data)."""
    async with stdio_client(_server_params(bundle_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            tool_names = {t.name for t in result.tools}

            expected_entity_tools = set()
            for name, plural in [
                ("contact", "contacts"),
                ("company", "companies"),
                ("deal", "deals"),
                ("pipeline", "pipelines"),
                ("activity", "activities"),
            ]:
                expected_entity_tools |= {
                    f"create_{name}",
                    f"get_{name}",
                    f"update_{name}",
                    f"list_{plural}",
                    f"search_{plural}",
                    f"delete_{name}",
                }

            for tool in expected_entity_tools:
                assert tool in tool_names, f"Missing tool: {tool}"
            assert "seed_data" in tool_names
            assert len(tool_names) == 31


@pytest.mark.asyncio
async def test_resources_list(bundle_path):
    """Context + 3 skill resources should be available."""
    async with stdio_client(_server_params(bundle_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_resources()
            uris = {str(r.uri) for r in result.resources}

            assert "upjack://context" in uris
            assert "upjack://skills/lead-qualification" in uris
            assert "upjack://skills/deal-forecasting" in uris
            assert "upjack://skills/follow-up-email" in uris


@pytest.mark.asyncio
async def test_create_contact(bundle_path):
    """Entity creation should work through the bundled MCP server."""
    async with stdio_client(_server_params(bundle_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "create_contact",
                {"data": {"first_name": "Alice", "last_name": "Chen", "email": "alice@test.com"}},
            )
            data = json.loads(result.content[0].text)
            assert data["id"].startswith("ct_")
            assert data["first_name"] == "Alice"
            assert data["status"] == "active"


@pytest.mark.asyncio
async def test_seed_and_list(bundle_path):
    """Seed data loads 5 items; list_contacts returns the 2 seeded contacts."""
    async with stdio_client(_server_params(bundle_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            seed_result = await session.call_tool("seed_data", {})
            seed_data = json.loads(seed_result.content[0].text)
            assert len(seed_data["loaded"]) == 5
            assert seed_data["errors"] == []

            list_result = await session.call_tool("list_contacts", {})
            result_data = json.loads(list_result.content[0].text)
            assert result_data["count"] == 2


@pytest.mark.asyncio
async def test_full_crud_cycle(bundle_path):
    """Create -> get -> update -> search -> delete through MCP."""
    async with stdio_client(_server_params(bundle_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Create
            create_result = await session.call_tool(
                "create_contact",
                {
                    "data": {
                        "first_name": "Bob",
                        "last_name": "Smith",
                        "email": "bob@test.com",
                    }
                },
            )
            contact = json.loads(create_result.content[0].text)
            contact_id = contact["id"]
            assert contact_id.startswith("ct_")

            # Get
            get_result = await session.call_tool("get_contact", {"contact_id": contact_id})
            fetched = json.loads(get_result.content[0].text)
            assert fetched["first_name"] == "Bob"
            assert fetched["email"] == "bob@test.com"

            # Update
            update_result = await session.call_tool(
                "update_contact",
                {"contact_id": contact_id, "data": {"lead_score": 85}},
            )
            updated = json.loads(update_result.content[0].text)
            assert updated["lead_score"] == 85
            assert updated["first_name"] == "Bob"

            # Search
            search_result = await session.call_tool(
                "search_contacts",
                {"query": "Bob"},
            )
            search_data = json.loads(search_result.content[0].text)
            assert search_data["count"] == 1
            assert search_data["entities"][0]["lead_score"] == 85

            # Delete
            delete_result = await session.call_tool("delete_contact", {"contact_id": contact_id})
            deleted = json.loads(delete_result.content[0].text)
            assert deleted["status"] == "deleted"

            # Verify gone from list
            list_result = await session.call_tool("list_contacts", {})
            list_data = json.loads(list_result.content[0].text)
            assert all(c["id"] != contact_id for c in list_data["entities"])
