---
title: "Entity Model"
description: "Base entity schema, type-prefixed IDs, storage format, schema layering, lifecycle states, relationship indexing, and activity tracking."
draft: false
---

## Overview

Every Upjack entity conforms to a two-layer JSON Schema composition. The **base entity schema** defines common metadata fields shared by all entities across all apps. The **app entity schema** defines domain-specific fields for a particular entity type. These are composed at validation time using JSON Schema `allOf`.

Entities are stored as individual JSON files in the tenant workspace git repository. In the full platform runtime, every write operation (create, update, delete) is a git commit, providing a complete audit trail.

> **Implementation note:** The `upjack` library handles file I/O only. Git commits are the responsibility of the hosting platform or calling code. The commit conventions below describe the intended platform behavior, not current library behavior.

## Base Entity Schema

The base entity schema defines the minimum required structure for all Upjack entities.

### Required Fields

| Field | Type | Pattern / Format | Description |
|-------|------|-----------------|-------------|
| `id` | string | `^[a-z]{2,4}_[0-9A-HJKMNP-TV-Z]{26}$` | Type-prefixed ULID. Immutable after creation. |
| `type` | string | `^[a-z][a-z0-9_]*$` | Entity type name matching the entity definition in the manifest. Immutable after creation. |
| `version` | integer | minimum: 1 | Schema version number. Used for lazy migration (see below). Immutable after creation. |
| `created_at` | string | ISO 8601 date-time | Timestamp of entity creation. Immutable after creation. |
| `updated_at` | string | ISO 8601 date-time | Timestamp of last modification. Auto-updated on every write. |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `created_by` | string | `"agent"` | Origin of the entity. Enum: `user`, `agent`, `system`, `ingestion`, `schedule`. Immutable after creation. |
| `status` | string | `"active"` | Lifecycle state. Enum: `active`, `archived`, `deleted`. |
| `tags` | array | `[]` | Freeform labels. Items: strings, maxLength 64, pattern `^[a-z0-9][a-z0-9-]*$`, maxItems 20, uniqueItems. |
| `source` | object | — | Provenance information for imported or enriched entities. |
| `relationships` | array | — | Typed links to other entities. |

#### `source` Object

| Sub-field | Type | Required | Description |
|-----------|------|----------|-------------|
| `origin` | string | No | Human-readable origin (e.g., `"linkedin"`, `"csv-import"`, `"web-scrape"`). |
| `ref` | string | No | External identifier in the source system. |
| `url` | string (uri) | No | URL back to the source record. |

#### `relationships` Array Items

| Sub-field | Type | Required | Description |
|-----------|------|----------|-------------|
| `rel` | string | Yes | Relationship type (e.g., `"works_at"`, `"parent_of"`, `"related_to"`). |
| `target` | string | Yes | Target entity ID. Pattern: `^[a-z]{2,4}_[0-9A-HJKMNP-TV-Z]{26}$` |
| `label` | string | No | Human-readable label for the relationship. |

### `additionalProperties: true`

The base schema sets `additionalProperties: true`, which is critical for `allOf` composition. Without it, the app schema's domain-specific fields would be rejected by the base schema during validation.

