# upjack

Schema-driven entity management for AI-native applications.

Define entities as JSON Schemas + a manifest. The library handles CRUD, validation, ID generation, storage, and search. Add FastMCP to serve it as an MCP server.

## Install

```bash
pip install upjack          # core library (entity management only)
pip install "upjack[mcp]"   # with MCP server support
```

Requires Python 3.13+.

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

This generates CRUD tools for every entity type in the manifest, exposes context and skills as MCP resources, and handles validation automatically. See `examples/crm/server.py` for a complete example.

## Requirements

- Python >= 3.13
- FastMCP >= 3.0 (only for `upjack[mcp]`)
