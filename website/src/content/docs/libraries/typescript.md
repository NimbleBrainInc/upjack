---
title: TypeScript Library
description: "The upjack TypeScript package: schema-driven entity management and MCP server generation for Node.js."
draft: false
---

Schema-driven entity management for AI-native applications. TypeScript edition.

Define entities as JSON Schemas + a manifest. The library handles CRUD, validation, ID generation, storage, and search. Add `@modelcontextprotocol/sdk` to serve it as an MCP server.

## Install

```bash
# Core library (entity management only)
npm install upjack

# With MCP server support (peer dependency)
npm install upjack @modelcontextprotocol/sdk
```

## Usage: Entity Management

```typescript
import { UpjackApp } from "upjack";

const app = UpjackApp.fromManifest("manifest.json");

// Create an entity
const contact = app.createEntity("contact", {
  first_name: "Sarah",
  last_name: "Chen",
  email: "sarah@example.com",
});

// List entities
const contacts = app.listEntities("contact");

// Update an entity
app.updateEntity("contact", contact.id, { lead_score: 85 });

// Get a single entity
const fetched = app.getEntity("contact", contact.id);

// Search entities
const results = app.searchEntities("contact", {
  query: "sarah",
  filter: { lead_score: { $gte: 70 } },
  sort: "-lead_score",
  limit: 10,
});

// Delete an entity (soft delete by default)
app.deleteEntity("contact", contact.id);

// Hard delete (permanent)
app.deleteEntity("contact", contact.id, true);
```

## Usage: MCP Server

```typescript
import { createServer, startServer } from "upjack/server";

// Quick start — creates and runs the server
startServer("manifest.json");

// Or create the server for more control
const server = createServer("manifest.json");
// Customize before starting...
```

This generates CRUD tools for every entity type in the manifest, exposes context and skills as MCP resources, and handles validation automatically. See the [CRM example](https://github.com/NimbleBrainInc/upjack/tree/main/examples/crm/server.ts) for a complete example.

## Configuration

The workspace root (where entity data is stored) is resolved in this order:

1. `UPJACK_ROOT` environment variable
2. `--root` CLI argument (when using `upjack serve`)
3. `.upjack` in the current directory (default)

Runners like mpak or NimbleBrain set `UPJACK_ROOT` automatically to ensure data persists outside the bundle cache.

### Tool Visibility

Entity definitions can include a `tools` array to control which operations appear in `tools/list`. All tools remain callable via `tools/call`. See [Manifest Reference: Entity Definition](/reference/manifest/) for options.

## Types

The library exports key TypeScript interfaces:

```typescript
import type { EntityRecord, EntityDefinition, UpjackManifestExtension } from "upjack";
```

**`EntityRecord`**: A single entity with base fields and app-specific fields.
- `id`, `type`, `version`, `created_at`, `updated_at`, `created_by`, `status`, `tags`, `relationships`, `source?`
- Plus `[key: string]: unknown` for app-specific fields

**`EntityDefinition`**: Entity configuration from the manifest.
- `name`, `plural?`, `schema`, `prefix`, `index?`

**`UpjackManifestExtension`**: The `_meta["ai.nimblebrain/upjack"]` block.
- `upjack_version`, `namespace`, `entities`, `display?`, `skills?`, `context?`, `seed?`

## Error Handling

All operations throw standard `Error` instances with descriptive messages:

```typescript
try {
  app.createEntity("contact", { name: "Bad" });
} catch (e) {
  // Error: Validation failed: must have required property 'email'
  console.error(e.message);
}

try {
  app.getEntity("contact", "ct_nonexistent");
} catch (e) {
  // Error: Entity not found: ct_nonexistent
  console.error(e.message);
}
```

| Error message pattern | When |
|----------------------|------|
| `Unknown entity type '...'` | Entity type not defined in manifest |
| `Entity not found: ...` | Entity ID does not exist on disk |
| `Validation failed: ...` | Data fails JSON Schema validation (AJV details included) |

## Requirements

- Node.js >= 18
- `@modelcontextprotocol/sdk` ^1.0.0 (only for MCP server support, peer dependency)

## API Differences from Python

| Aspect | TypeScript | Python |
|--------|------------|--------|
| Method naming | `camelCase` (`createEntity`) | `snake_case` (`create_entity`) |
| Server framework | @modelcontextprotocol/sdk | FastMCP |
| MCP extra | `@modelcontextprotocol/sdk` (peer dep) | `upjack[mcp]` (optional) |
| Schema validation | AJV (2020-12) | `jsonschema` (Draft202012Validator) |
| ID generation | `ulidx` | `python-ulid` |
| Search API | Options object: `{ query, filter, sort, limit }` | Keyword args: `query=, filter=, sort=, limit=` |
| Error types | Generic `Error` with descriptive messages | `ValueError`, `FileNotFoundError`, `ValidationError` |
| Lint/format | Biome | ruff |
| Type checking | tsc | ty |
| Testing | vitest | pytest |

Looking for Python? See the [Python Library](/libraries/python/) page.

## Development

```bash
npm install
make check    # format + lint + typecheck + test
make build    # produces dist/ (ESM + .d.ts)
```

## License

Apache 2.0
