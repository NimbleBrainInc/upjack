"""Tests for upjack.server — MCP server generation from Upjack manifests."""

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from upjack.server import (
    _build_instructions,
    _describe_schema_fields,
    create_server,
    main,
)

# ---------------------------------------------------------------------------
# Async helpers for MCP Client interaction
# ---------------------------------------------------------------------------


def _run(coro):
    """Run a coroutine synchronously."""
    return asyncio.run(coro)


async def _list_tool_names(mcp) -> set[str]:
    from fastmcp import Client

    async with Client(mcp) as client:
        tools = await client.list_tools()
        return {t.name for t in tools}


async def _call_tool(mcp, name: str, arguments: dict | None = None) -> Any:
    from fastmcp import Client

    async with Client(mcp) as client:
        result = await client.call_tool(name, arguments or {})
        if not result.content:
            return None
        return json.loads(result.content[0].text)


async def _list_resource_uris(mcp) -> set[str]:
    from fastmcp import Client

    async with Client(mcp) as client:
        resources = await client.list_resources()
        return {str(r.uri) for r in resources}


async def _read_resource(mcp, uri: str) -> str:
    from fastmcp import Client

    async with Client(mcp) as client:
        # Returns list[TextResourceContents | BlobResourceContents]
        contents = await client.read_resource(uri)
        return contents[0].text


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_manifest(
    tmp_path: Path,
    entities: list[dict],
    *,
    context: str | None = None,
    skills: list[dict] | None = None,
    seed: dict | None = None,
    display_name: str = "Test App",
) -> Path:
    """Create a manifest with schema files on disk."""
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir(exist_ok=True)

    for ent in entities:
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
        }
        schema_file = f"schemas/{ent['name']}.schema.json"
        (tmp_path / schema_file).write_text(json.dumps(schema))
        ent.setdefault("schema", schema_file)

    upjack: dict[str, Any] = {
        "upjack_version": "0.1",
        "namespace": "test",
        "display": {"name": display_name},
        "entities": list(entities),
    }
    if context:
        upjack["context"] = context
    if skills:
        upjack["skills"] = skills
    if seed:
        upjack["seed"] = seed

    manifest = {
        "manifest_version": "0.4",
        "name": "test-app",
        "version": "1.0.0",
        "title": "Test App",
        "server": None,
        "_meta": {"ai.nimblebrain/upjack": upjack},
    }

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return manifest_path


# ===========================================================================
# Unit tests for pure functions
# ===========================================================================


class TestDescribeSchemaFields:
    """Test _describe_schema_fields — generates human-readable field summaries."""

    def test_none_returns_empty(self):
        assert _describe_schema_fields(None) == ""

    def test_no_properties_returns_empty(self):
        assert _describe_schema_fields({}) == ""
        assert _describe_schema_fields({"properties": {}}) == ""

    def test_only_base_entity_fields_returns_empty(self):
        """Base entity fields (id, type, version, etc.) should be skipped."""
        schema = {
            "properties": {
                "id": {"type": "string"},
                "type": {"type": "string"},
                "version": {"type": "integer"},
                "created_at": {"type": "string"},
                "updated_at": {"type": "string"},
                "created_by": {"type": "string"},
                "status": {"type": "string"},
                "tags": {"type": "array"},
                "source": {"type": "object"},
                "relationships": {"type": "array"},
            }
        }
        assert _describe_schema_fields(schema) == ""

    def test_separates_required_and_optional(self):
        schema = {
            "properties": {
                "name": {"type": "string"},
                "score": {"type": "integer"},
            },
            "required": ["name"],
        }
        result = _describe_schema_fields(schema)
        assert "Required fields:" in result
        assert "name (string)" in result
        assert "Optional fields:" in result
        assert "score (integer)" in result

    def test_includes_enum_values(self):
        schema = {
            "properties": {
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
            },
        }
        result = _describe_schema_fields(schema)
        assert "one of:" in result

    def test_includes_min_max(self):
        schema = {
            "properties": {
                "score": {"type": "integer", "minimum": 0, "maximum": 100},
            },
        }
        result = _describe_schema_fields(schema)
        assert "min: 0" in result
        assert "max: 100" in result

    def test_includes_format(self):
        schema = {
            "properties": {
                "email": {"type": "string", "format": "email"},
            },
        }
        result = _describe_schema_fields(schema)
        assert "format: email" in result

    def test_includes_description(self):
        schema = {
            "properties": {
                "notes": {"type": "string", "description": "Free-form text notes"},
            },
        }
        result = _describe_schema_fields(schema)
        assert "Free-form text notes" in result

    def test_all_metadata_combined(self):
        """A field with multiple attributes should include all of them."""
        schema = {
            "properties": {
                "score": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Lead qualification score",
                },
            },
            "required": ["score"],
        }
        result = _describe_schema_fields(schema)
        assert "score (integer)" in result
        assert "min: 0" in result
        assert "max: 100" in result
        assert "Lead qualification score" in result
        assert "Required fields:" in result


