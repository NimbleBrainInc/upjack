---
title: "Schemas"
description: "JSON Schema definitions published by Upjack (entity base schema, manifest extension schema, and app schema) with hosted URLs and usage."
draft: false
---

## Overview

Upjack publishes two JSON Schemas (draft 2020-12) that define the structure of entities and manifest extensions. These schemas are:

- Hosted at `https://upjack.dev/schemas/v1/` for use as `$ref` targets
- Source-controlled in the [`schemas/v1/`](https://github.com/NimbleBrainInc/upjack/tree/main/schemas/v1) directory of the repository
- Available in both source form (with `$ref`) and bundled form (all references dereferenced for standalone validation)

## Published Schemas

| Schema | URL | Purpose |
|--------|-----|---------|
| **upjack-entity** | [`upjack-entity.schema.json`](https://upjack.dev/schemas/v1/upjack-entity.schema.json) | Base entity schema. Common fields shared by all entities across all apps. |
| **upjack-manifest** | [`upjack-manifest.schema.json`](https://upjack.dev/schemas/v1/upjack-manifest.schema.json) | Manifest extension schema. Validates `_meta["ai.nimblebrain/upjack"]`. |

Bundled versions (all `$ref` dereferenced) are also available at the same path with a `.bundled` suffix:

- [`upjack-entity.bundled.schema.json`](https://upjack.dev/schemas/v1/upjack-entity.bundled.schema.json)
- [`upjack-manifest.bundled.schema.json`](https://upjack.dev/schemas/v1/upjack-manifest.bundled.schema.json)

## Upjack Entity Schema

**URL:** `https://upjack.dev/schemas/v1/upjack-entity.schema.json`

The base entity schema defines the minimum required structure for all Upjack entities. Every app-specific entity schema composes with this via `allOf`. See [Entity Model](/reference/entity-model/) for the full field reference.

**Required fields:** `id`, `type`, `version`, `created_at`, `updated_at`

**Optional fields:** `created_by`, `status`, `tags`, `source`, `relationships`

### How apps reference it

App entity schemas use `allOf` to compose with the base:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "allOf": [
    { "$ref": "https://upjack.dev/schemas/v1/upjack-entity.schema.json" }
  ],
  "properties": {
    "title": { "type": "string" },
    "priority": { "type": "string", "enum": ["low", "medium", "high"] }
  },
  "required": ["title"]
}
```

The base schema sets `additionalProperties: true`, so app-specific fields are accepted during validation. At runtime, the `upjack` library resolves the `$ref` using a bundled local copy of the base schema, so no network request is made.

## Upjack Manifest Schema

**URL:** `https://upjack.dev/schemas/v1/upjack-manifest.schema.json`

Validates the `_meta["ai.nimblebrain/upjack"]` extension block inside an [MCPB](https://github.com/modelcontextprotocol/mcpb) manifest. This schema defines the structure for entities, skills, bundles, hooks, schedules, views, context, and seed configuration.

See [Manifest Reference](/reference/manifest/) for the full field-by-field specification.

### Key fields validated

| Field | Description |
|-------|-------------|
| `upjack_version` | Must be `"0.1"` |
| `namespace` | Must match `^apps/[a-z][a-z0-9-]*$` |
| `entities` | At least one entity definition with `name`, `schema`, `prefix` |
| `skills` | Optional array of mpak, GitHub, or bundled skill references |
| `bundles` | Optional dependency map keyed by alias |
| `hooks` | Optional event-driven skill triggers |
| `schedules` | Optional cron-based skill invocations |
| `views` | Optional named entity queries |

## Schema Versioning

Schemas are versioned under `/v1/`. The version in the URL path corresponds to the schema structure version, not the Upjack library version. Breaking changes to the schema structure will increment the version path (e.g., `/v2/`).

The `upjack_version` field inside the manifest (`"0.1"`) tracks the framework spec version independently from the schema URL version.

## Development Workflow

Schema source files live in `schemas/v1/` in the repository. After editing:

```bash
cd schemas
make validate    # bundles $refs and runs AJV validation tests
```

This generates the `.bundled.schema.json` files (with all `$ref` dereferenced) and validates sample data against them. Both source and bundled schemas are committed to the repository.

Schemas are synced to the website for hosting via:

```bash
./scripts/sync-schemas.sh    # copies schemas/v1/ → website/public/schemas/v1/
```

The website build deploys them to `upjack.dev/schemas/v1/`.

## Using Schemas for Validation

### In Python

The `upjack` library handles schema validation automatically, so you don't need to reference the schemas directly. When you call `app.create_entity()` or `app.update_entity()`, the library validates against the composed schema (base + app) before writing.

```python
from upjack import UpjackApp

app = UpjackApp.from_manifest("manifest.json")
# Validation happens automatically:
app.create_entity("task", {"title": "Hello"})  # valid
app.create_entity("task", {})                   # raises jsonschema.ValidationError
```

### In TypeScript

Same automatic validation:

```typescript
import { UpjackApp } from "upjack";

const app = UpjackApp.fromManifest("manifest.json");
app.createEntity("task", { title: "Hello" });  // valid
app.createEntity("task", {});                   // throws validation error
```

### Standalone validation

Use the bundled schemas with any JSON Schema draft 2020-12 validator:

```bash
# Validate a manifest
ajv validate -s upjack-app.bundled.schema.json -d manifest.json

# Validate entity data
ajv validate -s upjack-entity.bundled.schema.json -d entity.json
```
