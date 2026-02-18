# Upjack Example Apps

Reference implementations of Upjack apps. Each example is a complete MCP server you can build from source and connect to Claude Desktop, Claude Code, Cursor, or Codex.

**New to Upjack?** Start with the [Todo List](#todo-list). It's the easiest to understand and has all the core features.

## Prerequisites

- Python >= 3.13 and [uv](https://docs.astral.sh/uv/) (for Python examples)
- Node.js >= 18 (for TypeScript examples)
- Git (to clone the repo)

## Quick Start (any example)

Clone the repo and install the library from source:

```bash
git clone https://github.com/NimbleBrainInc/upjack.git
cd upjack
```

**Python:**

```bash
cd lib/python
uv pip install -e ".[mcp]"
cd ../../examples/todo
python server.py
```

**TypeScript:**

```bash
cd lib/typescript
npm install && npm run build
cd ../../examples/todo
npx tsx server.ts
```

> TypeScript examples use `npx tsx` to run `.ts` files directly. Running with `node` requires Node 22+.

The server communicates over stdio, so there's no visible output. It's ready when the terminal is waiting for input. Press Ctrl+C to stop. See each example's README for how to connect it to your editor or agent.

## Examples

| Example | Entities | Complexity | Best For |
|---------|----------|------------|----------|
| [Todo List](todo/) | 3 (task, project, label) | Mid | Getting started, understanding hooks and views |
| [Research Assistant](research-assistant/) | 4 (topic, source, note, report) | Minimal | Seeing the simplest possible Upjack app |
| [CRM](crm/) | 5 (contact, company, deal, pipeline, activity) | Full | Every Upjack feature in action |

## Validating Examples

Example manifests and schemas are validated as part of the test suite:

```bash
cd schemas && make validate      # schema validation
cd lib/python && make test       # runs integration tests against all 3 examples
cd lib/typescript && make test   # same, TypeScript side
```
