---
title: "Manifest Reference"
description: "Complete reference for the Upjack manifest format. The _meta extension that transforms an MCPB package into an Upjack app."
draft: false
---

## Overview

The upjack manifest is the extension block that transforms a standard [MCPB](https://github.com/modelcontextprotocol/mcpb) package into a NimbleBrain Upjack app. It lives inside `manifest.json` at `_meta["ai.nimblebrain/upjack"]`.

```json
{
  "name": "@nimblebrain/crm",
  "version": "0.1.0",
  "description": "Lightweight CRM for founder-led sales",
  "mcp_config": { ... },
  "_meta": {
    "ai.nimblebrain/upjack": {
      "upjack_version": "0.1",
      "namespace": "apps/crm",
      "entities": [ ... ],
      "skills": [ ... ]
    }
  }
}
```

The outer `manifest.json` follows the standard [MCPB manifest spec](https://github.com/modelcontextprotocol/mcpb/blob/main/schemas/mcpb-manifest-v0.4.schema.json). Non-NimbleBrain tools ignore `_meta` and install the package as a regular MCP server. The NimbleBrain platform reads the upjack extension and performs additional installation steps (workspace scaffolding, entity registration, skill installation).

The upjack extension is validated against the [upjack-manifest schema](/reference/schemas/#upjack-manifest-schema). Entity data is validated against the [upjack-entity schema](/reference/schemas/#upjack-entity-schema) composed with your app-specific schema via `allOf`.

## Top-Level Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `upjack_version` | string | Yes | — | Framework version. Const `"0.1"` for this spec. |
| `namespace` | string | Yes | — | Install path in tenant workspace. Pattern: `^apps/[a-z][a-z0-9-]*$` |
| `display` | object | No | — | Human-readable display metadata. |
| `entities` | array | Yes | — | Entity definitions. minItems: 1. |
| `skills` | array | No | `[]` | Skill references. |
| `bundles` | object | No | `{}` | Bundle (MCPB package) dependencies, keyed by alias. |
| `required_tools` | array | No | `[]` | Platform tools the app requires. |
| `required_connections` | array | No | `[]` | OAuth/API connections the app requires. |
| `schedules` | array | No | `[]` | Cron-based scheduled skill invocations. |
| `hooks` | array | No | `[]` | Event-driven skill triggers. |
| `views` | array | No | `[]` | Named entity views (filtered/sorted perspectives). |
| `context` | string | No | — | Path to a Markdown context file within the package. |
| `seed` | object | No | — | Initial data seeding configuration. |
| `server` | object or null | No | — | Custom MCP server configuration. `null` for pure declarative apps. *Note: this field lives in the outer MCPB manifest, not in the upjack extension block.* |

## Field Specifications

### `upjack_version`

```json
{
  "type": "string",
  "const": "0.1"
}
```

Identifies which version of the Upjack framework this manifest targets. Installers check this field to determine compatibility. This spec defines version `"0.1"`.

### `namespace`

```json
{
  "type": "string",
  "pattern": "^apps/[a-z][a-z0-9-]*$"
}
```

The directory path within the tenant workspace where the app is installed. All entity data, skills, views, and lock files live under this namespace.

Examples: `apps/crm`, `apps/research-tracker`, `apps/content-pipeline`

### `display`

```json
{
  "type": "object",
  "properties": {
    "name": { "type": "string", "maxLength": 64 },
    "icon": { "type": "string", "maxLength": 8 },
    "category": {
      "type": "string",
      "enum": [
        "sales", "marketing", "operations", "research",
        "finance", "hr", "engineering", "support", "custom"
      ]
    }
  }
}
```

| Sub-field | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | No | Human-readable app name. Max 64 characters. |
| `icon` | string | No | Emoji or short icon string. Max 8 characters. |
| `category` | string | No | App category for organization and discovery. |

### `entities`

```json
{
  "type": "array",
  "minItems": 1,
  "items": { "$ref": "#/$defs/entity_definition" }
}
```

Every Upjack app must define at least one entity. Each entity definition describes the data type, its schema, ID prefix, and storage behavior.

#### Entity Definition

| Sub-field | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | string | Yes | — | Entity type name. Pattern: `^[a-z][a-z0-9_]*$` |
| `plural` | string | No | `{name}s` | Plural form, used in storage paths and display. |
| `schema` | string | Yes | — | Relative path to JSON Schema file within the package. |
| `prefix` | string | Yes | — | ID prefix for ULID generation. Pattern: `^[a-z]{2,4}$` |
| `storage` | string | No | `data/{plural}/` | Relative storage path within the namespace. |
| `index` | boolean | No | `true` | Whether to index this entity for full-text search. |
| `singleton` | boolean | No | `false` | Whether only one instance of this entity can exist. |
| `tools` | string[] | No | all | Tool categories to list in `tools/list`. All tools remain callable. Options: `create`, `get`, `update`, `list`, `search`, `delete`, `query_by_relationship`, `get_related`, `get_composite`. |

```json
{
  "name": "lead",
  "plural": "leads",
  "schema": "schemas/lead.schema.json",
  "prefix": "ld",
  "storage": "data/leads/",
  "index": true,
  "singleton": false,
  "tools": ["create", "get", "update", "list", "search", "delete"]
}
```

The `prefix` is prepended to the ULID to form the entity ID: `ld_01HZ3QKBN9YWVJ0RPFA7MT8C5X`. Prefixes must be unique within an app.

#### Tool Visibility

The `tools` array controls which operation categories appear in `tools/list`. When omitted, all tools are listed (default). When specified, only the listed categories are discoverable by the LLM. All tools remain registered and callable via `tools/call` regardless of this setting.

Available categories: `create`, `get`, `update`, `list`, `search`, `delete`, `query_by_relationship`, `get_related`, `get_composite`.

```json
{
  "name": "session",
  "tools": ["get", "search"]
}
```

For reference data entities that should be read-only from the LLM's perspective, use `"tools": ["get", "search"]`. For entities that need full CRUD, omit the `tools` field entirely.

To control global utility tool visibility, add `utility_tools` at the upjack extension level (sibling of `entities`):

```json
{
  "_meta": {
    "ai.nimblebrain/upjack": {
      "entities": [...],
      "utility_tools": ["rebuild_index"]
    }
  }
}
```

Available utility tools: `seed_data`, `add_field`, `rebuild_index`. When omitted, all are listed.

### `skills`

```json
{
  "type": "array",
  "items": { "oneOf": [
    { "$ref": "#/$defs/skill_mpak" },
    { "$ref": "#/$defs/skill_github" },
    { "$ref": "#/$defs/skill_bundled" }
  ]}
}
```

Skills can be sourced from three locations:

#### mpak skill

A skill published as an mpak package.

| Sub-field | Type | Required | Description |
|-----------|------|----------|-------------|
| `source` | string | Yes | Const `"mpak"` |
| `name` | string | Yes | Scoped package name. Pattern: `^@[a-z0-9-]+/[a-z0-9-]+$` |
| `version` | string | Yes | Semver range (e.g., `"^1.0.0"`, `">=2.0.0 <3.0.0"`). |
| `integrity` | string | No | SHA-256 hash for verification. Pattern: `^sha256-[a-f0-9]{64}$` |

```json
{
  "source": "mpak",
  "name": "@nimblebrain/lead-qualification",
  "version": "^1.0.0",
  "integrity": "sha256-abc123..."
}
```

#### GitHub skill

A skill file hosted in a GitHub repository.

| Sub-field | Type | Required | Description |
|-----------|------|----------|-------------|
| `source` | string | Yes | Const `"github"` |
| `repo` | string | Yes | GitHub repo in `owner/repo` format. |
| `path` | string | Yes | Path to the skill file within the repo. |
| `ref` | string | No | Git ref (branch, tag, or commit SHA). Defaults to default branch. |

```json
{
  "source": "github",
  "repo": "NimbleBrainInc/skills",
  "path": "sales/lead-qualification.md",
  "ref": "main"
}
```

#### Bundled skill

A skill file included directly in the MCPB package.

| Sub-field | Type | Required | Description |
|-----------|------|----------|-------------|
| `source` | string | Yes | Const `"bundled"` |
| `path` | string | Yes | Relative path to the `SKILL.md` file within the package. |

```json
{
  "source": "bundled",
  "path": "skills/deal-review.md"
}
```

### `bundles`

```json
{
  "type": "object",
  "patternProperties": {
    "^[a-z][a-z0-9-]*$": { "$ref": "#/$defs/bundle_dependency" }
  },
  "additionalProperties": false
}
```

Bundle dependencies are MCPB packages that provide MCP tools the app needs. They are keyed by a **logical alias**, so skills reference tools via the alias (e.g., `email__send_email`), not the package name. The alias indirection enables swappability.

#### Bundle Dependency

| Sub-field | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `description` | string | Yes | — | Human-readable purpose of this dependency. |
| `required` | boolean | No | `true` | Whether the app can function without this bundle. |
| `default` | object | Yes | — | Default package (`name` + `version`). |
| `alternatives` | array | No | `[]` | Alternative packages that satisfy the same contract. |
| `tools_used` | array | Yes | — | Tool names the app invokes. minItems: 1. This is the compatibility contract. |
| `config_map` | object | No | `{}` | Configuration keys the bundle expects. |

```json
{
  "email": {
    "description": "Email sending capability",
    "required": true,
    "default": {
      "name": "@nimblebrain/aws-ses",
      "version": "^1.0.0"
    },
    "alternatives": [
      { "name": "@nimblebrain/sendgrid", "version": "^1.0.0" }
    ],
    "tools_used": ["send_email", "list_templates"],
    "config_map": {
      "from_address": "Default sender email address"
    }
  }
}
```

The `tools_used` array is the **compatibility contract**. During installation, the installer verifies that the chosen package exposes all listed tools. If a tool is missing, installation fails with an explicit error.

### `required_tools`

```json
{
  "type": "array",
  "items": { "type": "string" }
}
```

Platform tools the app requires. These are always-available tools provided by the NimbleBrain platform (not bundle dependencies).

```json
["platform:web_search", "platform:file_read", "platform:git_commit"]
```

### `required_connections`

```json
{
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "type": { "type": "string" },
      "required": { "type": "boolean", "default": true },
      "purpose": { "type": "string" }
    },
    "required": ["type"]
  }
}
```

OAuth or API connections the user must configure before the app is fully functional.

```json
[
  {
    "type": "google-workspace",
    "required": true,
    "purpose": "Access Google Calendar for meeting scheduling"
  },
  {
    "type": "linkedin",
    "required": false,
    "purpose": "Enrich lead profiles with LinkedIn data"
  }
]
```

### `schedules`

```json
{
  "type": "array",
  "items": { "$ref": "#/$defs/schedule" }
}
```

#### Schedule

| Sub-field | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | string | Yes | — | Schedule identifier. Pattern: `^[a-z][a-z0-9-]*$` |
| `cron` | string | Yes | — | 5-field cron expression (minute hour day-of-month month day-of-week). |
| `skill` | string | Yes | — | Name of the skill to invoke. |
| `description` | string | No | — | Human-readable description. |
| `enabled_by_default` | boolean | No | `true` | Whether this schedule is active on install. |

```json
{
  "name": "weekly-pipeline-review",
  "cron": "0 9 * * 1",
  "skill": "pipeline-review",
  "description": "Review deal pipeline every Monday at 9am",
  "enabled_by_default": true
}
```

### `hooks`

```json
{
  "type": "array",
  "items": { "$ref": "#/$defs/hook" }
}
```

#### Hook

| Sub-field | Type | Required | Description |
|-----------|------|----------|-------------|
| `event` | string | Yes | Lifecycle event. Enum: `entity.created`, `entity.updated`, `entity.deleted`, `entity.status_changed`, `app.installed`, `app.updated` |
| `entity` | string | No | Filter to a specific entity type. Only applies to `entity.*` events. |
| `condition` | string | No | JSONPath expression that must evaluate to true. |
| `skill` | string | Yes | Name of the skill to invoke when the hook fires. |

```json
{
  "event": "entity.created",
  "entity": "lead",
  "skill": "lead-qualification"
},
{
  "event": "entity.status_changed",
  "entity": "deal",
  "condition": "$.status == 'active'",
  "skill": "deal-review"
}
```

### `views`

```json
{
  "type": "array",
  "items": { "$ref": "#/$defs/view" }
}
```

#### View

| Sub-field | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | string | Yes | — | View identifier. |
| `entity` | string | Yes | — | Entity type this view applies to. |
| `description` | string | No | — | Human-readable description. |
| `filter` | string | No | — | JSONPath filter expression. |
| `sort` | string | No | — | Sort expression (field name, prefix with `-` for descending). |
| `storage` | string | No | `views/` | Relative storage path for materialized view data. |

```json
{
  "name": "open-deals",
  "entity": "deal",
  "description": "All active deals sorted by expected close date",
  "filter": "$.status == 'active'",
  "sort": "expected_close",
  "storage": "views/"
}
```

### `context`

```json
{
  "type": "string"
}
```

Path to a Markdown file within the package that provides additional context for the agent. This file is loaded when the app is active and gives the agent background knowledge about the domain, business rules, or organizational conventions.

```json
"context": "context/crm-overview.md"
```

### `seed`

```json
{
  "type": "object",
  "properties": {
    "data": { "type": "string" },
    "run_on_install": { "type": "boolean", "default": true }
  }
}
```

| Sub-field | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `data` | string | Yes | — | Path to seed data directory or file within the package. |
| `run_on_install` | boolean | No | `true` | Whether to seed data automatically on install. |

```json
{
  "data": "seed/",
  "run_on_install": true
}
```

The seed directory contains JSON files organized by entity type. The installer creates entities from these files during installation.

## Complete Example: CRM App

See the [CRM example manifest](https://github.com/NimbleBrainInc/upjack/blob/main/examples/crm/manifest.json) for a full working CRM manifest. Here is a summary of what it declares:

1. **Five entity types** with typed ID prefixes: contacts (`ct_`), companies (`co_`), deals (`dl_`), pipeline (`pl_`, singleton), and activities (`act_`).
2. **Four skills**: three bundled in the package, one from mpak.
3. **Three bundle dependencies**: email (required, with alternatives), enrichment (optional), and PDF generation (optional).
4. **Two required connections**: email (required) and calendar (optional).
5. **Three schedules**: daily pipeline review, weekly stale deal alert, nightly lead scoring.
6. **Two hooks**: auto-score new contacts, trigger forecast on closed deals.
7. **Three views**: hot leads, stale deals, weekly pipeline.
8. **Seed data** loaded on install.
9. **Custom MCP server** via `create_server()` (Tier 2 app).

The manifest demonstrates every major Upjack feature: entities with schemas, bundled and external skills, alias-based bundle dependencies with alternatives, hooks, schedules, views, seed data, and server configuration.