### Base Schema (JSON Schema)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://upjack.dev/schemas/v1/upjack-entity.schema.json",
  "title": "Upjack Entity Base",
  "description": "Base schema for all Upjack entities.",
  "type": "object",
  "required": ["id", "type", "version", "created_at", "updated_at"],
  "additionalProperties": true,
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^[a-z]{2,4}_[0-9A-HJKMNP-TV-Z]{26}$",
      "description": "Type-prefixed ULID. Immutable after creation."
    },
    "type": {
      "type": "string",
      "pattern": "^[a-z][a-z0-9_]*$",
      "description": "Entity type name."
    },
    "version": {
      "type": "integer",
      "minimum": 1,
      "description": "Schema version for lazy migration."
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 creation timestamp."
    },
    "updated_at": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 last-modified timestamp."
    },
    "created_by": {
      "type": "string",
      "enum": ["user", "agent", "system", "ingestion", "schedule"],
      "default": "agent",
      "description": "Origin of the entity."
    },
    "status": {
      "type": "string",
      "enum": ["active", "archived", "deleted"],
      "default": "active",
      "description": "Lifecycle state."
    },
    "tags": {
      "type": "array",
      "items": {
        "type": "string",
        "maxLength": 64,
        "pattern": "^[a-z0-9][a-z0-9-]*$"
      },
      "maxItems": 20,
      "uniqueItems": true,
      "default": [],
      "description": "Freeform labels."
    },
    "source": {
      "type": "object",
      "properties": {
        "origin": { "type": "string" },
        "ref": { "type": "string" },
        "url": { "type": "string", "format": "uri" }
      },
      "description": "Provenance information."
    },
    "relationships": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["rel", "target"],
        "properties": {
          "rel": { "type": "string" },
          "target": {
            "type": "string",
            "pattern": "^[a-z]{2,4}_[0-9A-HJKMNP-TV-Z]{26}$"
          },
          "label": { "type": "string" }
        }
      },
      "description": "Typed links to other entities."
    }
  }
}
```

## Entity IDs

Entity IDs follow the format `{prefix}_{ULID}`:

- **Prefix**: 2-4 lowercase letters defined in the entity manifest (`prefix` field). Must be unique within an app.
- **Separator**: underscore (`_`)
- **ULID**: 26-character Crockford Base32 encoded ULID ([spec](https://github.com/ulid/spec))

The ULID character set excludes `I`, `L`, `O`, and `U` to avoid ambiguity: `0-9A-HJKMNP-TV-Z`.

### ID Pattern

```
^[a-z]{2,4}_[0-9A-HJKMNP-TV-Z]{26}$
```

### Examples

| Entity Type | Prefix | Example ID |
|-------------|--------|------------|
| lead | `ld` | `ld_01HZ3QKBN9YWVJ0RPFA7MT8C5X` |
| company | `co` | `co_01HZ3QKBN9YWVJ0RPFA7MT8C5Y` |
| deal | `dl` | `dl_01HZ3QM4R2XW8K1DPGB6NT9C7Z` |
| activity | `act` | `act_01HZ3QN7V5YX9L2EQHC8PU0D8A` |
| pipeline_config | `pc` | `pc_01HZ3QP9W6ZY0M3FRIC9QV1E9B` |

### Why Prefixed ULIDs

- **Type-evident**: You can identify the entity type from the ID alone without a database lookup.
- **Sortable**: ULIDs are monotonically sortable by creation time.
- **Collision-resistant**: 128-bit randomness per millisecond.
- **Human-friendly**: Short prefixes make IDs recognizable in logs and conversations.

## Schema Layering

Entity validation uses JSON Schema `allOf` composition. At validation time, the platform composes the base schema with the app-specific schema:

```json
{
  "allOf": [
    { "$ref": "https://upjack.dev/schemas/v1/upjack-entity.schema.json" },
    { "$ref": "./lead.schema.json" }
  ]
}
```

### How It Works

1. The **base schema** defines required metadata fields (`id`, `type`, `version`, `created_at`, `updated_at`) and optional common fields (`status`, `tags`, `source`, `relationships`).
2. The **app schema** defines domain-specific fields (e.g., `email`, `company_name`, `deal_value`).
3. `allOf` requires the entity to satisfy **both** schemas simultaneously.
4. Because the base schema sets `additionalProperties: true`, it does not reject the app schema's fields.

### App Schema Example (Lead)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.nimblebrain.ai/apps/crm/lead.schema.json",
  "title": "CRM Lead",
  "description": "A sales lead in the CRM.",
  "type": "object",
  "required": ["name", "email"],
  "properties": {
    "name": {
      "type": "string",
      "maxLength": 256,
      "description": "Full name of the lead."
    },
    "email": {
      "type": "string",
      "format": "email",
      "description": "Primary email address."
    },
    "company_name": {
      "type": "string",
      "maxLength": 256,
      "description": "Company the lead works at."
    },
    "title": {
      "type": "string",
      "maxLength": 256,
      "description": "Job title."
    },
    "stage": {
      "type": "string",
      "enum": ["new", "contacted", "qualified", "converted", "lost"],
      "default": "new",
      "description": "Sales pipeline stage."
    },
    "score": {
      "type": "integer",
      "minimum": 0,
      "maximum": 100,
      "description": "Lead qualification score (0-100)."
    },
    "next_action": {
      "type": "string",
      "description": "Next action to take with this lead."
    },
    "next_action_date": {
      "type": "string",
      "format": "date",
      "description": "When the next action is due."
    }
  },
  "additionalProperties": true
}
```

### Composed Entity (What Gets Stored)

