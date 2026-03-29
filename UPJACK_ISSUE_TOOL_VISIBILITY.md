# Feature: Tool visibility whitelist in manifest

## Problem

`create_server()` registers every auto-generated tool for every entity — CRUD (6), graph traversal (3), and activity tools per entity type. For an app with 6 entities, that's 67+ tools before any custom tools are added.

This overwhelms LLM clients:
- Claude Desktop took 16 seconds to process the `tools/list` response (278K chars of tool schemas)
- LLMs struggle with tool selection when presented with 77 options
- Most auto-generated tools are irrelevant for the use case (e.g., `create_session` and `delete_speaker` on a read-only conference app)

## Current workaround

Monkey-patching `_list_tools` after `create_server()`:

```python
mcp = create_server(str(MANIFEST), root=str(WORKSPACE))

_VISIBLE_TOOLS = {"find_sessions", "create_bookmark", "get_speaker", ...}

_original_list_tools = mcp._list_tools

async def _filtered_list_tools():
    all_tools = await _original_list_tools()
    return [t for t in all_tools if t.name in _VISIBLE_TOOLS]

mcp._list_tools = _filtered_list_tools
```

This works — hidden tools remain registered and callable via `tools/call`, they just don't appear in `tools/list`. But it's fragile and requires knowing FastMCP internals.

## Proposed solution

### Option A: Manifest-level visibility per entity

```json
{
  "entities": [
    {
      "name": "session",
      "prefix": "ss",
      "schema": "schemas/session.schema.json",
      "tools": {
        "visible": ["get", "search"]
      }
    },
    {
      "name": "bookmark",
      "prefix": "bk",
      "schema": "schemas/bookmark.schema.json",
      "tools": {
        "visible": ["create", "list", "delete"]
      }
    }
  ]
}
```

`tools.visible` is a whitelist of which auto-generated tool categories to include in `tools/list`. Options: `create`, `get`, `update`, `list`, `search`, `delete`, `query_by_relationship`, `get_related`, `get_composite`.

Default (no `tools` key): all tools visible (current behavior).

### Option B: `create_server()` parameter

```python
mcp = create_server(
    manifest_path,
    root="./workspace",
    visible_tools=["create_bookmark", "list_bookmarks", "get_session", ...]
)
```

### Option C: Global visibility config in manifest

```json
{
  "_meta": {
    "ai.nimblebrain/upjack": {
      "tool_visibility": {
        "mode": "whitelist",
        "include": ["create_bookmark", "list_bookmarks", "delete_bookmark", ...]
      }
    }
  }
}
```

## Recommendation

Option A is the best — it's declarative, per-entity, and lives in the manifest where the entity definitions already are. The app author decides at schema time which operations are relevant for each entity type.

For reference data entities (session, speaker, sponsor), you'd set `"visible": ["get"]` or `"visible": ["get", "search"]`. For personal data entities (bookmark, note, connection), you'd set `"visible": ["create", "list", "delete"]` or similar.

## Impact

The MCP Dev Summit app went from 77 tools to 21 visible tools with the workaround. The `tools/list` response dropped from 278K chars to ~50K, and tool selection accuracy improved significantly.

## Notes

- Hidden tools must remain callable — `tools/call` with a hidden tool name should still work
- This is a listing/discoverability concern, not a security concern
- Graph traversal and activity tools should also be controllable (default: hidden unless opted in)
- The `seed_data`, `add_field`, and `rebuild_index` utility tools should have their own visibility toggle
