"""Tests for upjack.server — MCP server generation from Upjack manifests."""

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from upjack.server import (
    _build_instructions,
    _prepare_entity_schema,
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


async def _get_tool_input_schema(mcp, name: str) -> dict[str, Any]:
    from fastmcp import Client

    async with Client(mcp) as client:
        tools = await client.list_tools()
        for t in tools:
            if t.name == name:
                return t.inputSchema
        raise KeyError(f"Tool {name!r} not found")


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


class TestPrepareEntitySchema:
    """Test _prepare_entity_schema — strips base fields and prepares for tool input."""

    def test_strips_base_entity_fields(self):
        schema = {
            "type": "object",
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
                "name": {"type": "string"},
            },
            "required": ["name"],
        }
        result = _prepare_entity_schema(schema)
        assert "name" in result["properties"]
        assert "id" not in result["properties"]
        assert "type" not in result["properties"]
        assert "status" not in result["properties"]

    def test_strips_json_schema_meta_keywords(self):
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://example.com/schema",
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }
        result = _prepare_entity_schema(schema)
        assert "$schema" not in result
        assert "$id" not in result
        assert result["type"] == "object"

    def test_preserves_required_for_create(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "score": {"type": "integer"},
            },
            "required": ["name"],
        }
        result = _prepare_entity_schema(schema)
        assert result["required"] == ["name"]

    def test_strips_base_fields_from_required(self):
        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
            },
            "required": ["id", "name"],
        }
        result = _prepare_entity_schema(schema)
        assert result["required"] == ["name"]

    def test_removes_empty_required(self):
        """If all required fields are base fields, remove the required key entirely."""
        schema = {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        }
        result = _prepare_entity_schema(schema)
        assert "required" not in result

    def test_strips_required_for_update(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        result = _prepare_entity_schema(schema, for_update=True)
        assert "required" not in result

    def test_preserves_nested_structure(self):
        """Nested objects and arrays should pass through unchanged."""
        schema = {
            "type": "object",
            "properties": {
                "emotional_drivers": {
                    "type": "object",
                    "properties": {
                        "fear": {
                            "type": "object",
                            "properties": {
                                "theme": {"type": "string"},
                                "trigger_statement": {"type": "string"},
                            },
                            "required": ["theme", "trigger_statement"],
                        },
                    },
                },
                "scoring_signals": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "signal": {"type": "string"},
                            "points": {"type": "integer"},
                        },
                        "required": ["signal", "points"],
                    },
                },
            },
        }
        result = _prepare_entity_schema(schema)
        # Nested structure preserved exactly
        fear = result["properties"]["emotional_drivers"]["properties"]["fear"]
        assert fear["required"] == ["theme", "trigger_statement"]
        items = result["properties"]["scoring_signals"]["items"]
        assert items["required"] == ["signal", "points"]

    def test_does_not_mutate_original(self):
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"id": {"type": "string"}, "name": {"type": "string"}},
            "required": ["id", "name"],
        }
        _prepare_entity_schema(schema)
        # Original untouched
        assert "$schema" in schema
        assert "id" in schema["properties"]
        assert "id" in schema["required"]


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
            "add_field",
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

        # 6 tools per entity × 2 entities + 1 add_field = 13
        assert len(tools) == 13
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


