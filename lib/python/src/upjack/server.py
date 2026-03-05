"""FastMCP server that reads an Upjack manifest and auto-generates domain-specific tools."""

import argparse
import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

try:
    from fastmcp import FastMCP
    from fastmcp.tools.tool import Tool, ToolResult
except ImportError as e:
    raise ImportError(
        "FastMCP is required for server functionality. Install with: pip install upjack[mcp]"
    ) from e

from mcp.types import TextContent

from upjack.app import UpjackApp

# Base entity fields auto-managed by the framework — stripped from tool input schemas
_BASE_ENTITY_KEYS = frozenset(
    {
        "id",
        "type",
        "version",
        "created_at",
        "updated_at",
        "created_by",
        "status",
        "tags",
        "source",
        "relationships",
    }
)


def _prepare_entity_schema(schema: dict[str, Any], *, for_update: bool = False) -> dict[str, Any]:
    """Prepare an entity JSON Schema for use as an MCP tool input.

    Strips base entity fields (auto-managed by the framework) and JSON Schema
    meta keywords that don't belong in a tool input schema.  For update tools,
    removes ``required`` since updates are partial merges.
    """
    result = copy.deepcopy(schema)

    # Strip JSON Schema meta keywords not applicable inside tool input
    result.pop("$schema", None)
    result.pop("$id", None)

    if "properties" in result:
        result["properties"] = {
            k: v for k, v in result["properties"].items() if k not in _BASE_ENTITY_KEYS
        }

    if for_update:
        # Updates are partial merges — all fields optional
        result.pop("required", None)
    elif "required" in result:
        result["required"] = [r for r in result["required"] if r not in _BASE_ENTITY_KEYS]
        if not result["required"]:
            del result["required"]

    return result


def _make_entity_tool(
    *,
    name: str,
    description: str,
    parameters: dict[str, Any],
    handler: Callable[[dict[str, Any]], dict[str, Any]],
) -> Tool:
    """Create a Tool instance with raw JSON Schema parameters and a handler closure.

    Uses a dynamically-created subclass so the handler is captured in the closure
    scope — no Pydantic private-attribute hacks required.
    """

    async def run(self: Tool, arguments: dict[str, Any]) -> ToolResult:
        # Raw Tool subclasses bypass FastMCP's Pydantic deserialization —
        # object arguments may arrive as JSON strings over stdio transport
        parsed: dict[str, Any] = {}
        for k, v in arguments.items():
            if isinstance(v, str) and v.startswith(("{", "[")):
                try:
                    parsed[k] = json.loads(v)
                except (json.JSONDecodeError, ValueError):
                    parsed[k] = v
            else:
                parsed[k] = v
        result = handler(parsed)
        return ToolResult(content=[TextContent(type="text", text=json.dumps(result, default=str))])

    tool_cls = type(f"_{name}_tool", (Tool,), {"run": run})
    return tool_cls(name=name, description=description, parameters=parameters)


def _register_entity_tools(
    mcp: FastMCP,
    app: UpjackApp,
    entity_def: dict[str, Any],
    schema: dict[str, Any] | None,
) -> None:
    """Register 6 CRUD+search tools for a single entity type."""
    name = entity_def["name"]
    plural = entity_def.get("plural", name + "s")
    prefix = entity_def["prefix"]

    id_hint = f"IDs start with {prefix}_"

    # --- create_{name} ---
    # Use the entity's JSON Schema so LLMs see full field structure
    if schema:
        data_schema = _prepare_entity_schema(schema)
    else:
        data_schema = {"type": "object"}

    mcp.add_tool(
        _make_entity_tool(
            name=f"create_{name}",
            description=f"Create a new {name}. {id_hint}.",
            parameters={
                "type": "object",
                "properties": {"data": data_schema},
                "required": ["data"],
            },
            handler=lambda args, _n=name: app.create_entity(_n, args["data"]),
        )
    )

    # --- get_{name} ---
    get_desc = f"Get a {name} by ID. {id_hint}."

    @mcp.tool(name=f"get_{name}", description=get_desc)
    def get_tool(entity_id: str, _name: str = name) -> dict[str, Any]:
        return app.get_entity(_name, entity_id)

    # --- update_{name} ---
    # Use the entity's JSON Schema with required stripped (partial merge)
    if schema:
        update_data_schema = _prepare_entity_schema(schema, for_update=True)
    else:
        update_data_schema = {"type": "object"}

    mcp.add_tool(
        _make_entity_tool(
            name=f"update_{name}",
            description=f"Update a {name} by ID. Merges fields by default. {id_hint}.",
            parameters={
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": f"{name} ID ({prefix}_...)",
                    },
                    "data": update_data_schema,
                },
                "required": ["entity_id", "data"],
            },
            handler=lambda args, _n=name: app.update_entity(_n, args["entity_id"], args["data"]),
        )
    )

    # --- list_{plural} ---
    list_desc = (
        f"List {plural}. Filters by status (default: active). Returns newest first. {id_hint}."
    )

    @mcp.tool(name=f"list_{plural}", description=list_desc)
    def list_tool(
        status: str = "active", limit: int = 50, _name: str = name
    ) -> list[dict[str, Any]]:
        return app.list_entities(_name, status=status, limit=limit)

    # --- search_{plural} ---
    search_desc = (
        f"Search {plural} with text query and/or structured filters. "
        f"Text query matches across all string fields (case-insensitive). "
        f"Filters support: direct equality, $gt, $gte, $lt, $lte, $ne, $in, "
        f"$contains, $exists. Sort with '-field' for descending. {id_hint}."
    )

    @mcp.tool(name=f"search_{plural}", description=search_desc)
    def search_tool(
        query: str | None = None,
        filter: dict[str, Any] | None = None,
        sort: str = "-updated_at",
        limit: int = 20,
        _name: str = name,
    ) -> list[dict[str, Any]]:
        return app.search_entities(_name, query=query, filter=filter, sort=sort, limit=limit)

    # --- delete_{name} ---
    delete_desc = (
        f"Delete a {name} by ID. Soft delete by default (sets status to 'deleted'). "
        f"Set hard=true to permanently remove. {id_hint}."
    )

    @mcp.tool(name=f"delete_{name}", description=delete_desc)
    def delete_tool(entity_id: str, hard: bool = False, _name: str = name) -> dict[str, Any]:
        return app.delete_entity(_name, entity_id, hard=hard)


