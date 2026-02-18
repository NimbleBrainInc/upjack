---
title: Python Library
description: "The upjack Python package: schema-driven entity management and MCP server generation."
draft: false
---

Schema-driven entity management for AI-native applications.

Define entities as JSON Schemas + a manifest. The library handles CRUD, validation, ID generation, storage, and search. Add FastMCP to serve it as an MCP server.

## Install

```bash
# Core library (entity management only)
uv add upjack

# With MCP server support
uv add upjack[mcp]
```

## Usage: Entity Management

```python
from upjack import UpjackApp

app = UpjackApp.from_manifest("manifest.json")

# Create an entity
contact = app.create_entity("contact", {
    "first_name": "Sarah",
    "last_name": "Chen",
    "email": "sarah@example.com",
})

# List entities
contacts = app.list_entities("contact")

# Update an entity
app.update_entity("contact", contact["id"], {"lead_score": 85})

# Get a single entity
contact = app.get_entity("contact", contact["id"])

# Delete an entity (soft delete by default)
app.delete_entity("contact", contact["id"])
```

## Usage: MCP Server

```python
from upjack.server import create_server

mcp = create_server("manifest.json", root="./workspace")
mcp.run()
```

This generates CRUD tools for every entity type in the manifest, exposes context and skills as MCP resources, and handles validation automatically. See the [CRM example](https://github.com/NimbleBrainInc/upjack/tree/main/examples/crm/server.py) for a complete example.

## Requirements

- Python >= 3.13
- FastMCP >= 3.0 (only for `upjack[mcp]`)

## API Differences from TypeScript

| Aspect | Python | TypeScript |
|--------|--------|------------|
| Method naming | `snake_case` (`create_entity`) | `camelCase` (`createEntity`) |
| Server framework | FastMCP | @modelcontextprotocol/sdk |
| MCP extra | `upjack[mcp]` (optional) | `@modelcontextprotocol/sdk` (peer dep) |
| Schema validation | `jsonschema` (Draft202012Validator) | AJV (2020-12) |
| ID generation | `python-ulid` | `ulidx` |
| Error types | `ValueError`, `FileNotFoundError`, `ValidationError` | Generic `Error` with descriptive messages |

Looking for TypeScript? See the [TypeScript Library](/libraries/typescript/) page.
