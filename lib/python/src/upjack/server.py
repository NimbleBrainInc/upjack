"""FastMCP server that reads an Upjack manifest and auto-generates domain-specific tools."""

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from fastmcp import FastMCP
except ImportError as e:
    raise ImportError(
        "FastMCP is required for server functionality. Install with: pip install upjack[mcp]"
    ) from e

from upjack.app import UpjackApp


def _describe_schema_fields(schema: dict[str, Any] | None) -> str:
    """Generate a human-readable field description from JSON Schema properties."""
    if schema is None:
        return ""

    props = schema.get("properties", {})
    required = set(schema.get("required", []))

    # Skip base entity fields — those are auto-managed
    base_keys = {
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

    app_props = {k: v for k, v in props.items() if k not in base_keys}
    if not app_props:
        return ""

    req_fields = []
    opt_fields = []

    for name, prop in app_props.items():
        ptype = prop.get("type", "any")
        parts = [f"{name} ({ptype})"]

        if "enum" in prop:
            parts.append(f"one of: {prop['enum']}")
        if "minimum" in prop:
            parts.append(f"min: {prop['minimum']}")
        if "maximum" in prop:
            parts.append(f"max: {prop['maximum']}")
        if "format" in prop:
            parts.append(f"format: {prop['format']}")
        if "description" in prop:
            parts.append(prop["description"])

        desc = " — ".join(parts)
        if name in required:
            req_fields.append(desc)
        else:
            opt_fields.append(desc)

    lines = []
    if req_fields:
        lines.append("Required fields: " + "; ".join(req_fields))
    if opt_fields:
        lines.append("Optional fields: " + "; ".join(opt_fields))
    return ". ".join(lines)


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

    field_desc = _describe_schema_fields(schema)
    id_hint = f"IDs start with {prefix}_"

    # --- create_{name} ---
    create_desc = f"Create a new {name}. {id_hint}."
    if field_desc:
        create_desc += f" {field_desc}."

    @mcp.tool(name=f"create_{name}", description=create_desc)
    def create_tool(data: dict[str, Any], _name: str = name) -> dict[str, Any]:
        return app.create_entity(_name, data)

    # --- get_{name} ---
    get_desc = f"Get a {name} by ID. {id_hint}."

    @mcp.tool(name=f"get_{name}", description=get_desc)
    def get_tool(entity_id: str, _name: str = name) -> dict[str, Any]:
        return app.get_entity(_name, entity_id)

    # --- update_{name} ---
    update_desc = f"Update a {name} by ID. Merges fields by default. {id_hint}."
    if field_desc:
        update_desc += f" {field_desc}."

    @mcp.tool(name=f"update_{name}", description=update_desc)
    def update_tool(entity_id: str, data: dict[str, Any], _name: str = name) -> dict[str, Any]:
        return app.update_entity(_name, entity_id, data)

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
