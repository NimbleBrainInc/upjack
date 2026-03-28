---
name: upjack-app-builder
description: Builds complete, compliant NimbleBrain Upjack apps from natural language descriptions. Generates manifest, entity schemas, skills, context, seed data, and server entry point. Use when creating a new Upjack app, building an AI-native app, or scaffolding a domain-specific application. Triggers include "create me a todo app", "build an upjack app", "new upjack app for", "scaffold an app".
metadata:
  version: "0.3.1"
  category: development
  tags:
    - upjack
    - app-builder
    - scaffolding
    - ai-native
    - mcp
  triggers:
    - create me a
    - build an upjack app
    - new upjack app
    - scaffold an app
    - make me an app
    - upjack app for
  surfaces:
    - claude-code
  author:
    name: NimbleBrain
    url: https://www.nimblebrain.ai
---

# Upjack App Builder

Generate complete, spec-compliant NimbleBrain Upjack apps from a plain English description. The user says "create me a todo app" and you produce every file needed for a working Upjack app.

## Quick Start

**User says:** "Create me a todo app"

**You produce:**

```
todo/
├── manifest.json
├── README.md
├── schemas/
│   ├── task.schema.json
│   ├── project.schema.json
│   └── label.schema.json
├── skills/
│   └── task-management/
│       └── SKILL.md
├── context.md
├── seed/
│   └── sample-tasks.json
└── server.py
```

## References

Read these before generating. They are the source of truth. All paths are relative to the Upjack repo root.

- **Upjack spec**: `docs/SPEC.md`
- **Entity model**: `docs/ENTITY_MODEL.md`
- **Manifest spec**: `docs/UPJACK_MANIFEST.md`
- **Manifest schema**: `schemas/v1/upjack-manifest.schema.json`
- **Entity base schema**: `schemas/v1/upjack-entity.schema.json`
- **CRM example**: `examples/crm/`
- **Research example**: `examples/research-assistant/`
- **Library source**: `lib/src/upjack/`

## Process

### Phase 1: Understand the Request

Extract from the user's description:

1. **App domain**: What problem space? (productivity, finance, content, operations, etc.)
2. **Core entities**: What things does the user manage? (tasks, projects, invoices, articles)
3. **Behaviors**: What should the agent do automatically? (prioritize, categorize, alert, summarize)
4. **Relationships**: How do entities connect? (tasks belong to projects, invoices have line items)
5. **Target location**: Where to create files. Default: `examples/{app-name}/`

If the request is ambiguous, ask ONE round of clarifying questions. Keep it tight — propose a default and ask if they want changes:

```
I'll build a todo app with these entities:
- task (the core item — title, description, priority, due date)
- project (groups tasks)
- label (categorization tags)

One skill: task-management (prioritization, overdue detection, daily planning).
Sound right, or should I adjust?
```

### Phase 2: Design the Domain Model

#### Entity Design Rules

| Rule | Detail |
|------|--------|
| **Naming** | Lowercase, underscores allowed. Pattern: `^[a-z][a-z0-9_]*$` |
| **Prefix** | 2-4 lowercase chars, unique per app. Mnemonic (task=tsk, project=prj) |
| **Plural** | Required unless singleton. Used for directory names and tool names |
| **Singleton** | Use for config-like entities (one record total). Omit `plural` |
| **Relationships** | Use the `relationships` array on entities, not foreign key fields |
| **Denormalization** | OK to denormalize frequently-accessed fields (e.g., `project_name` on task) |

#### Prefix Assignment

Choose short, mnemonic, non-colliding prefixes:

```
task    → tsk     contact  → ct      invoice  → inv
project → prj     company  → co      payment  → pmt
label   → lbl     deal     → dl      article  → art
note    → nt      topic    → top     recipe   → rcp
report  → rpt     source   → src     event    → evt
```

#### Category Selection

Pick from the allowed manifest categories:

| Category | Use for |
|----------|---------|
| `sales` | CRM, pipeline, deals |
| `marketing` | Content, campaigns, social |
| `operations` | Tasks, workflows, inventory |
| `research` | Knowledge, notes, analysis |
| `finance` | Invoices, expenses, budgets |
| `hr` | People, hiring, reviews |
| `engineering` | Bugs, sprints, releases |
| `support` | Tickets, knowledge base |
| `custom` | Anything else |

### Phase 3: Generate Files

Generate ALL files in a single pass. Every file must be complete and valid.

#### 3a. Entity Schemas (`schemas/{entity}.schema.json`)