class TestToolInputSchemas:
    """Verify that create/update tools expose full entity JSON Schema."""

    def test_create_tool_exposes_entity_schema(self, tmp_path):
        """create_* tools should have the entity schema nested under data."""
        entity_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "type": {"type": "string"},
                "name": {"type": "string", "description": "Campaign name"},
                "score": {"type": "integer", "minimum": 0, "maximum": 100},
                "emotional_drivers": {
                    "type": "object",
                    "properties": {
                        "fear": {"type": "object", "properties": {"theme": {"type": "string"}}},
                    },
                },
            },
            "required": ["name"],
        }

        # _make_manifest writes a default schema; overwrite it after
        manifest_path = _make_manifest(
            tmp_path,
            [
                {
                    "name": "campaign",
                    "plural": "campaigns",
                    "prefix": "cp",
                }
            ],
        )
        (tmp_path / "schemas" / "campaign.schema.json").write_text(json.dumps(entity_schema))
        mcp = create_server(manifest_path, root=tmp_path / "workspace")
        input_schema = _run(_get_tool_input_schema(mcp, "create_campaign"))

        # data property should contain the entity schema (minus base fields)
        data_schema = input_schema["properties"]["data"]
        assert "name" in data_schema["properties"]
        assert data_schema["properties"]["name"]["description"] == "Campaign name"
        assert "score" in data_schema["properties"]
        assert data_schema["properties"]["score"]["minimum"] == 0
        # Nested structure preserved
        assert "emotional_drivers" in data_schema["properties"]
        fear = data_schema["properties"]["emotional_drivers"]["properties"]["fear"]
        assert "theme" in fear["properties"]
        # Base fields stripped
        assert "id" not in data_schema["properties"]
        assert "type" not in data_schema["properties"]
        # $schema meta keyword stripped
        assert "$schema" not in data_schema
        # Required preserved (minus base fields)
        assert data_schema["required"] == ["name"]

    def test_update_tool_has_no_required_in_data(self, tmp_path):
        """update_* tools should have all data fields optional (partial merge)."""
        entity_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "score": {"type": "integer"},
            },
            "required": ["name"],
        }

        # _make_manifest writes a default schema; overwrite it after
        manifest_path = _make_manifest(
            tmp_path,
            [
                {
                    "name": "item",
                    "plural": "items",
                    "prefix": "it",
                }
            ],
        )
        (tmp_path / "schemas" / "item.schema.json").write_text(json.dumps(entity_schema))
        mcp = create_server(manifest_path, root=tmp_path / "workspace")
        input_schema = _run(_get_tool_input_schema(mcp, "update_item"))

        # Top-level requires entity_id and data
        assert "entity_id" in input_schema["properties"]
        assert set(input_schema["required"]) == {"entity_id", "data"}
        # Data schema has no required (partial update)
        data_schema = input_schema["properties"]["data"]
        assert "required" not in data_schema
        # But fields are still described
        assert "name" in data_schema["properties"]
        assert "score" in data_schema["properties"]

    def test_create_tool_falls_back_to_opaque_without_schema(self, tmp_path):
        """Without a schema, create_* should still work with opaque object."""
        schemas_dir = tmp_path / "schemas"
        schemas_dir.mkdir()
        # Minimal schema with no app properties
        (schemas_dir / "thing.schema.json").write_text(
            json.dumps(
                {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}
            )
        )

        manifest_path = _make_manifest(
            tmp_path,
            [
                {
                    "name": "thing",
                    "plural": "things",
                    "prefix": "th",
                    "schema": "schemas/thing.schema.json",
                }
            ],
        )
        mcp = create_server(manifest_path, root=tmp_path / "workspace")
        input_schema = _run(_get_tool_input_schema(mcp, "create_thing"))
        assert input_schema["properties"]["data"]["type"] == "object"


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
# JSON string deserialization (stdio transport edge case)
# ===========================================================================


class TestJsonStringDeserialization:
    """Raw Tool subclasses bypass FastMCP's Pydantic deserialization.

    Over stdio transport, object arguments may arrive as JSON strings instead
    of parsed dicts.  The server must handle both forms.
    """

    @pytest.fixture
    def mcp(self, tmp_path):
        manifest_path = _make_manifest(
            tmp_path,
            [{"name": "item", "plural": "items", "prefix": "it"}],
        )
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        return create_server(manifest_path, root=workspace)

    def test_create_with_data_as_json_string(self, mcp):
        """create_* should work when data arrives as a JSON string."""
        data_str = json.dumps({"name": "StringWidget"})
        created = _run(_call_tool(mcp, "create_item", {"data": data_str}))
        assert created["name"] == "StringWidget"
        assert created["id"].startswith("it_")

    def test_update_with_data_as_json_string(self, mcp):
        """update_* should work when data arrives as a JSON string."""
        created = _run(_call_tool(mcp, "create_item", {"data": {"name": "Original"}}))
        data_str = json.dumps({"name": "Updated"})
        updated = _run(
            _call_tool(
                mcp,
                "update_item",
                {"entity_id": created["id"], "data": data_str},
            )
        )
        assert updated["name"] == "Updated"

    def test_plain_string_args_not_mangled(self, mcp):
        """Non-JSON string arguments (like entity_id) must not be altered."""
        created = _run(_call_tool(mcp, "create_item", {"data": {"name": "Test"}}))
        fetched = _run(_call_tool(mcp, "get_item", {"entity_id": created["id"]}))
        assert fetched["id"] == created["id"]

    def test_dict_args_still_work(self, mcp):
        """Native dict arguments (normal in-process path) must keep working."""
        created = _run(_call_tool(mcp, "create_item", {"data": {"name": "DictWidget"}}))
        assert created["name"] == "DictWidget"


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


# ===========================================================================
# Add field tool tests
# ===========================================================================