```json
{
  "id": "ld_01HZ3QKBN9YWVJ0RPFA7MT8C5X",
  "type": "lead",
  "version": 1,
  "created_at": "2026-02-15T10:30:00Z",
  "updated_at": "2026-02-15T14:22:00Z",
  "created_by": "agent",
  "status": "active",
  "tags": ["inbound", "saas"],
  "name": "Alice Chen",
  "email": "alice@example.com",
  "company_name": "TechCorp",
  "title": "VP Engineering",
  "stage": "qualified",
  "score": 85,
  "next_action": "Schedule demo call",
  "next_action_date": "2026-02-20",
  "source": {
    "origin": "linkedin",
    "url": "https://linkedin.com/in/alicechen"
  },
  "relationships": [
    {
      "rel": "works_at",
      "target": "co_01HZ3QKBN9YWVJ0RPFA7MT8C5Y",
      "label": "TechCorp"
    }
  ]
}
```

## Lifecycle States

Entities follow a simple lifecycle:

```
active  -->  archived  -->  deleted
  ^             |
  |             |
  +-------------+
    (restore)
```

| State | Meaning | Queryable | Restorable |
|-------|---------|-----------|------------|
| `active` | Normal operational state. Returned by default queries. | Yes | N/A |
| `archived` | Removed from active use but preserved. Not returned by default queries. | With filter | Yes (to active) |
| `deleted` | Soft-deleted. Not returned by any default query. | With filter | Yes (to active) |

- **Soft delete** is the default. `entity_delete` sets `status: "deleted"` and updates `updated_at`.
- **Hard delete** removes the file from the workspace entirely. Only used with explicit `hard: true`.
- **Restore** changes status from `archived` or `deleted` back to `active` via `entity_update`.

## Relationship Indexing

Relationships defined in the `relationships` array are automatically indexed at write time. When an entity is created, updated, or deleted, the framework maintains a reverse index at:

```
{namespace}/data/_index/relations.json
```

The reverse index maps `(target_id, rel)` back to the source entity, enabling efficient lookups in both directions. For example, if lead `ld_01HZ...5X` has `{"rel": "works_at", "target": "co_01HZ...5Y"}`, the index records that `co_01HZ...5Y` has an inbound `works_at` edge from `ld_01HZ...5X`.

### Index Behavior

- **Automatic** — no configuration needed. Any entity with a `relationships` array participates.
- **Write-time updated** — the index is updated atomically on every `create_entity`, `update_entity`, and `delete_entity` call.
- **Self-healing** — if the index file is missing or corrupt, it is rebuilt from entity files on the next read. You can also force a rebuild with the `rebuild_index()` method or the `rebuild_index` MCP tool.

## Querying Relationships

Three methods on `UpjackApp` expose the relationship graph. Each is also registered as an MCP tool per entity type.

### `query_by_relationship`

Find entities of a given type that have a specific relationship to a target.

```python
# Find all leads that work at company co_01HZ...5Y
leads = app.query_by_relationship("lead", "works_at", "co_01HZ...5Y")

# With additional field filter and limit
leads = app.query_by_relationship(
    "lead", "works_at", "co_01HZ...5Y",
    filter={"stage": "qualified"},
    limit=10,
)
```

Uses the reverse index for fast lookup without scanning entity files.

### `get_related`

Follow relationship edges from an entity, forward or reverse, and return resolved entities.

```python
# Forward: get entities this lead points to
related = app.get_related("ld_01HZ...5X")

# Forward, specific relationship
companies = app.get_related("ld_01HZ...5X", rel="works_at")

# Reverse: get entities that point to this company
inbound = app.get_related("co_01HZ...5Y", direction="reverse")

# Both directions
all_related = app.get_related("ld_01HZ...5X", direction="both")
```

### `get_composite`

Load an entity with all its related entities in a single call. Returns the entity with a `_related` key containing forward and reverse relationships grouped by relationship type.

```python
composite = app.get_composite("lead", "ld_01HZ...5X")
```

```json
{
  "id": "ld_01HZ...5X",
  "type": "lead",
  "name": "Alice Chen",
  "_related": {
    "works_at": [
      { "id": "co_01HZ...5Y", "type": "company", "name": "TechCorp" }
    ],
    "~works_at": [
      { "id": "dl_01HZ...7Z", "type": "deal", "name": "TechCorp Expansion" }
    ]
  }
}
```

#### The `~` Prefix Convention

