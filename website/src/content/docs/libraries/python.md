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

mcp = create_server("manifest.json")
mcp.run()
```

This generates CRUD tools for every entity type in the manifest, exposes context and skills as MCP resources, and handles validation automatically. See the [CRM example](https://github.com/NimbleBrainInc/upjack/tree/main/examples/crm/server.py) for a complete example.

## Configuration

The workspace root (where entity data is stored) is resolved in this order:

1. `UPJACK_ROOT` environment variable
2. `--root` CLI argument (when using `upjack serve`)
3. `.upjack` in the current directory (default)

Runners like mpak or NimbleBrain set `UPJACK_ROOT` automatically to ensure data persists outside the bundle cache.

## Relationship Queries

Query the relationship graph to traverse connections between entities. These methods use a reverse index that Upjack maintains automatically at write time.

```python
from upjack import UpjackApp

app = UpjackApp.from_manifest("manifest.json")

# Find all contacts at a company (reverse lookup)
contacts = app.query_by_relationship("contact", "company", "co_01JQ3KM...")

# With filtering and limit
senior = app.query_by_relationship(
    "contact", "company", "co_01JQ3KM...",
    filter={"role": "VP"},
    limit=10,
)

# Follow edges forward: get entities a contact links to
related = app.get_related("ct_01JQ3KM...", direction="forward")
# → [{"id": "co_01JQ3KM...", "name": "Acme Corp", ...}, ...]

# Follow edges in reverse: get entities that link to a company
referrers = app.get_related("co_01JQ3KM...", direction="reverse")
# → [{"id": "ct_01JQ3KM...", "first_name": "Sarah", ...}, ...]

# Filter by relationship name
deals = app.get_related("co_01JQ3KM...", rel="company", direction="reverse")

# Load an entity with all related entities in one call
composite = app.get_composite("contact", "ct_01JQ3KM...", depth=1)
# {
#   "id": "ct_01JQ3KM...",
#   "first_name": "Sarah",
#   "company": "co_01JQ3KM...",
#   "_related": {
#     "company": [{"id": "co_01JQ3KM...", "name": "Acme Corp", ...}],
#     "~company": [{"id": "dl_01JQ3KM...", "title": "Enterprise Plan", ...}]
#   }
# }
```

In `_related`, forward relationships use the relationship name (e.g. `"company"`) and reverse relationships use a `~` prefix (e.g. `"~company"` for deals that reference this contact via their `company` field).

## Activity Tracking

Log timestamped activities against any entity. Requires `"activities": true` in the manifest's upjack extension:

```json
{
  "_meta": {
    "ai.nimblebrain/upjack": {
      "activities": true
    }
  }
}
```

Once enabled, Upjack registers a built-in `activity` entity type (prefix `act`) and exposes two methods:

```python
from upjack import UpjackApp

app = UpjackApp.from_manifest("manifest.json")

# Log an activity against a contact
app.log_activity("ct_01JQ3KM...", "email_sent", detail={
    "subject": "Follow-up on proposal",
    "channel": "email",
})

# Log a deal stage change
app.log_activity("dl_01JQ3KM...", "stage_changed", detail={
    "from": "qualification",
    "to": "proposal",
})

# Get all activities for an entity
activities = app.get_activities("ct_01JQ3KM...")

# Filter by action
emails = app.get_activities("ct_01JQ3KM...", action="email_sent")

# Limit results
recent = app.get_activities("ct_01JQ3KM...", limit=5)
```

Activities are stored as regular entities and linked to their subject via the relationship index, so they also appear in `get_composite` results.

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