class TestAddFieldTool:
    """Test the add_field tool for agent-initiated schema evolution."""

    @pytest.fixture
    def setup(self, tmp_path):
        """Create manifest with a widget entity and return (mcp, tmp_path, schema_path)."""
        schemas_dir = tmp_path / "schemas"
        schemas_dir.mkdir()
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
        }
        schema_path = schemas_dir / "widget.schema.json"
        schema_path.write_text(json.dumps(schema))

        manifest_path = _make_manifest(
            tmp_path,
            [
                {
                    "name": "widget",
                    "plural": "widgets",
                    "prefix": "wg",
                    "schema": "schemas/widget.schema.json",
                }
            ],
        )
        # Overwrite the default schema that _make_manifest created
        schema_path.write_text(json.dumps(schema))

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mcp = create_server(manifest_path, root=workspace)
        return mcp, tmp_path, schema_path

    def test_tool_is_registered(self, setup):
        mcp, _, _ = setup
        tools = _run(_list_tool_names(mcp))
        assert "add_field" in tools

    def test_adds_property_to_schema_file(self, setup):
        mcp, _, schema_path = setup
        result = _run(
            _call_tool(
                mcp,
                "add_field",
                {
                    "entity_type": "widget",
                    "field_name": "score",
                    "field_type": "integer",
                    "default": 0,
                },
            )
        )
        assert result["success"] is True

        updated = json.loads(schema_path.read_text())
        assert "score" in updated["properties"]
        assert updated["properties"]["score"]["default"] == 0

    def test_adds_to_required_when_required_true(self, setup):
        mcp, _, schema_path = setup
        _run(
            _call_tool(
                mcp,
                "add_field",
                {
                    "entity_type": "widget",
                    "field_name": "score",
                    "field_type": "integer",
                    "default": 0,
                    "required": True,
                },
            )
        )

        updated = json.loads(schema_path.read_text())
        assert "score" in updated["required"]

    def test_reload_works_new_entities_get_default(self, setup):
        mcp, _, _ = setup
        # Create entity before adding field
        created = _run(_call_tool(mcp, "create_widget", {"data": {"name": "Test"}}))

        # Add field with default
        _run(
            _call_tool(
                mcp,
                "add_field",
                {
                    "entity_type": "widget",
                    "field_name": "priority",
                    "field_type": "string",
                    "default": "medium",
                },
            )
        )

        # Read entity — should get hydrated default from new schema
        fetched = _run(_call_tool(mcp, "get_widget", {"entity_id": created["id"]}))
        assert fetched["priority"] == "medium"

    def test_rejects_invalid_field_type(self, setup):
        mcp, _, _ = setup
        result = _run(
            _call_tool(
                mcp,
                "add_field",
                {
                    "entity_type": "widget",
                    "field_name": "bad",
                    "field_type": "uuid",
                    "default": "abc",
                },
            )
        )
        assert "error" in result
        assert "Invalid field_type" in result["error"]

    def test_rejects_type_incompatible_default(self, setup):
        mcp, _, _ = setup
        result = _run(
            _call_tool(
                mcp,
                "add_field",
                {
                    "entity_type": "widget",
                    "field_name": "count",
                    "field_type": "integer",
                    "default": "not_a_number",
                },
            )
        )
        assert "error" in result
        assert "not compatible" in result["error"]

    def test_returns_error_if_field_exists_with_different_type(self, setup):
        mcp, _, _ = setup
        # name is a string in the schema
        result = _run(
            _call_tool(
                mcp,
                "add_field",
                {
                    "entity_type": "widget",
                    "field_name": "name",
                    "field_type": "integer",
                    "default": 0,
                },
            )
        )
        assert "error" in result
        assert "already exists" in result["error"]

    def test_returns_error_if_field_already_exists_same_type(self, setup):
        mcp, _, _ = setup
        result = _run(
            _call_tool(
                mcp,
                "add_field",
                {
                    "entity_type": "widget",
                    "field_name": "name",
                    "field_type": "string",
                    "default": "",
                },
            )
        )
        assert "error" in result
        assert "already exists" in result["error"]

    def test_rejects_invalid_field_name(self, setup):
        mcp, _, _ = setup
        for bad_name in ["Has Spaces", "UPPERCASE", "123start", "special-char", ""]:
            result = _run(
                _call_tool(
                    mcp,
                    "add_field",
                    {
                        "entity_type": "widget",
                        "field_name": bad_name,
                        "field_type": "string",
                        "default": "",
                    },
                )
            )
            assert "error" in result, f"Expected error for field_name={bad_name!r}"
            assert "Invalid field_name" in result["error"]

    def test_rejects_reserved_base_field_names(self, setup):
        mcp, _, _ = setup
        for reserved in ["id", "type", "version", "created_at", "updated_at", "status", "tags"]:
            result = _run(
                _call_tool(
                    mcp,
                    "add_field",
                    {
                        "entity_type": "widget",
                        "field_name": reserved,
                        "field_type": "string",
                        "default": "",
                    },
                )
            )
            assert "error" in result, f"Expected error for reserved field {reserved!r}"
            assert "reserved" in result["error"]

    def test_rejects_path_traversal_in_schema(self, tmp_path):
        """Schema path that escapes manifest_dir is rejected."""
        schemas_dir = tmp_path / "schemas"
        schemas_dir.mkdir()
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        schema_path = schemas_dir / "widget.schema.json"
        schema_path.write_text(json.dumps(schema))

        manifest_path = _make_manifest(
            tmp_path,
            [
                {
                    "name": "widget",
                    "plural": "widgets",
                    "prefix": "wg",
                    "schema": "../../etc/widget.schema.json",
                }
            ],
        )
        schema_path.write_text(json.dumps(schema))

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mcp = create_server(manifest_path, root=workspace)

        result = _run(
            _call_tool(
                mcp,
                "add_field",
                {
                    "entity_type": "widget",
                    "field_name": "score",
                    "field_type": "integer",
                    "default": 0,
                },
            )
        )
        assert "error" in result
        assert "escapes" in result["error"]
