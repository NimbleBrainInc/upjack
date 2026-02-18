# Todo List: Upjack Example App

A personal todo list and project tracker built with the Upjack framework. Near-zero code: just schemas, skills, a manifest, and a 3-line server entry point.

## What This Demonstrates

A mid-complexity Upjack app between the minimal Research Assistant and the full-featured CRM:

- **3 entity types** with JSON Schema definitions and `allOf` composition
- **1 bundled skill** (task management with prioritization rubric)
- **1 hook**: auto-assess new tasks on creation
- **1 schedule**: weekday morning daily review (9 AM)
- **3 views**: overdue tasks, today's tasks, high-priority tasks
- **Seed data**: sample tasks, projects, and labels

## Entities

| Entity | Prefix | Purpose |
|--------|--------|---------|
| **Task** | `tsk_` | Todo items with priority, effort, due date |
| **Project** | `prj_` | Project containers for grouping tasks |
| **Label** | `lbl_` | Categories for cross-project tagging |

## Running Locally

### Prerequisites

- Python >= 3.13 and [uv](https://docs.astral.sh/uv/), **or** Node.js >= 18
- Git

### 1. Clone and install

```bash
git clone https://github.com/NimbleBrainInc/upjack.git
cd upjack
```

**Python:**

```bash
cd lib/python
uv pip install -e ".[mcp]"
```

**TypeScript:**

```bash
cd lib/typescript
npm install && npm run build
```

### 2. Run the server

```bash
cd examples/todo
```

**Python:**

```bash
python server.py
```

**TypeScript:**

```bash
npx tsx server.ts
```

> TypeScript examples use `npx tsx` to run `.ts` files directly. Running with `node` requires Node 22+.

The server communicates over stdio, so there's no visible output. It's ready when the terminal is waiting for input. Press Ctrl+C to stop.

It exposes 18 tools (6 per entity type: `create_task`, `get_task`, `update_task`, `list_tasks`, `search_tasks`, `delete_task`, plus the same for projects and labels) and a `seed_data` tool to load sample data.

### 3. Connect to your editor

The server communicates over stdio, so you can connect it to any MCP-compatible client.

**Claude Desktop**: add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "todo": {
      "command": "python",
      "args": ["/absolute/path/to/upjack/examples/todo/server.py"]
    }
  }
}
```

**Claude Code:**

```bash
claude mcp add todo -- python /absolute/path/to/upjack/examples/todo/server.py
```

**Cursor**: add to `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "todo": {
      "command": "python",
      "args": ["/absolute/path/to/upjack/examples/todo/server.py"]
    }
  }
}
```

**Codex:**

```bash
codex --mcp-config '{"mcpServers":{"todo":{"command":"python","args":["/absolute/path/to/upjack/examples/todo/server.py"]}}}'
```

Replace `/absolute/path/to/upjack` with the actual path where you cloned the repo.

### What to try

Once connected, ask your agent:

- "Load the seed data" (populates sample tasks, projects, and labels)
- "Create a task called 'Write README' with high priority"
- "List all my tasks"
- "Search for tasks about README"
- "Create a project called 'Documentation'"
- "Update that task to link it to the Documentation project"

## Structure

```
todo/
├── manifest.json          # MCPB manifest with upjack extension
├── context.md             # Domain knowledge (prioritization, lifecycle)
├── server.py              # 3-line Python MCP server
├── server.ts              # 3-line TypeScript MCP server
├── schemas/               # Entity JSON Schemas
│   ├── task.schema.json
│   ├── project.schema.json
│   └── label.schema.json
├── skills/
│   └── task-management/SKILL.md
└── seed/                  # Initial data
    ├── sample-tasks.json
    ├── sample-projects.json
    └── sample-labels.json
```
