# Changelog

All notable changes to this project will be documented in this file.

This project follows [Keep a Changelog](https://keepachangelog.com/).

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
