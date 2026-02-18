---
title: Examples Overview
description: "Reference implementations of Upjack apps — CRM, Todo, and Research Assistant."
draft: false
---

These reference apps demonstrate Upjack at different levels of complexity.

| Example | Complexity | Entity Types | Skills | Features |
|---------|-----------|-------------|--------|----------|
| [Research Assistant](/examples/research-assistant/) | Minimal | 4 | 1 | Basic CRUD + search |
| [Todo](/examples/todo/) | Mid | 3 | 1 | Hooks, schedules, views |
| [CRM](/examples/crm/) | Full | 5 | 3 | Bundles, hooks, schedules, seed data |

All examples are available on [GitHub](https://github.com/NimbleBrainInc/upjack/tree/main/examples/).

## CRM

A full-featured CRM with 5 entity types, 3 bundled skills, bundle dependencies for email sending, and cron schedules. Demonstrates the full range of Upjack features.

```
examples/crm/
├── manifest.json          # Complete MCPB manifest with upjack extension
├── context.md             # Domain knowledge for the agent
├── schemas/               # Entity JSON Schemas
├── skills/                # Bundled skill definitions
└── seed/                  # Initial data
```

## Research Assistant

A simpler app for managing research topics, sources, notes, and reports. Demonstrates the minimal viable Upjack app.

```
examples/research-assistant/
├── manifest.json
├── context.md
├── schemas/
├── skills/
└── seed/
```

## Todo List

A mid-complexity personal todo list with 3 entity types, 1 bundled skill, hooks, schedules, and views. Sits between Research Assistant and CRM in complexity.

```
examples/todo/
├── manifest.json
├── context.md
├── schemas/
├── skills/
└── seed/
```

## Validating Examples

Example manifests are validated as part of the schema validation suite:

```bash
cd schemas && make validate
```