class TestBuildInstructions:
    """Test _build_instructions — builds server instruction string."""

    def test_includes_app_name_and_entity_count(self):
        upjack = {
            "display": {"name": "My CRM"},
            "entities": [
                {"name": "contact", "prefix": "ct"},
                {"name": "deal", "prefix": "dl"},
            ],
        }
        result = _build_instructions(upjack)
        assert "My CRM" in result
        assert "2 entity types" in result
        assert "contact (ct_)" in result
        assert "deal (dl_)" in result

    def test_with_context_adds_resource_hint(self):
        upjack = {
            "display": {"name": "App"},
            "entities": [],
            "context": "context.md",
        }
        result = _build_instructions(upjack)
        assert "upjack://context" in result

    def test_without_context_no_resource_hint(self):
        upjack = {
            "display": {"name": "App"},
            "entities": [],
        }
        result = _build_instructions(upjack)
        assert "upjack://context" not in result

    def test_default_app_name_when_display_missing(self):
        upjack = {"entities": [{"name": "thing", "prefix": "th"}]}
        result = _build_instructions(upjack)
        assert "App" in result


# ===========================================================================
# Integration tests for create_server
# ===========================================================================


class TestCreateServer:
    """Test create_server — the main server factory."""

    def test_returns_fastmcp_instance(self, tmp_path):
        from fastmcp import FastMCP

        manifest_path = _make_manifest(
            tmp_path,
            [
                {"name": "item", "plural": "items", "prefix": "it"},
            ],
        )
        mcp = create_server(manifest_path, root=tmp_path / "workspace")
        assert isinstance(mcp, FastMCP)

    def test_server_name_from_display(self, tmp_path):
        manifest_path = _make_manifest(
            tmp_path,
            [{"name": "item", "plural": "items", "prefix": "it"}],
            display_name="My Custom App",
        )
        mcp = create_server(manifest_path, root=tmp_path / "workspace")
        assert mcp.name == "My Custom App"

    def test_registers_six_tools_per_entity(self, tmp_path):
        manifest_path = _make_manifest(
            tmp_path,
            [
                {"name": "widget", "plural": "widgets", "prefix": "wg"},
            ],
        )
        mcp = create_server(manifest_path, root=tmp_path / "workspace")
        tools = _run(_list_tool_names(mcp))

        assert tools == {
            "create_widget",
            "get_widget",
            "update_widget",
            "list_widgets",
            "search_widgets",
            "delete_widget",
        }

    def test_multiple_entity_types(self, tmp_path):
        manifest_path = _make_manifest(
            tmp_path,
            [
                {"name": "contact", "plural": "contacts", "prefix": "ct"},
                {"name": "deal", "plural": "deals", "prefix": "dl"},
            ],
        )
        mcp = create_server(manifest_path, root=tmp_path / "workspace")
        tools = _run(_list_tool_names(mcp))

        # 6 tools per entity × 2 entities = 12
        assert len(tools) == 12
        assert "create_contact" in tools
        assert "search_deals" in tools

    def test_uses_title_when_display_name_missing(self, tmp_path):
        """Falls back to manifest title when display.name is absent."""
        schemas_dir = tmp_path / "schemas"
        schemas_dir.mkdir()
        schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}
        (schemas_dir / "item.schema.json").write_text(json.dumps(schema))

        manifest = {
            "manifest_version": "0.4",
            "name": "test",
            "version": "1.0.0",
            "title": "Fallback Title",
            "server": None,
            "_meta": {
                "ai.nimblebrain/upjack": {
                    "upjack_version": "0.1",
                    "namespace": "test",
                    "entities": [
                        {
                            "name": "item",
                            "plural": "items",
                            "prefix": "it",
                            "schema": "schemas/item.schema.json",
                        },
                    ],
                }
            },
        }
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        mcp = create_server(manifest_path, root=tmp_path / "workspace")
        assert mcp.name == "Fallback Title"


