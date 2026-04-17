# Changelog

All notable changes to this project will be documented in this file.

This project follows [Keep a Changelog](https://keepachangelog.com/).

## [0.5.2] - 2026-04-17 (Python only — interim fix)

This is a tactical patch. The proper architectural fix — versioned optimistic concurrency via the existing `version` field, symmetric across Python and TypeScript SDKs — is tracked in [#26](https://github.com/NimbleBrainInc/upjack/issues/26) and will ship as 0.6.0.

### Fixed
- `update_entity` and `delete_entity` now serialize concurrent access via an advisory `flock` on a sidecar `.lock` file. Previously, two tool calls targeting the same entity in parallel (e.g. an agent invoking `update_deal` and `move_deal_stage` on the same deal) would each read the same pre-state, compute their update, and write sequentially — silently clobbering the other's fields. Observed in production as tool responses returning wrong `previous_stage` values. The final on-disk state was usually consistent (last writer wins), but the intermediate responses lied.

### Added
- `EntityLockTimeout` (exported from `upjack.entity`) — raised if a lock cannot be acquired within 30 seconds. Guards against a stuck-but-alive writer wedging the whole tool server.
- Lock is reentrant on the same thread (thread-local tracking of held paths) so future callers that nest `update_entity` from within another locked section don't deadlock.

### Known limitations
- **Windows**: `fcntl` is unavailable, so the lock is a no-op there. Concurrent updates remain unsafe on Windows, but no worse than 0.5.1.
- **TypeScript SDK**: unchanged at 0.5.1 — the analogous race is latent (Node's sync I/O accidentally serializes today) but not fixed by design. Resolved together with Python in 0.6.0 via the versioned-CAS design in [#26](https://github.com/NimbleBrainInc/upjack/issues/26).
- **Cross-machine / networked filesystems**: flock semantics on NFS and similar are implementation-defined. 0.6.0's CAS approach does not have this caveat.

## [0.5.1] - 2026-04-16

Applies to both the Python and TypeScript libraries. The tool contract is now identical across both SDKs.

The 0.5.0 version number was burned by an earlier TypeScript-only release (npm `upjack@0.5.0`) that bumped the version without applying the flat-kwarg contract change described below. To keep the "same version = same contract" invariant across SDKs, the corrected release ships as 0.5.1. `upjack@0.5.0` on npm has been deprecated; please upgrade to 0.5.1.

### Changed
- **Breaking:** Auto-generated `create_{name}` and `update_{name}` MCP tools now take flat kwargs at the top level. The `{data: {...}}` wrapper has been removed — pass entity fields directly, e.g. `create_deal({"title": "...", "amount": 1000, "stage": "qualified"})`. Mixing the old and new shapes in the same tool list was measurably confusing LLMs and driving ~30% tool-call failure rates on the auto-generated CRUD surface. The flat form matches the hand-written tool convention and the FastMCP / MCP SDK idiom.
- **Breaking (TypeScript only):** `get_{name}`, `update_{name}`, and `delete_{name}` tools now take an entity-specific id parameter (e.g. `contact_id`, `deal_id`) instead of the generic `entity_id`. This matches the Python library and the existing relationship-tool convention.
- `get_{name}`, `update_{name}`, and `delete_{name}` tool schemas now include a JSON Schema `examples` field with a minimal valid call so LLMs have an in-context anchor for the correct shape. Author-supplied `examples` on the entity schema are passed through verbatim for `create_{name}` (base entity fields stripped so framework-managed values don't leak into tool examples).

### Fixed
- `tools/list` no longer forces a network fetch of `https://upjack.dev/schemas/v1/upjack-entity.schema.json` when activities or any `allOf + $ref` schema is in play. The base-entity `$ref` is now inlined at schema-load time (`load_schema` / `loadSchema`). This eliminates a ~4-second-per-call penalty that hit every activity-enabled app.

### Added
- `upjack.schema.BASE_ENTITY_REF` (Python and TypeScript) — the canonical `$id` / `$ref` URL for the bundled base entity schema, exported for consumers that want to recognise or rewrite it. The inlining itself is performed automatically by `load_schema` / `loadSchema` and is not part of the public API.
- `upjack.schema.BASE_ENTITY_MARKER` (TypeScript only) — the non-standard key (`x-upjack-base-entity: true`) attached to the inlined base-entity schema so downstream code can identify it without the `$id` that would otherwise conflict with AJV's pre-registered copy.

## [0.3.1] - 2026-03-27

### Fixed
- `create_entity` no longer generates a filename ULID that differs from the `id` in the JSON content when data includes an `id` field
- Provided IDs are now respected when valid for the entity's prefix (enables deterministic seeding with cross-references)
- Duplicate ID detection — `create_entity` raises `ValueError` if an entity with that ID already exists
- `type` field in data no longer leaks into the record via `update()` — `entity_type` parameter always wins
- Seed tool now passes `id` through to `create_entity` so seed data can use stable IDs

## [0.3.0] - 2026-03-27

### Changed
- **Breaking:** CRUD tools use entity-specific parameter names (`contact_id`, `deal_id`) instead of generic `entity_id`
- **Breaking:** `list_*` and `search_*` tools return `{entities: [...], count, ...}` envelope instead of bare arrays
- **Breaking:** `query_*_by_relationship` and `get_related_*` tools return the same envelope format
- All entity-derived tools declare `outputSchema` and return `structuredContent` (MCP spec 2025-06-18)
- Added `build_entity_output_schema()` and `build_list_output_schema()` helpers to `upjack.schema`
- Internal: `_wrap_list()` helper for consistent response envelope construction

## [0.2.0] - 2026-03-26

### Added
- Schema evolution: hydrate-on-read migration, `validate_schema_change()` guard, `add_field` MCP tool, required-without-default warning
- Relationship indexing: write-time reverse index at `_index/relations.json`, auto-rebuild from entity files, atomic writes
- Graph traversal methods on UpjackApp: `query_by_relationship`, `get_related`, `get_composite`
- Activity tracking: opt-in via `"activities": true` in manifest, `log_activity` and `get_activities` methods
- Per-entity MCP tools: `query_{plural}_by_relationship`, `get_related_{name}`, `get_{name}_composite`
- Global MCP tools: `rebuild_index`, `log_activity`, `get_activities` (when activities enabled)
- CRUD hooks: `on_relationships_changed` callback for automatic index maintenance

## [0.1.0] - 2026-02-24

### Added
- Upjack Framework specification (v0.1 Draft)
- `upjack` Python library (PyPI) — entity CRUD, search, schema validation, MCP server auto-generation via FastMCP
- `upjack` TypeScript library (npm) — identical API, Node 18+, MCP server via @modelcontextprotocol/sdk
- `upjack init` CLI for scaffolding new apps (Python and TypeScript)
- JSON Schema definitions (upjack-entity, upjack-manifest, upjack-app)
- Schema bundling and validation tooling
- CRM example app (5 entity types, 3 bundled skills, schedules, hooks, views)
- Todo List example app (3 entity types, hooks, schedules, views)
- Research Assistant example app (4 entity types, schedule)
- Documentation website (Astro/Starlight)