Template — adapt properties per entity:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "{App} {Entity}",
  "description": "{What this entity represents}",
  "allOf": [
    { "$ref": "https://upjack.dev/schemas/v1/upjack-entity.schema.json" }
  ],
  "properties": {
    "field_name": {
      "type": "string",
      "description": "What this field represents"
    }
  },
  "required": ["field_name"]
}
```

**Schema rules:**
- Always use `"$schema": "https://json-schema.org/draft/2020-12/schema"`
- Always compose with base via `allOf` referencing `https://upjack.dev/schemas/v1/upjack-entity.schema.json`
- Every property needs a `description`
- Use appropriate JSON Schema types and formats:
  - `"format": "email"` for emails
  - `"format": "uri"` for URLs
  - `"format": "date-time"` for timestamps
  - `"format": "date"` for dates
  - `"enum": [...]` for fixed value sets
  - `"minimum"` / `"maximum"` for bounded numbers
  - `"pattern"` for string constraints
- Keep `required` minimal — only fields essential for the entity to make sense
- Do NOT redefine base entity fields (`id`, `type`, `version`, `created_at`, `updated_at`, `status`, `tags`, `relationships`, `source`, `created_by`) — those come from the base schema via `allOf`
- Do NOT set `"additionalProperties": false` — the base schema sets `"additionalProperties": true` to allow app fields

**Property design guidance by domain:**

| Domain | Common properties |
|--------|-------------------|
| Productivity | `title`, `description`, `priority` (enum), `due_date` (date), `completed_at` (date-time) |
| Finance | `amount` (number), `currency` (string, pattern `^[A-Z]{3}$`), `due_date`, `paid_at` |
| Content | `title`, `body` (string), `author`, `published_at` (date-time), `word_count` (integer) |
| People | `first_name`, `last_name`, `email` (format: email), `role`, `phone` |
| Inventory | `name`, `sku`, `quantity` (integer, minimum: 0), `unit_price` (number), `location` |

#### 3b. Manifest (`manifest.json`)

```json
{
  "manifest_version": "0.4",
  "name": "@nimblebraininc/{app-name}",
  "version": "1.0.0",
  "title": "{Human-Readable App Title}",
  "description": "{One-line description of what the app does}",
  "server": {
    "type": "python",
    "entry_point": "server",
    "mcp_config": {
      "command": "python",
      "args": ["server.py"]
    }
  },
  "_meta": {
    "ai.nimblebrain/upjack": {
      "upjack_version": "0.1",
      "namespace": "apps/{app-name}",
      "display": {
        "name": "{Display Name}",
        "icon": "{emoji}",
        "category": "{category}"
      },
      "entities": [
        {
          "name": "{entity_name}",
          "plural": "{entity_names}",
          "schema": "schemas/{entity_name}.schema.json",
          "prefix": "{xx}",
          "index": true
        }
      ],
      "skills": [
        {
          "source": "bundled",
          "path": "skills/{skill-name}/SKILL.md"
        }
      ],
      "context": "context.md",
      "seed": {
        "data": "seed/",
        "run_on_install": true
      }
    }
  }
}
```

**Manifest rules:**
- `manifest_version` is always `"0.4"`
- `upjack_version` is always `"0.1"`
- `namespace` pattern: `apps/{app-name}` (lowercase, hyphens OK)
- `name` pattern: `@nimblebraininc/{app-name}`
- Every entity needs: `name`, `schema`, `prefix`. Add `plural` unless singleton
- Singleton entities: set `"singleton": true`, omit `plural`
- `index: true` is default for searchable entities. Set `false` for high-volume log-like entities

**Optional manifest sections** — include when appropriate:

**Schedules** (for recurring agent tasks):
```json
"schedules": [
  {
    "name": "daily-review",
    "cron": "0 9 * * 1-5",
    "skill": "bundled:{skill-name}",
    "description": "What this schedule does"
  }
]
```

**Hooks** (for reactive behaviors):
```json
"hooks": [
  {
    "event": "entity.created",
    "entity": "{entity_name}",
    "skill": "bundled:{skill-name}"
  }
]
```
Hook events: `entity.created`, `entity.updated`, `entity.deleted`, `entity.status_changed`, `app.installed`, `app.updated`

**Views** (for named filtered queries):
```json
"views": [
  {
    "name": "overdue-tasks",
    "entity": "task",
    "description": "Active tasks past their due date",
    "filter": "$.status == 'active'",
    "sort": "due_date"
  }
]
```

**Bundles** — only if the app genuinely needs external tools (email, enrichment, PDF). Most simple apps do NOT need bundles. Do not add bundles speculatively.

