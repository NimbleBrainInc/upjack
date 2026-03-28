---
title: "Schema Evolution"
description: "How Upjack handles schema changes without migrations: hydrate-on-read, defaults-driven evolution, and the rules for safe schema changes."
draft: false
---

## The Problem

Your app ships with a campaign entity schema. Three weeks later, you need to add a `score` field. In a traditional system, you'd write a migration, run it against every record, pray nothing breaks. Upjack doesn't work that way.

Upjack entities are JSON files. There is no database to `ALTER TABLE` on. Instead, the framework uses **hydrate-on-read** — schema defaults are applied automatically when entities are loaded, so old data conforms to the new schema without rewriting anything.

## How It Works

Every read path in the framework — `get_entity`, `list_entities`, `search_entities`, and the merge step of `update_entity` — checks the entity's schema for `default` values and fills in any missing fields before returning the entity to the caller.

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  JSON file   │────▶│   hydrate    │────▶│  caller gets │
│  (on disk)   │     │  defaults    │     │  complete    │
│              │     │  from schema │     │  entity      │
│  score: ???  │     │  score → 0   │     │  score: 0    │
└─────────────┘     └──────────────┘     └──────────────┘
```

1. Entity is read from disk (raw JSON, may be missing fields)
2. Framework walks the schema's `properties` and any `allOf` members
3. For each property with a `default` that is absent from the entity, the default is applied
4. The hydrated entity is returned to the caller

On **update**, the same hydration happens before the merge and validation step. This means an old entity missing the new field gets the default filled in, the update is merged on top, and validation against the new schema succeeds. The hydrated + updated entity is then written back to disk — effectively a lazy migration.

## Adding a Field (The Common Case)

This is the most common schema evolution: adding a new field to an existing entity type.

### Step 1: Add the field to your schema with a `default`

```json
{
  "properties": {
    "score": {
      "type": "integer",
      "minimum": 0,
      "maximum": 100,
      "default": 0,
      "description": "Lead qualification score (0-100)."
    }
  }
}
```

### Step 2: That's it.

Old entities that don't have `score` will return `0` when read. New entities will have whatever value the caller provides, or `0` if omitted. No migration script, no bulk rewrite, no downtime.

### What happens under the hood

| Operation | Old entity (no `score`) | New entity |
|-----------|------------------------|------------|
| `get_entity` | Returns `score: 0` (hydrated) | Returns `score: 85` (as stored) |
| `list_entities` | Returns `score: 0` (hydrated) | Returns `score: 85` (as stored) |
| `search_entities` | Returns `score: 0` (hydrated) | Returns `score: 85` (as stored) |
| `update_entity` | Hydrates `score: 0`, merges update, writes back | Normal merge and write |

After an old entity is updated for any reason, the hydrated default is persisted to disk. Over time, entities lazily migrate forward as they are touched.

## Safe vs Unsafe Schema Changes

### Safe (no migration needed)

| Change | Why it's safe |
|--------|--------------|
| **Add optional field** | Missing fields are ignored on read, absent from validation |
| **Add field with `default`** | Hydrate-on-read fills the value automatically |
| **Add field to `required` with `default`** | Hydration fills it before validation runs |
| **Remove a field** | `additionalProperties: true` means old data with extra fields still validates |
| **Widen an enum** (add values) | Old values still valid, new values available |
| **Relax a constraint** (remove `minimum`, widen `maxLength`) | Existing data that passed the old constraint passes the new one |

### Unsafe (requires manual handling)

| Change | Why it breaks | What to do |
|--------|--------------|------------|
| **Add required field without `default`** | Old entities fail validation on update | Always provide a `default` |
| **Narrow an enum** (remove values) | Old entities with removed values fail validation | Add a migration skill or keep the old values |
| **Change a field's type** | Old data doesn't match new type | Add a migration skill |
| **Rename a field** | Old field name unrecognized, new field missing | Add a migration skill |
| **Tighten a constraint** (lower `maximum`, add `pattern`) | Old data may violate new constraint | Audit existing data first |

## Defaults by Type

The `default` keyword works for any JSON Schema type:

```json
{
  "properties": {
    "score": { "type": "integer", "default": 0 },
    "priority": { "type": "string", "default": "medium" },
    "enabled": { "type": "boolean", "default": true },
    "channels": {
      "type": "array",
      "items": { "type": "string" },
      "default": ["email"]
    },
    "config": {
      "type": "object",
      "default": { "retries": 3, "timeout": 30 }
    }
  }
}
```

## The `version` Field

Every entity has a `version` field (integer, minimum 1) stamped at creation time. This records which schema version the entity was created under.

The `version` field is **informational** — it tells you how old an entity's schema shape is, but the framework doesn't use it to decide whether to hydrate. Hydration always runs when a schema is available, regardless of version. This is intentional: it keeps the logic simple and means you can never get into a state where an entity is "too old" to read.

If you want to track schema versions explicitly, use a convention like `x-upjack-version` in your schema file:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "x-upjack-version": 2,
  "properties": { ... }
}
```

## Migration Skills (Advanced)

For the rare case where a default isn't enough — renaming a field, restructuring nested data, changing a field's type — you can write a migration skill. This is a Markdown skill that the agent executes against entities that need transformation.

Migration skills are a power-user escape hatch, not the primary path. If you find yourself writing migration skills frequently, your schema design may be evolving too aggressively. Prefer additive changes with defaults.

### Example: Renaming a field

If you rename `company_name` to `organization`:

1. Add `organization` with a `default` of `""`
2. Write a skill that reads old entities, copies `company_name` to `organization`, and removes `company_name`
3. Run the skill against the entity set (via `search_entities` + `update_entity`)
4. Once all entities are migrated, remove `company_name` from the schema

## Design Rationale

### Why not traditional migrations?

Upjack entities are JSON files in a git-backed workspace. There is no database server to run `ALTER TABLE` against. Traditional migration frameworks (Alembic, Flyway, Knex) assume a centralized database — they don't map to file-based storage.

### Why not refuse to load old entities?

Catastrophic DX. If adding a field breaks every existing entity, developers won't evolve their schemas — they'll work around the framework instead. The framework should make the right thing easy.

### Why not maintain multiple schema versions simultaneously?

Complexity explosion. If the runtime needs to know "entity version 1 uses schema A, version 2 uses schema B", every read path becomes a version dispatch. Hydrate-on-read sidesteps this entirely: there's one schema, and missing fields get filled in.

### Why hydrate on read instead of on write?

Both. Reads are hydrated so callers always get complete entities. Updates hydrate before merge so validation passes. Once an entity is updated, the hydrated values are persisted — the entity lazily migrates forward on disk.