In composite results, forward relationships use the bare relationship name (`works_at`), while reverse relationships are prefixed with `~` (`~works_at`). This makes direction unambiguous when both forward and reverse edges share the same relationship type. The `~` prefix is only a display convention in `get_composite` results — it is not stored in entity data or the index.

The optional `depth` parameter controls how many hops to traverse (default: 1).

## Activity Tracking

Activity tracking is an opt-in feature that provides a built-in audit log for entity interactions.

### Enabling

Add `"activities": true` to the `ai.nimblebrain/upjack` extension in your manifest:

```json
{
  "_meta": {
    "ai.nimblebrain/upjack": {
      "namespace": "apps/crm",
      "entities": { ... },
      "activities": true
    }
  }
}
```

### What It Provides

When enabled, the framework registers an `activity` entity type automatically (prefix: `act`, plural: `activities`) with a built-in schema:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action` | string | Yes | What happened (e.g., `"called"`, `"emailed"`, `"stage_changed"`). |
| `detail` | object | No | Arbitrary metadata about the action. |

Activities are linked to their subject via a `subject` relationship, so they participate in the relationship index like any other entity.

### Logging and Querying Activities

```python
# Log an activity
app.log_activity("ld_01HZ...5X", "called", detail={"duration": 300})

# Get activities for a subject
activities = app.get_activities("ld_01HZ...5X")

# Filter by action
calls = app.get_activities("ld_01HZ...5X", action="called", limit=10)
```

Both `log_activity` and `get_activities` are also registered as MCP tools when activities are enabled.

## Storage

Entities are stored as individual JSON files in the tenant workspace git repository.

### Path Format

```
{namespace}/data/{plural}/{id}.json
```

### Examples

| Entity | Path |
|--------|------|
| Lead `ld_01HZ...5X` | `apps/crm/data/leads/ld_01HZ3QKBN9YWVJ0RPFA7MT8C5X.json` |
| Company `co_01HZ...5Y` | `apps/crm/data/companies/co_01HZ3QKBN9YWVJ0RPFA7MT8C5Y.json` |
| Deal `dl_01HZ...7Z` | `apps/crm/data/deals/dl_01HZ3QM4R2XW8K1DPGB6NT9C7Z.json` |
| Pipeline config (singleton) | `apps/crm/data/pipeline_configs/pc_01HZ3QP9W6ZY0M3FRIC9QV1E9B.json` |

### File Format

Each file contains a single JSON object: the complete entity with base and domain fields. Files are formatted with 2-space indentation for human readability and clean git diffs.

### Git Commits

> **Platform-level.** These commit conventions describe the intended behavior of the NimbleBrain platform runtime. The `upjack` library writes files but does not make git commits.

Every entity write is an atomic git commit:

- **Create**: `crm: create lead ld_01HZ...5X`
- **Update**: `crm: update lead ld_01HZ...5X`
- **Delete (soft)**: `crm: delete lead ld_01HZ...5X`
- **Delete (hard)**: `crm: hard-delete lead ld_01HZ...5X`

## Version Field and Lazy Migration

The `version` field is a **schema version number**, not a record revision counter. It indicates which version of the entity schema this record was created or last migrated under.

### How It Works

1. App v0.1.0 defines lead schema version 1. All leads are created with `"version": 1`.
2. App v0.2.0 adds a new required field with a default. The lead schema is now version 2.
3. Existing leads still have `"version": 1`. They are **not** migrated immediately.
4. When an existing lead is read, the runtime checks `version < current_schema_version`.
5. If a migration function exists, it is applied on read (lazy). The migrated entity is written back with the new version.
6. New leads are created with `"version": 2`.

Lazy migration avoids bulk rewrites on app update. Records are migrated as they are accessed.

## Fields Intentionally Excluded from Base

The following fields were considered for the base schema and intentionally excluded:

| Field | Reason for Exclusion |
|-------|---------------------|
| `name` / `title` | Not every entity has a name. Singletons, activities, and config entities often lack one. Domain-specific naming belongs in the app schema. |
| `description` | Too domain-specific. A lead's "description" means something different from a deal's. |
| `confidence` | Goes stale quickly. Better as a computed/transient value than a stored field. |
| `notes` | Better modeled as a related entity (e.g., `activity` of type `note`) for proper history tracking. |
| `assignee` / `owner` | Not all apps have multi-user assignment. Single-user apps do not need this. |
| `priority` | Domain-specific semantics. A lead priority scale differs from a task priority scale. |

These fields can and should be added in app-specific schemas where appropriate.