class TestServerToolsWork:
    """Verify that generated tools actually perform CRUD correctly."""

    @pytest.fixture
    def mcp(self, tmp_path):
        manifest_path = _make_manifest(
            tmp_path,
            [
                {"name": "item", "plural": "items", "prefix": "it"},
            ],
        )
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        return create_server(manifest_path, root=workspace)

    def test_create_and_get_roundtrip(self, mcp):
        created = _run(_call_tool(mcp, "create_item", {"data": {"name": "Widget"}}))
        assert created["id"].startswith("it_")
        assert created["name"] == "Widget"
        assert created["type"] == "item"

        fetched = _run(_call_tool(mcp, "get_item", {"entity_id": created["id"]}))
        assert fetched["id"] == created["id"]
        assert fetched["name"] == "Widget"

    def test_update_merges_fields(self, mcp):
        created = _run(_call_tool(mcp, "create_item", {"data": {"name": "Old"}}))
        updated = _run(
            _call_tool(
                mcp,
                "update_item",
                {
                    "entity_id": created["id"],
                    "data": {"name": "New", "extra": "field"},
                },
            )
        )
        assert updated["name"] == "New"
        assert updated["extra"] == "field"

    def test_list_returns_created_entities(self, mcp):
        _run(_call_tool(mcp, "create_item", {"data": {"name": "A"}}))
        _run(_call_tool(mcp, "create_item", {"data": {"name": "B"}}))

        items = _run(_call_tool(mcp, "list_items", {}))
        assert len(items) == 2

    def test_search_finds_by_text(self, mcp):
        _run(_call_tool(mcp, "create_item", {"data": {"name": "Alpha"}}))
        _run(_call_tool(mcp, "create_item", {"data": {"name": "Beta"}}))

        results = _run(_call_tool(mcp, "search_items", {"query": "Alpha"}))
        assert len(results) == 1
        assert results[0]["name"] == "Alpha"

    def test_delete_soft(self, mcp):
        created = _run(_call_tool(mcp, "create_item", {"data": {"name": "Doomed"}}))
        result = _run(_call_tool(mcp, "delete_item", {"entity_id": created["id"]}))
        assert result["status"] == "deleted"

        # Should not appear in list (default active filter)
        items = _run(_call_tool(mcp, "list_items", {}))
        assert items is None or len(items) == 0

    def test_delete_hard(self, mcp):
        created = _run(_call_tool(mcp, "create_item", {"data": {"name": "Gone"}}))
        _run(_call_tool(mcp, "delete_item", {"entity_id": created["id"], "hard": True}))

        # Hard-deleted entities are gone from disk entirely
        result = _run(_call_tool(mcp, "list_items", {}))
        assert result is None or all(r["id"] != created["id"] for r in result)


# ===========================================================================
# Seed tool tests
# ===========================================================================