#### 3c. Skills (`skills/{skill-name}/SKILL.md`)

Every app gets at least one bundled skill encoding domain expertise. Skills are Markdown documents the agent reads and reasons over — they are NOT executable code.

```markdown
# {Skill Title}

{What this skill enables the agent to do.}

## When to Use

- {Trigger condition 1 — e.g., "A new task is created"}
- {Trigger condition 2 — e.g., "User asks to prioritize tasks"}
- {Trigger condition 3 — e.g., "Daily review schedule fires"}

## Process

1. **{Step name}**: {What to do}
   - {Detail}
   - {Detail}

2. **{Step name}**: {What to do}
   - {Detail}

## {Domain-Specific Section}

{Rubrics, scoring criteria, decision trees, procedures — whatever the domain needs.}

## Rules

- {Hard constraint 1}
- {Hard constraint 2}
- {Hard constraint 3}
```

**Skill design rules:**
- Write as instructions TO the agent, not documentation ABOUT the domain
- Be specific: scoring rubrics with numbers, decision criteria with thresholds
- Reference entity fields by name (e.g., "update the task's `priority` field")
- Reference relationships ("link the note to the topic via a `belongs_to` relationship")
- Include when-to-use triggers that map to hooks/schedules in the manifest
- One skill per behavioral concern (don't combine unrelated behaviors)

#### 3d. Context (`context.md`)

Domain knowledge the agent reads for background understanding. Shorter and more general than skills.

```markdown
# {App Name} Domain Knowledge

{Role statement: "You are managing a..." }

## Entity Relationships

- **{Entity A}** {relationship} **{Entity B}** via the `{rel_type}` relationship
- **{Entity C}** are linked to **{Entity A}** and/or **{Entity B}**

## {Domain Concept 1}

{Explanation of how this concept works in the domain.}

## {Domain Concept 2}

{Explanation.}

## Rules

- {Global rule 1}
- {Global rule 2}
```

**Context rules:**
- Describe entity relationships explicitly
- Explain domain concepts the agent needs to reason about
- Keep it under 50 lines — this is background knowledge, not a manual
- Reference entity and field names exactly as defined in schemas

#### 3e. Server Entry Point (`server.py`)

Always the same 5-line pattern:

```python
"""{ App title } MCP server built with upjack + FastMCP."""

from pathlib import Path

from upjack.server import create_server

manifest = Path(__file__).parent / "manifest.json"
mcp = create_server(manifest)

if __name__ == "__main__":
    mcp.run()
```

Do not add custom logic unless the user specifically asks for Tier 3 (custom server) features.

#### 3f. README (`README.md`)

Every example app gets a README. Follow the pattern in `examples/crm/README.md`.

```markdown
# {App Title} — Upjack Example App

{One sentence: what this app does and that it's built with Upjack.}

## What This Demonstrates

This example shows:

- **{N} entity types** with JSON Schema definitions and `allOf` composition
- {Feature bullet per notable feature: singletons, skills, hooks, schedules, views, bundles}
- **Seed data** ({brief description of what's seeded})

## Entity Types

| Entity | Prefix | Schema | Notes |
|--------|--------|--------|-------|
| {Name} | `{pfx}_` | [{name}.schema.json](schemas/{name}.schema.json) | {One-line description} |

## Skills

### [{Skill Title}](skills/{skill-name}/SKILL.md)

{2-3 sentence description of what the skill does and when it fires.}

## File Structure

```
{app-name}/
├── manifest.json
├── context.md
├── schemas/
│   └── {list each schema file}
├── skills/
│   └── {list each skill}
└── seed/
    └── {list each seed file}
```

## Running the Server

```bash
uv pip install upjack[mcp]
python server.py
```
```

**README rules:**
- Include entity table with prefix, schema link, and notes
- List every skill with a link and short description
- Include hooks/schedules/views tables if the app has them
- Include bundle dependency table if the app has them
- Show the file structure tree
- End with run instructions

#### 3g. Seed Data (`seed/{entity-plural}.json`)

Sample data so the app is immediately useful after install. JSON arrays of entity objects (without base fields — those are auto-generated).

```json
[
  {
    "type": "{entity_name}",
    "version": 1,
    "field_1": "value",
    "field_2": "value",
    "tags": ["sample"]
  }
]
```

**Seed data rules:**
- Include `type` and `version: 1` on every seed record
- Do NOT include `id`, `created_at`, `updated_at` — the runtime generates these
- Do NOT include `status` unless you want something other than `"active"` (the default)
- Include `tags: ["sample"]` so seed data is identifiable
- 2-5 records per entity type is sufficient
- Make seed data realistic and useful, not lorem ipsum
- For relationships, omit them in seed data (IDs aren't known yet)
- Name seed files by entity plural: `sample-tasks.json`, `sample-projects.json`

### Phase 4: Generate E2E Tests

Add a test class to `lib/tests/test_e2e.py` following the existing CRM and Research Assistant test patterns. The tests validate that the app's manifest, schemas, and seed data work correctly with the upjack library.

#### 4a. Add Example Directory Constant

At the top of `test_e2e.py`, alongside the existing constants:

```python
{APP_UPPER}_DIR = _CODE_ROOT / "examples" / "{app-name}"
```

#### 4b. UpjackApp-Level Tests (`Test{AppName}App`)

Test class with a fixture loading the manifest:

```python
class Test{AppName}App:
    """E2E tests using the real {App Name} manifest and schemas."""

    @pytest.fixture
    def app(self, tmp_path):
        return UpjackApp.from_manifest({APP_UPPER}_DIR / "manifest.json", root=tmp_path)
```

**Required test methods:**

| Test | What it validates |
|------|-------------------|
| `test_loads_all_entity_types` | Every entity defined in manifest is accessible |
| `test_create_{entity}_with_valid_data` | One per entity type — create with valid data, assert ID prefix and field values |
| `test_{entity}_requires_{field}` | One per required field — assert `ValidationError` when missing |
| `test_{entity}_{field}_bounded` | For numeric fields with min/max — assert `ValidationError` outside bounds |
| `test_{entity}_{field}_enum` | For enum fields — assert `ValidationError` for invalid values |
| `test_full_crud_cycle` | Create, read, update, search, list, delete on the primary entity |
| `test_multiple_entity_types_coexist` | Create one of each type, list each, verify counts |
| `test_search_with_structured_filter` | Create 2-3 entities with varying field values, filter with `$gte`/`$lte`, verify order |

#### 4c. Server-Level Tests (`Test{AppName}Server`)

```python
class Test{AppName}Server:
    """E2E tests for a server created from the {App Name} manifest."""

    @pytest.fixture
    def mcp(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        return create_server({APP_UPPER}_DIR / "manifest.json", root=workspace)
```

**Required test methods:**

| Test | What it validates |
|------|-------------------|
| `test_registers_all_{app}_tools` | 6 tools per entity (create, get, update, list, search, delete) + seed_data |
| `test_registers_context_and_skill_resources` | `upjack://context` + one `upjack://skills/{name}` per bundled skill |
| `test_create_{primary_entity}_through_tool` | Call create tool via MCP client, assert ID prefix |
| `test_seed_data_loads_{app}_samples` | Call seed_data tool, assert loaded count matches seed files, verify entities exist |
| `test_server_name_is_{app}` | `mcp.name` matches manifest display name |

#### 4d. Test Patterns

Use the existing helper functions at the top of `test_e2e.py` — do NOT redefine them:

```python
_run(coro)                    # asyncio.run wrapper
_list_tool_names(mcp)         # returns set[str] of tool names
_call_tool(mcp, name, args)   # calls tool, returns parsed JSON
_list_resource_uris(mcp)      # returns set[str] of resource URIs
```

**Test style rules:**
- Use `pytest.raises(ValidationError)` for schema validation failures
- Assert ID prefixes with `startswith("{prefix}_")`
- Use descriptive docstrings on non-obvious tests
- Keep test data minimal but realistic — match the seed data domain
- Tool name pattern: `create_{name}`, `get_{name}`, `update_{name}`, `list_{plural}`, `search_{plural}`, `delete_{name}`
- For singleton entities, omit `plural` from tool names (use `list_pipelines` etc. only if plural is defined)

### Phase 5: Validate

Run this checklist before delivering. Every item must pass.

```
UPJACK APP COMPLIANCE CHECKLIST
═══════════════════════════════════════════════════

Manifest
  □ manifest_version is "0.4"
  □ upjack_version is "0.1"
  □ namespace matches pattern ^apps/[a-z][a-z0-9-]*$
  □ Every entity has: name, schema, prefix
  □ Every non-singleton entity has: plural
  □ All prefixes are 2-4 lowercase chars and unique
  □ All schema paths point to files that exist
  □ All skill paths point to files that exist
  □ category is one of: sales, marketing, operations, research,
    finance, hr, engineering, support, custom

Schemas
  □ Every schema has $schema draft 2020-12
  □ Every schema uses allOf with base entity $ref
  □ Every property has a description
  □ required array only contains app-specific fields
  □ No base fields redefined (id, type, version, etc.)
  □ No additionalProperties: false

Skills
  □ At least one bundled skill exists
  □ Every skill has: When to Use, Process, Rules sections
  □ Skills reference entity fields by their schema names
  □ Hook/schedule triggers in manifest match skill triggers

Context
  □ context.md exists
  □ Documents entity relationships
  □ References entity and field names correctly

Server
  □ server.py uses create_server() pattern
  □ No custom logic (unless Tier 3 requested)

README
  □ README.md exists
  □ Entity table with prefix, schema link, notes
  □ Skills listed with links and descriptions
  □ File structure tree included
  □ Run instructions included

Seed
  □ Every seed record has type and version: 1
  □ No id, created_at, or updated_at in seed records
  □ Realistic sample data (not lorem ipsum)

E2E Tests (in lib/tests/test_e2e.py)
  □ Directory constant added at top of file
  □ Test{AppName}App class with fixture loading manifest
  □ test_loads_all_entity_types covers every entity
  □ At least one create test per entity type
  □ At least one required-field validation test per entity
  □ test_full_crud_cycle on primary entity
  □ Test{AppName}Server class with fixture
  □ test_registers_all_{app}_tools checks tool count
  □ test_seed_data_loads_{app}_samples verifies seed
  □ Uses existing helper functions (not redefined)
```

### Phase 6: Deliver

Write all files using the Write tool. Present a summary:

```
Created {app-name} Upjack app at {path}/

Entities:
  - {entity} ({prefix}) — {description}
  - {entity} ({prefix}) — {description}

Skills:
  - {skill-name} — {what it does}

Files created:
  manifest.json
  README.md
  schemas/{entity}.schema.json (x{N})
  skills/{skill-name}/SKILL.md (x{N})
  context.md
  seed/{file}.json (x{N})
  server.py

Tests added to lib/tests/test_e2e.py:
  Test{AppName}App — {N} tests (CRUD, validation, search)
  Test{AppName}Server — {N} tests (tools, resources, seed)

To run: cd {path} && python server.py
To test: cd lib && make test
```

## Examples

### Example 1: Todo App

**User:** "Create me a todo app"

**Entities:**
- `task` (tsk) — A todo item with title, description, priority, due date
- `project` (prj) — Groups related tasks
- `label` (lbl) — Categorization tags that can be applied to tasks

**Skill:** `task-management` — Prioritization, overdue detection, daily planning, project progress tracking

**Views:** `overdue-tasks`, `today`, `high-priority`

**Hooks:** Auto-prioritize new tasks on `entity.created`

### Example 2: Recipe Book

**User:** "Build me a recipe management app"

**Entities:**
- `recipe` (rcp) — A recipe with title, ingredients, instructions, prep/cook time
- `ingredient` (ing) — An ingredient with name, category, unit
- `meal_plan` (mp) — A planned meal for a date, linking to recipes
- `collection` (col) — A named collection of recipes (e.g., "weeknight dinners")

**Skill:** `meal-planning` — Weekly meal planning, grocery list generation, nutrition awareness, seasonal suggestions

**Views:** `quick-meals` (under 30 min), `this-week` (current meal plan)

### Example 3: Bug Tracker

**User:** "Create a bug tracking app"

**Entities:**
- `bug` (bug) — A bug report with title, description, severity, steps to reproduce
- `release` (rel) — A software release version
- `component` (cmp) — A software component that can have bugs

**Skill:** `triage` — Severity assessment, duplicate detection, assignment suggestions, release planning

**Hooks:** Auto-triage new bugs on `entity.created`

**Views:** `critical-bugs`, `unresolved`, `by-component`

## Anti-Patterns

| Anti-pattern | Why it's bad | Instead |
|--------------|-------------|---------|
| Adding bundles speculatively | Adds unused dependencies | Only add bundles when the app genuinely needs external tools |
| Foreign key fields instead of relationships | Bypasses the relationship system | Use the `relationships` array with `rel` and `target` |
| Redefining base entity fields | Conflicts with schema composition | Let `allOf` inherit id, type, version, etc. from base |
| Giant monolith skill | Hard for agent to reason over | One skill per behavioral concern |
| Generic seed data | Useless for understanding the app | Make seed data realistic and domain-appropriate |
| Setting additionalProperties: false | Breaks allOf composition with base schema | Omit it entirely — base schema allows additional properties |
| Custom server logic by default | Unnecessary complexity for most apps | Use Tier 1/2 (create_server) unless Tier 3 is specifically needed |
| Over-engineering entities | Complexity without value | Start with 2-5 entities; the user can add more later |
