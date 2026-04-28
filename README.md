[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/nimblebraininc-upjack-badge.png)](https://mseep.ai/app/nimblebraininc-upjack)

<p align="center">
  <img src="website/public/readme-banner.png" alt="Upjack — Declarative AI-native apps. Kill your boilerplate." width="100%" />
</p>

[![CI](https://github.com/NimbleBrainInc/upjack/actions/workflows/ci.yml/badge.svg)](https://github.com/NimbleBrainInc/upjack/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/upjack)](https://pypi.org/project/upjack/)
[![npm](https://img.shields.io/npm/v/upjack)](https://www.npmjs.com/package/upjack)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-%E2%89%A53.13-blue.svg)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/node-%E2%89%A518-green.svg)](https://nodejs.org/)
[![Status](https://img.shields.io/badge/status-beta-yellow.svg)]()

**Build AI-powered apps by describing your domain, not writing code.**

Write a JSON Schema for your data. Write Markdown for your domain expertise. Get entity management, validation, search, and a complete [MCP](https://modelcontextprotocol.io) server, automatically.

**No API code. No database. No deployment config.**

## What You Get

Define an entity schema and a skill in Markdown. Upjack gives you:

- **6 MCP tools per entity**: `create_<entity>`, `get_<entity>`, `update_<entity>`, `list_<entities>`, `search_<entities>`, `delete_<entity>`
- **Schema validation** on every write. Invalid data never hits storage.
- **Type-prefixed IDs** like `tk_01HZ3QKB...` so you know the type at a glance
- **Full-text search** across all string fields
- **JSON file storage** in a git-friendly directory structure
- **Skills as resources**: your Markdown expertise files are served to the agent via `upjack://skills/*`

Define a task tracker, a CRM, a research notebook, an inventory system — any domain. Your AI agent gets full CRUD, search, and domain expertise from just two files.

## Prerequisites

You don't need deep knowledge of these to get started, but they're helpful context:

| Concept | What It Is | Learn More |
|---------|-----------|------------|
| [JSON Schema](https://json-schema.org/learn) | A standard for describing the shape of JSON data. Upjack uses it to define what each entity looks like. | [Getting Started](https://json-schema.org/learn/getting-started-step-by-step) |
| [MCP](https://modelcontextprotocol.io) | Model Context Protocol — a standard that lets AI agents call tools and read resources. Upjack can expose your app as an MCP server so agents can interact with it. | [Introduction](https://modelcontextprotocol.io/introduction) |
| [MCPB](https://github.com/modelcontextprotocol/mcpb) | MCP Bundle — a packaging format for distributing MCP servers. Upjack apps use the MCPB manifest format, with upjack-specific config in a `_meta` extension field. | [Spec](https://github.com/modelcontextprotocol/mcpb) |
| [ULID](https://github.com/ulid/spec) | Universally Unique Lexicographically Sortable Identifier — like a UUID but sortable by creation time. Upjack uses prefixed ULIDs as entity IDs (e.g., `ct_01HZ3QKB...`). | [Spec](https://github.com/ulid/spec) |
| CRUD | Create, Read, Update, Delete — the four basic data operations. Upjack auto-generates these for every entity type. | — |
| stdio | Standard input/output — a way for programs to communicate by reading from stdin and writing to stdout. MCP servers use stdio so any MCP client can connect to them. | — |
| [FastMCP](https://github.com/jlowin/fastmcp) | A Python library that makes it easy to build MCP servers. Upjack uses it internally to generate your MCP tools. Install via `upjack[mcp]`. | [Docs](https://gofastmcp.com) |
| `allOf` | A JSON Schema keyword that combines multiple schemas. Upjack uses it to layer your app-specific fields on top of the base entity schema (which provides `id`, `status`, `created_at`, etc.). | [JSON Schema docs](https://json-schema.org/understanding-json-schema/reference/combining#allof) |

## Quick Start

Two ways to get started. The fast way lets your AI agent build the app for you. The manual way gives you full control.

### The Fast Way: Let Your Agent Build It

Install the [Upjack App Builder](https://mpak.dev/skills/@nimblebraininc/upjack-app-builder) skill, describe what you want, and your agent generates a complete app.

**Prerequisites:** [Node.js](https://nodejs.org/) v18+

**1. Install the skill**

```bash
npx @nimblebrain/mpak skill install @nimblebraininc/upjack-app-builder
```

**2. Tell your agent what you want**

```
claude > Build me a CRM app
```

The agent generates a complete, ready-to-run app:

```
my-crm/
  manifest.json               # Wiring: entities, skills, hooks, schedules
  schemas/
    contact.schema.json        # Entity definitions (JSON Schema)
    company.schema.json
    deal.schema.json
  skills/
    lead-qualification/
      SKILL.md                 # Domain expertise the agent reads
  context.md                   # Background knowledge
  seed/
    sample-contacts.json       # Initial data
  server.py                    # MCP server entry point
```

**3. Run it**

```bash
cd my-crm
uv sync && python server.py        # Python
# or: npm install && npx tsx server.ts   # TypeScript
```

Done. Your agent now has tools like `create_contact`, `list_contacts`, and `search_contacts`, plus resources for your domain knowledge and skills.

---

### The Manual Way: Build It Yourself

If you prefer to understand every file and wire things up by hand.

#### 1. Install

> **Python 3.13+ required.** Check your version: `python --version`

```bash
# Python
pip install upjack              # or: uv add upjack
pip install "upjack[mcp]"       # with MCP server support

# TypeScript (Node.js >= 18)
npm install upjack
```

#### 2. Try an example

```bash
git clone https://github.com/NimbleBrainInc/upjack.git
cd upjack
pip install "upjack[mcp]"
python examples/todo/server.py    # or: npx tsx examples/todo/server.ts
```

> The server communicates over stdio — no visible output. It's ready when the terminal is waiting for input. Ctrl+C to stop.

Connect it to **Claude Code**, **Claude Desktop**, **Cursor**, or **Codex**. See the [Todo README](examples/todo/README.md#3-connect-to-your-editor) for copy-paste configs.

All three examples ([Todo](examples/todo/), [CRM](examples/crm/), [Research Assistant](examples/research-assistant/)) work the same way.

#### 3. Scaffold your own app

```bash
upjack init
# prompts: App name? → my-crm | First entity? → contact
```

Creates a ready-to-run app directory:

```
my-crm/
  manifest.json               # Wiring: entities, skills, hooks, schedules
  schemas/
    contact.schema.json        # What a contact looks like (JSON Schema)
  context.md                   # Domain knowledge the agent always has
  seed/
    sample-contacts.json       # Initial data
  server.py                    # 3-line MCP server entry point (Python)
  server.ts                    # 3-line MCP server entry point (TypeScript)
```

#### 4. Create a manifest

`manifest.json` follows the [MCPB](https://github.com/modelcontextprotocol/mcpb) package format. Upjack-specific config lives in `_meta["ai.nimblebrain/upjack"]`:

```json
{
  "manifest_version": "0.4",
  "name": "my-notes-app",
  "version": "0.1.0",
  "title": "Notes",
  "server": null,
  "_meta": {
    "ai.nimblebrain/upjack": {
      "upjack_version": "0.1",
      "namespace": "apps/notes",
      "entities": [
        {
          "name": "note",
          "plural": "notes",
          "prefix": "nt",
          "schema": "schemas/note.schema.json"
        }
      ]
    }
  }
}
```

The `namespace` determines where entity files are stored. The `prefix` is prepended to generated IDs (`nt_01HZ3QKB...`).

#### 5. Create an entity schema

Create `schemas/note.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "title": { "type": "string" },
    "body": { "type": "string" },
    "tags": { "type": "array", "items": { "type": "string" } }
  },
  "required": ["title"]
}
```

#### 6. Use it (Python)

```python
from upjack import UpjackApp

app = UpjackApp.from_manifest("manifest.json")

note = app.create_entity("note", {"title": "Hello", "body": "My first note"})
print(note["id"])    # nt_01HZ3QKB9YWVJ0RPFA7MT8C5X

notes = app.list_entities("note")
results = app.search_entities("note", query="hello")
app.update_entity("note", note["id"], {"body": "Updated body"})
app.delete_entity("note", note["id"])    # soft delete
```

Invalid data never reaches storage:

```python
app.create_entity("note", {"body": "No title"})
# jsonschema.ValidationError: 'title' is a required property
```

#### 7. Use it (TypeScript)

```typescript
import { UpjackApp } from "upjack";

const app = UpjackApp.fromManifest("manifest.json");

const note = app.createEntity("note", { title: "Hello", body: "My first note" });
console.log(note.id);    // nt_01HZ3QKB9YWVJ0RPFA7MT8C5X

const notes = app.listEntities("note");
const results = app.searchEntities("note", { query: "hello" });
app.updateEntity("note", note.id, { body: "Updated body" });
app.deleteEntity("note", note.id);    // soft delete
```

#### 8. Serve as an MCP server

**Python:**

```python
from upjack.server import create_server
mcp = create_server("manifest.json")
mcp.run()
# Tools: create_note, get_note, update_note, list_notes, search_notes, delete_note
```

**TypeScript:**

```typescript
import { startServer } from "upjack/server";
startServer("manifest.json");
```

#### 9. Connect to your agent

The server communicates over stdio. Point any MCP-compatible client at your server:

**Claude Code:**

```bash
claude mcp add my-notes-app -- python /path/to/my-notes-app/server.py
```

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "my-notes-app": {
      "command": "python",
      "args": ["/path/to/my-notes-app/server.py"]
    }
  }
}
```

**Cursor** (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "my-notes-app": {
      "command": "python",
      "args": ["/path/to/my-notes-app/server.py"]
    }
  }
}
```

**Codex:**

```bash
codex --mcp-config '{"mcpServers":{"my-notes-app":{"command":"python","args":["/path/to/my-notes-app/server.py"]}}}'
```

> For TypeScript, replace `python` / `server.py` with `npx tsx` / `server.ts`.

The agent sees tools like `create_note`, `list_notes`, `search_notes`, and resources like `upjack://context` and `upjack://skills/*`.

> **Publishing**: Upjack apps are [MCPB](https://github.com/modelcontextprotocol/mcpb) bundles. Use [mpak](https://mpak.dev) to package and distribute them (`npx @nimblebrain/mpak run @yourorg/my-notes-app`).

## How It Works

```
  You write:                    Upjack generates:

  ┌─────────────────┐           ┌─────────────────────────────┐
  │ schemas/        │           │  MCP Tools                  │
  │  contact.json   │──────────▶│  create_contact             │
  │  deal.json      │           │  get_contact, list_contacts │
  └─────────────────┘           │  update_contact             │
                                │  search_contacts            │
  ┌─────────────────┐           │  delete_contact             │
  │ skills/         │──────────▶│  ... (× every entity type)  │
  │  lead-qual.md   │           ├─────────────────────────────┤
  └─────────────────┘           │  MCP Resources              │
                                │  upjack://context           │
  ┌─────────────────┐           │  upjack://skills/*          │
  │ manifest.json   │──────────▶├─────────────────────────────┤
  │  entities       │           │  Storage & Validation       │
  │  hooks          │           │  JSON files + JSON Schema   │
  │  schedules      │           │  Prefixed ULID IDs          │
  └─────────────────┘           └─────────────────────────────┘
```

## Three Tiers

| Tier | What You Write | What upjack Provides |
|------|---------------|---------------------------|
| **Schemas + Skills** | JSON Schema + Markdown | Entity management, storage, validation |
| **MCP Server** | `create_server()` / `createServer()` | Full MCP server with CRUD tools, resources |
| **Custom Server** | Python/TypeScript MCP server + custom logic | Entity management + your custom tools |

Most apps never leave Tier 1.

## Example: CRM App

The [`examples/crm/`](examples/crm/) directory contains a complete CRM with:

- **5 entity types**: contact, company, deal, pipeline (singleton), activity
- **3 bundled skills**: lead qualification (scoring rubric), deal forecasting, follow-up emails
- **3 schedules**: daily pipeline review, weekly stale deal alert, nightly lead scoring
- **2 hooks**: auto-score new contacts, trigger forecast on closed deals
- **3 swappable dependencies**: email (SES/SendGrid/Resend), enrichment (Clearbit/Apollo), PDF generation

See also [`examples/todo/`](examples/todo/) for a mid-complexity example and [`examples/research-assistant/`](examples/research-assistant/) for a minimal example.

## Key Concepts

**Entity**: A typed data record with a [JSON Schema](https://json-schema.org). Every entity gets a type-prefixed [ULID](https://github.com/ulid/spec) (`ct_01HZ3QKB...` for contacts, `dl_01HZ4RMN...` for deals). Stored as individual JSON files. Validated at write time.

**Skill**: A Markdown document encoding domain expertise: scoring rubrics, decision criteria, procedures. The AI agent reads skills and applies them through reasoning.

**Manifest**: A JSON declaration that wires entities to skills, defines hooks (react to data changes), schedules (cron triggers), views (named queries), and bundle dependencies (external tools declared by capability alias, not package name).

**Bundle Dependency**: An external tool provider declared by alias (e.g., `email`) with a compatibility contract (`tools_used` array). Swap the underlying package without touching skills or schemas.

## Documentation

Full documentation is available at **[upjack.dev](https://upjack.dev)**.

| Topic | Link |
|-------|------|
| Thesis | [Why AI-native apps need a new framework](https://upjack.dev/concepts/thesis/) |
| Architecture | [Design philosophy, three tiers](https://upjack.dev/concepts/architecture/) |
| Manifest Reference | [Full manifest format](https://upjack.dev/reference/manifest/) |
| Schemas | [Published JSON Schemas and validation](https://upjack.dev/reference/schemas/) |
| Entity Model | [Base entity schema, IDs, storage, lifecycle](https://upjack.dev/reference/entity-model/) |
| Bundles & Skills | [Dependencies and skill references](https://upjack.dev/reference/bundles-and-skills/) |
| Runtime Tools | [The 6 entity management tools](https://upjack.dev/reference/runtime-tools/) |
| Lifecycle | [Install, update, uninstall, migration](https://upjack.dev/reference/lifecycle/) |
| Tutorial | [Build a Todo App in 5 Minutes](https://upjack.dev/tutorials/todo-app/) |

## Structure

```
schemas/        JSON Schemas (upjack-manifest, upjack-entity)
lib/python/     upjack Python library (entity management + MCP server factory)
lib/typescript/ upjack TypeScript library (same API, Node 18+)
examples/       Reference apps (CRM, Todo, Research Assistant)
website/        Documentation site (upjack.dev)
```

## Packaging

Upjack apps are standard [MCPB](https://github.com/modelcontextprotocol/mcpb) packages. The upjack-specific metadata lives in `_meta["ai.nimblebrain/upjack"]`, which MCPB treats as opaque vendor metadata. Non-MCPB-aware tools can install an Upjack app as a regular MCP server and ignore the extension.

## Getting Help

- **Bug reports and feature requests**: [GitHub Issues](https://github.com/NimbleBrainInc/upjack/issues)
- **Questions and discussions**: [GitHub Discussions](https://github.com/NimbleBrainInc/upjack/discussions)
- **Contributing**: See [CONTRIBUTING.md](CONTRIBUTING.md)

## License

Apache 2.0