class TestSeedTool:
    """Test the seed_data tool that loads sample data."""

    def test_seed_tool_registered_when_config_present(self, tmp_path):
        seed_dir = tmp_path / "seed"
        seed_dir.mkdir()

        manifest_path = _make_manifest(
            tmp_path,
            [{"name": "item", "plural": "items", "prefix": "it"}],
            seed={"data": "seed/", "run_on_install": True},
        )
        mcp = create_server(manifest_path, root=tmp_path / "workspace")
        tools = _run(_list_tool_names(mcp))
        assert "seed_data" in tools

    def test_no_seed_tool_when_config_absent(self, tmp_path):
        manifest_path = _make_manifest(
            tmp_path,
            [
                {"name": "item", "plural": "items", "prefix": "it"},
            ],
        )
        mcp = create_server(manifest_path, root=tmp_path / "workspace")
        tools = _run(_list_tool_names(mcp))
        assert "seed_data" not in tools

    def test_seed_loads_single_entity(self, tmp_path):
        seed_dir = tmp_path / "seed"
        seed_dir.mkdir()
        (seed_dir / "widget.json").write_text(
            json.dumps({"type": "item", "name": "Seeded Widget", "status": "active"})
        )

        manifest_path = _make_manifest(
            tmp_path,
            [{"name": "item", "plural": "items", "prefix": "it"}],
            seed={"data": "seed/"},
        )
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mcp = create_server(manifest_path, root=workspace)

        result = _run(_call_tool(mcp, "seed_data"))
        assert len(result["loaded"]) == 1
        assert result["errors"] == []

    def test_seed_loads_array_of_entities(self, tmp_path):
        seed_dir = tmp_path / "seed"
        seed_dir.mkdir()
        (seed_dir / "items.json").write_text(
            json.dumps(
                [
                    {"type": "item", "name": "One"},
                    {"type": "item", "name": "Two"},
                    {"type": "item", "name": "Three"},
                ]
            )
        )

        manifest_path = _make_manifest(
            tmp_path,
            [{"name": "item", "plural": "items", "prefix": "it"}],
            seed={"data": "seed/"},
        )
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mcp = create_server(manifest_path, root=workspace)

        result = _run(_call_tool(mcp, "seed_data"))
        assert len(result["loaded"]) == 3
        assert result["errors"] == []

    def test_seed_reports_missing_type(self, tmp_path):
        seed_dir = tmp_path / "seed"
        seed_dir.mkdir()
        (seed_dir / "bad.json").write_text(json.dumps({"name": "No Type Field"}))

        manifest_path = _make_manifest(
            tmp_path,
            [{"name": "item", "plural": "items", "prefix": "it"}],
            seed={"data": "seed/"},
        )
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mcp = create_server(manifest_path, root=workspace)

        result = _run(_call_tool(mcp, "seed_data"))
        assert result["loaded"] == []
        assert len(result["errors"]) == 1
        assert "missing 'type'" in result["errors"][0]

    def test_seed_missing_directory(self, tmp_path):
        # Don't create the seed directory — it should return an error
        manifest_path = _make_manifest(
            tmp_path,
            [{"name": "item", "plural": "items", "prefix": "it"}],
            seed={"data": "nonexistent_seed/"},
        )
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mcp = create_server(manifest_path, root=workspace)

        result = _run(_call_tool(mcp, "seed_data"))
        assert "error" in result


# ===========================================================================
# Resource tests
# ===========================================================================


