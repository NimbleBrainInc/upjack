"""CLI tools for scaffolding and running Upjack apps."""

import argparse
import json
import sys
from pathlib import Path

_MANIFEST_TEMPLATE = {
    "manifest_version": "0.4",
    "name": "",
    "version": "0.1.0",
    "title": "",
    "description": "",
    "server": {
        "type": "python",
        "entry_point": "server",
        "mcp_config": {"command": "python", "args": ["server.py"]},
    },
    "_meta": {
        "ai.nimblebrain/upjack": {
            "upjack_version": "0.1",
            "namespace": "",
            "entities": [],
            "context": "context.md",
            "seed": {"data": "seed/", "run_on_install": True},
        }
    },
}

_SCHEMA_TEMPLATE = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "",
    "description": "",
    "allOf": [{"$ref": "https://upjack.dev/schemas/v1/upjack-entity.schema.json"}],
    "properties": {
        "name": {"type": "string", "maxLength": 256, "description": "Display name"},
    },
    "required": ["name"],
}

_SERVER_TEMPLATE = '''"""MCP server built with upjack + FastMCP."""

from pathlib import Path

from upjack.server import create_server

manifest = Path(__file__).parent / "manifest.json"
mcp = create_server(manifest)

if __name__ == "__main__":
    mcp.run()
'''

_CONTEXT_TEMPLATE = """# {title} Domain Knowledge

You are managing a {title} application. Help the user work effectively with {entity_plural}.

## Entity Types

- **{entity_title}**: The primary entity type. Prefix: `{prefix}_`

## Rules

- Validate data before creating or updating entities
- Keep records up to date
"""


def _slugify(name: str) -> str:
    """Convert a name to a lowercase slug."""
    return name.lower().replace(" ", "-").strip("-")


def _make_prefix(name: str) -> str:
    """Generate a 2-4 char prefix from an entity name."""
    name = name.lower().strip()
    if len(name) <= 4:
        return name[:4]
    # Use consonants after the first letter
    consonants = [c for c in name[1:] if c not in "aeiou "]
    prefix = name[0] + "".join(consonants)
    return prefix[:3] if len(prefix) >= 3 else name[:3]


def _prompt(message: str, default: str = "") -> str:
    """Prompt the user for input with an optional default."""
    if default:
        result = input(f"{message} [{default}]: ").strip()
        return result or default
    return input(f"{message}: ").strip()


def init(args: argparse.Namespace) -> None:
    """Scaffold a new Upjack app directory."""
    target = Path(args.directory) if args.directory else None

    # Gather info interactively unless --name is provided
    if args.name:
        app_name = args.name
    else:
        app_name = _prompt("App name", "my-app")

    slug = _slugify(app_name)

    if target is None:
        target = Path.cwd() / slug

    if args.entity:
        entity_name = args.entity.lower()
    else:
        entity_name = _prompt("First entity type (e.g., task, contact, note)", "item")
        entity_name = entity_name.lower().strip()

    entity_plural = entity_name + "s"
    prefix = _make_prefix(entity_name)

    # Check target directory
    if target.exists() and any(target.iterdir()):
        print(f"Error: {target} already exists and is not empty.", file=sys.stderr)
        sys.exit(1)

    # Create directory structure
    target.mkdir(parents=True, exist_ok=True)
    (target / "schemas").mkdir()
    (target / "seed").mkdir()
    (target / "skills").mkdir()

    # Write manifest
    manifest = json.loads(json.dumps(_MANIFEST_TEMPLATE))
    manifest["name"] = slug
    manifest["title"] = app_name.replace("-", " ").title()
    manifest["description"] = f"A {app_name} app built with NimbleBrain Upjack"
    upjack = manifest["_meta"]["ai.nimblebrain/upjack"]
    upjack["namespace"] = f"apps/{slug}"
    upjack["entities"] = [
        {
            "name": entity_name,
            "plural": entity_plural,
            "schema": f"schemas/{entity_name}.schema.json",
            "prefix": prefix,
            "index": True,
        }
    ]

    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    # Write entity schema
    schema = json.loads(json.dumps(_SCHEMA_TEMPLATE))
    schema["title"] = entity_name.title()
    schema["description"] = f"A {entity_name} entity"
    (target / "schemas" / f"{entity_name}.schema.json").write_text(
        json.dumps(schema, indent=2) + "\n"
    )

    # Write server.py
    (target / "server.py").write_text(_SERVER_TEMPLATE)

    # Write context.md
    context = _CONTEXT_TEMPLATE.format(
        title=app_name.replace("-", " ").title(),
        entity_plural=entity_plural,
        entity_title=entity_name.title(),
        prefix=prefix,
    )
    (target / "context.md").write_text(context)

    # Write empty seed file
    seed_data = [
        {
            "type": entity_name,
            "name": f"Sample {entity_name}",
        }
    ]
    (target / "seed" / f"sample-{entity_plural}.json").write_text(
        json.dumps(seed_data, indent=2) + "\n"
    )

    print(f"Created Upjack app at {target}/")
    print()
    print("Next steps:")
    print(f"  cd {target.name}")
    print(f"  # Edit schemas/{entity_name}.schema.json to add your fields")
    print("  # Edit context.md with your domain knowledge")
    print("  uv run python server.py")


def serve(args: argparse.Namespace) -> None:
    """Run the MCP server from a manifest."""
    from upjack.paths import resolve_root
    from upjack.server import create_server

    manifest_path = Path(args.manifest).resolve()
    root = resolve_root(args.root)
    root.mkdir(parents=True, exist_ok=True)

    mcp = create_server(manifest_path, root)
    mcp.run()


def main() -> None:
    """Main CLI entry point for upjack."""
    parser = argparse.ArgumentParser(
        prog="upjack",
        description="NimbleBrain Upjack — schema-driven AI-native applications",
    )
    subparsers = parser.add_subparsers(dest="command")

    # upjack init
    init_parser = subparsers.add_parser("init", help="Scaffold a new Upjack app")
    init_parser.add_argument(
        "directory", nargs="?", help="Target directory (default: ./{app-name})"
    )
    init_parser.add_argument("--name", help="App name (skips interactive prompt)")
    init_parser.add_argument("--entity", help="First entity type (skips interactive prompt)")

    # upjack serve
    serve_parser = subparsers.add_parser("serve", help="Run MCP server from a manifest")
    serve_parser.add_argument("manifest", help="Path to manifest.json")
    serve_parser.add_argument(
        "--root", default=None, help="Workspace root (default: UPJACK_ROOT env or .upjack)"
    )

    args = parser.parse_args()

    if args.command == "init":
        init(args)
    elif args.command == "serve":
        serve(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