def _register_seed_tool(
    mcp: FastMCP,
    app: UpjackApp,
    manifest_dir: Path,
    upjack: dict[str, Any],
) -> None:
    """Register the seed_data tool if seed config exists."""
    seed_config = upjack.get("seed")
    if not seed_config:
        return

    seed_dir = manifest_dir / seed_config.get("data", "seed/")

    @mcp.tool(
        name="seed_data",
        description="Load sample data from the app's seed directory into the workspace.",
    )
    def seed_data() -> dict[str, Any]:
        if not seed_dir.exists():
            return {"error": f"Seed directory not found: {seed_dir}"}

        loaded: list[str] = []
        errors: list[str] = []

        for file in sorted(seed_dir.glob("*.json")):
            raw = json.loads(file.read_text())

            # Normalize to list (single entity or array)
            items = raw if isinstance(raw, list) else [raw]

            for item in items:
                entity_type = item.get("type")
                if not entity_type:
                    errors.append(f"{file.name}: missing 'type' field")
                    continue

                # Extract app data (strip base fields that create_entity generates)
                data = {
                    k: v
                    for k, v in item.items()
                    if k not in {"id", "type", "created_at", "updated_at", "created_by"}
                }

                try:
                    result = app.create_entity(entity_type, data, created_by="system")
                    loaded.append(f"{entity_type}: {result['id']}")
                except (ValueError, KeyError) as e:
                    errors.append(f"{file.name} ({entity_type}): {e}")

        return {"loaded": loaded, "errors": errors}


def _register_resources(
    mcp: FastMCP,
    manifest_dir: Path,
    upjack: dict[str, Any],
) -> None:
    """Register context and skill resources."""
    # Context resource
    context_file = upjack.get("context")
    if context_file:
        context_path = manifest_dir / context_file
        if context_path.exists():

            @mcp.resource("upjack://context", name="Context", description="App domain knowledge")
            def get_context() -> str:
                return context_path.read_text()

    # Skill resources
    skills = upjack.get("skills", [])
    for skill in skills:
        if skill.get("source") != "bundled":
            continue
        skill_path = manifest_dir / skill["path"]
        if not skill_path.exists():
            continue

        # Extract skill name from path (e.g., "skills/lead-qualification/SKILL.md" → "lead-qualification")
        skill_name = skill_path.parent.name
        _register_skill_resource(mcp, skill_name, skill_path)


def _register_skill_resource(mcp: FastMCP, skill_name: str, skill_path: Path) -> None:
    """Register a single skill resource (separate function for clean closure)."""

    @mcp.resource(
        f"upjack://skills/{skill_name}",
        name=skill_name,
        description=f"Skill: {skill_name}",
    )
    def get_skill() -> str:
        return skill_path.read_text()


def _build_instructions(upjack: dict[str, Any]) -> str:
    """Build server instructions from manifest metadata."""
    display = upjack.get("display", {})
    app_name = display.get("name", "App")

    entities = upjack.get("entities", [])
    entity_summaries = []
    for e in entities:
        name = e["name"]
        prefix = e["prefix"]
        entity_summaries.append(f"{name} ({prefix}_)")

    instructions = f"{app_name} with {len(entities)} entity types: {', '.join(entity_summaries)}."

    if upjack.get("context"):
        instructions += "\nRead the upjack://context resource for domain knowledge."

    return instructions


def create_server(manifest_path: str | Path, root: str | Path = ".") -> FastMCP:
    """Create a FastMCP server from an Upjack manifest.

    Args:
        manifest_path: Path to manifest.json.
        root: Workspace root directory.

    Returns:
        Configured FastMCP server instance.
    """
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    manifest_dir = manifest_path.parent

    upjack = manifest.get("_meta", {}).get("ai.nimblebrain/upjack", {})
    display = upjack.get("display", {})
    app_name = display.get("name", manifest.get("title", "Upjack App"))

    app = UpjackApp.from_manifest(manifest_path, root=root)

    mcp = FastMCP(
        name=app_name,
        instructions=_build_instructions(upjack),
    )

    # Register tools for each entity type
    for entity_def in upjack.get("entities", []):
        schema = app._schemas.get(entity_def["name"])
        _register_entity_tools(mcp, app, entity_def, schema)

    # Register seed tool
    _register_seed_tool(mcp, app, manifest_dir, upjack)

    # Register resources
    _register_resources(mcp, manifest_dir, upjack)

    return mcp


def main() -> None:
    """CLI entrypoint for running the Upjack MCP server."""
    parser = argparse.ArgumentParser(description="Run an Upjack MCP server from a manifest")
    parser.add_argument(
        "manifest",
        help="Path to the Upjack manifest.json",
    )
    parser.add_argument(
        "--root",
        default="./workspace",
        help="Workspace root directory (default: ./workspace)",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    root = Path(args.root).resolve()

    # Ensure workspace exists
    root.mkdir(parents=True, exist_ok=True)

    mcp = create_server(manifest_path, root)
    mcp.run()


if __name__ == "__main__":
    main()
