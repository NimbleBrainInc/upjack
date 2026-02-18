---
title: Todo
description: "A mid-complexity todo app example — tasks, projects, labels, hooks, schedules, and views."
draft: false
---

The Todo example sits between Research Assistant (minimal) and CRM (full-featured). It shows hooks, schedules, and views in a familiar domain.

[View on GitHub](https://github.com/NimbleBrainInc/upjack/tree/main/examples/todo/)

## What's Included

- **3 entity types**: task (`tsk_`), project (`prj_`), label (`lbl_`)
- **1 bundled skill**: task management (prioritization, daily review)
- **Hooks**: auto-assign priority on new tasks
- **Schedules**: daily review at 9 AM
- **Views**: overdue tasks, high-priority tasks

## Entity Types

| Entity | Prefix | Purpose |
|--------|--------|---------|
| `task` | `tsk_` | Individual tasks with priority, due date, effort |
| `project` | `prj_` | Groups of related tasks |
| `label` | `lbl_` | Tags for categorization |

## Key Patterns

**Priority and effort**: Tasks have both a priority level (`critical`, `high`, `medium`, `low`, `none`) and an effort estimate (`trivial`, `small`, `medium`, `large`, `epic`). The skill teaches the agent how to balance urgency and effort.

**Views**: Named queries like "overdue tasks" are declared in the manifest. The platform materializes them for quick access.

See the [Build a Todo App](/tutorials/todo-app/) tutorial for a step-by-step walkthrough of building a simpler version of this example.