class TestResources:
    """Test context and skill resource registration."""

    def test_context_resource_registered(self, tmp_path):
        context_file = tmp_path / "context.md"
        context_file.write_text("# CRM Domain Knowledge\nThis is the context.")

        manifest_path = _make_manifest(
            tmp_path,
            [{"name": "item", "plural": "items", "prefix": "it"}],
            context="context.md",
        )
        mcp = create_server(manifest_path, root=tmp_path / "workspace")
        uris = _run(_list_resource_uris(mcp))
        assert "upjack://context" in uris

    def test_context_resource_returns_file_content(self, tmp_path):
        expected_content = "# Sales Playbook\nAlways follow up within 24 hours."
        (tmp_path / "context.md").write_text(expected_content)

        manifest_path = _make_manifest(
            tmp_path,
            [{"name": "item", "plural": "items", "prefix": "it"}],
            context="context.md",
        )
        mcp = create_server(manifest_path, root=tmp_path / "workspace")
        content = _run(_read_resource(mcp, "upjack://context"))
        assert expected_content in content

    def test_no_context_resource_when_file_missing(self, tmp_path):
        manifest_path = _make_manifest(
            tmp_path,
            [{"name": "item", "plural": "items", "prefix": "it"}],
            context="nonexistent.md",
        )
        mcp = create_server(manifest_path, root=tmp_path / "workspace")
        uris = _run(_list_resource_uris(mcp))
        assert "upjack://context" not in uris

    def test_skill_resources_registered(self, tmp_path):
        skill_dir = tmp_path / "skills" / "lead-qual"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Lead Qualification\nScore leads 0-100.")

        manifest_path = _make_manifest(
            tmp_path,
            [{"name": "item", "plural": "items", "prefix": "it"}],
            skills=[{"source": "bundled", "path": "skills/lead-qual/SKILL.md"}],
        )
        mcp = create_server(manifest_path, root=tmp_path / "workspace")
        uris = _run(_list_resource_uris(mcp))
        assert "upjack://skills/lead-qual" in uris

    def test_skill_resource_returns_content(self, tmp_path):
        skill_dir = tmp_path / "skills" / "scoring"
        skill_dir.mkdir(parents=True)
        expected = "# Scoring Rubric\nRate each lead on 5 dimensions."
        (skill_dir / "SKILL.md").write_text(expected)

        manifest_path = _make_manifest(
            tmp_path,
            [{"name": "item", "plural": "items", "prefix": "it"}],
            skills=[{"source": "bundled", "path": "skills/scoring/SKILL.md"}],
        )
        mcp = create_server(manifest_path, root=tmp_path / "workspace")
        content = _run(_read_resource(mcp, "upjack://skills/scoring"))
        assert expected in content

    def test_non_bundled_skills_not_registered(self, tmp_path):
        """Skills with source != 'bundled' should not get resources."""
        manifest_path = _make_manifest(
            tmp_path,
            [{"name": "item", "plural": "items", "prefix": "it"}],
            skills=[{"source": "mpak", "name": "@external/skill", "version": "^1.0"}],
        )
        mcp = create_server(manifest_path, root=tmp_path / "workspace")
        uris = _run(_list_resource_uris(mcp))
        # Only entity tools, no skill resources
        assert not any("skills" in uri for uri in uris)

    def test_missing_skill_file_not_registered(self, tmp_path):
        manifest_path = _make_manifest(
            tmp_path,
            [{"name": "item", "plural": "items", "prefix": "it"}],
            skills=[{"source": "bundled", "path": "skills/nonexistent/SKILL.md"}],
        )
        mcp = create_server(manifest_path, root=tmp_path / "workspace")
        uris = _run(_list_resource_uris(mcp))
        assert not any("skills" in uri for uri in uris)


# ===========================================================================
# CLI entrypoint tests
# ===========================================================================


class TestMain:
    """Test the main() CLI entrypoint."""

    def test_creates_workspace_directory(self, tmp_path):
        manifest_path = _make_manifest(
            tmp_path,
            [
                {"name": "item", "plural": "items", "prefix": "it"},
            ],
        )
        workspace = tmp_path / "auto_workspace"

        with mock.patch(
            "sys.argv",
            [
                "upjack-server",
                str(manifest_path),
                "--root",
                str(workspace),
            ],
        ):
            # Mock mcp.run() to prevent blocking
            with mock.patch("upjack.server.FastMCP.run"):
                main()

        assert workspace.exists()

    def test_default_root(self, tmp_path, monkeypatch):
        manifest_path = _make_manifest(
            tmp_path,
            [
                {"name": "item", "plural": "items", "prefix": "it"},
            ],
        )
        # Change cwd so ./workspace resolves to tmp_path/workspace
        monkeypatch.chdir(tmp_path)

        with mock.patch("sys.argv", ["upjack-server", str(manifest_path)]):
            with mock.patch("upjack.server.FastMCP.run"):
                main()

        assert (tmp_path / "workspace").exists()
