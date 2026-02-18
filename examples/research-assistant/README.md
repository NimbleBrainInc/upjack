# Research Assistant: Upjack Example App

A minimal research management app built with the Upjack framework. Track topics, evaluate sources, take structured notes, and synthesize reports, all from schemas and skills.

## What This Demonstrates

The simplest Upjack app. A good starting point to understand the framework before exploring the [Todo](../todo/) or [CRM](../crm/) examples:

- **4 entity types** with JSON Schema definitions and `allOf` composition
- **1 bundled skill** (research methodology: systematic investigation process)
- **1 schedule** (daily topic monitoring)
- **Seed data** (sample research topics)
- **Domain context** (`context.md` with source evaluation rubric and note-taking guidelines)

## Entity Types

| Entity | Prefix | Schema | Notes |
|--------|--------|--------|-------|
| Topic | `top_` | [topic.schema.json](schemas/topic.schema.json) | Research questions with priority and key questions |
| Source | `src_` | [source.schema.json](schemas/source.schema.json) | Articles, papers, reports with credibility rating (1-5) |
| Note | `nt_` | [note.schema.json](schemas/note.schema.json) | Extracted insights tagged by claim type |
| Report | `rpt_` | [report.schema.json](schemas/report.schema.json) | Synthesized findings with executive summary |

## Skill

### [Research Methodology](skills/research-methodology/SKILL.md)

A five-step process: scope the topic, discover sources, evaluate credibility, extract notes, and synthesize reports. Also handles daily monitoring of active topics for new developments.

## Schedule

| Name | Cron | Skill |
|------|------|-------|
| `topic-monitoring` | `0 8 * * *` (daily 8 AM) | Research methodology |

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
cd examples/research-assistant
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

It exposes tools for all four entity types (`create_topic`, `list_topics`, `search_topics`, etc.) and serves `context.md` and the research methodology skill as MCP resources.

### 3. Connect to your editor

**Claude Desktop**: add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "research": {
      "command": "python",
      "args": ["/absolute/path/to/upjack/examples/research-assistant/server.py"]
    }
  }
}
```

**Claude Code:**

```bash
claude mcp add research -- python /absolute/path/to/upjack/examples/research-assistant/server.py
```

**Cursor**: add to `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "research": {
      "command": "python",
      "args": ["/absolute/path/to/upjack/examples/research-assistant/server.py"]
    }
  }
}
```

**Codex:**

```bash
codex --mcp-config '{"mcpServers":{"research":{"command":"python","args":["/absolute/path/to/upjack/examples/research-assistant/server.py"]}}}'
```

Replace `/absolute/path/to/upjack` with the actual path where you cloned the repo.

### What to try

Once connected, ask your agent:

- "Load the seed data" (populates sample research topics)
- "Create a topic about MCP adoption trends with high priority"
- "Add a source: the MCP spec at modelcontextprotocol.io, credibility 5"
- "Take a note on that source about how MCP enables agent interop"
- "List all my notes"
- "Create a report summarizing what we know about MCP adoption"

## File Structure

```
research-assistant/
├── manifest.json                         # MCPB manifest with upjack extension
├── context.md                            # Domain knowledge (source evaluation, note-taking)
├── server.py                             # 3-line Python MCP server
├── server.ts                             # 3-line TypeScript MCP server
├── schemas/
│   ├── topic.schema.json                 # Research topic schema
│   ├── source.schema.json                # Source schema (credibility 1-5)
│   ├── note.schema.json                  # Note schema (claim types)
│   └── report.schema.json               # Report schema (executive summary + body)
├── skills/
│   └── research-methodology/SKILL.md     # Investigation process
└── seed/
    └── sample-topics.json                # Example topics (AI frameworks, MCP adoption)
```
