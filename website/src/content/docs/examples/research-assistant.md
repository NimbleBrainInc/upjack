---
title: Research Assistant
description: "A minimal Upjack example for managing research topics, sources, notes, and reports."
draft: false
---

The Research Assistant is the simplest example app, a Tier 1 app with schemas and skills but no custom server.

[View on GitHub](https://github.com/NimbleBrainInc/upjack/tree/main/examples/research-assistant/)

## What's Included

- **4 entity types**: topic (`tp_`), source (`src_`), note (`nt_`), report (`rpt_`)
- **1 bundled skill**: research methodology (source evaluation, note-taking, synthesis)
- **Seed data**: sample topics and sources

## Entity Types

| Entity | Prefix | Purpose |
|--------|--------|---------|
| `topic` | `tp_` | Research topics being investigated |
| `source` | `src_` | Books, papers, URLs, interviews |
| `note` | `nt_` | Notes taken from sources |
| `report` | `rpt_` | Synthesized findings |

## Key Patterns

**Minimal viable app**: No hooks, no schedules, no bundle dependencies. Just schemas and a skill. This is what a Tier 1 Upjack app looks like.

**Relationships**: Notes link to both a topic and a source via the `relationships` array. Reports link to a topic.

**Skill-driven synthesis**: The research methodology skill teaches the agent how to evaluate source credibility, take structured notes, and synthesize findings into reports. The logic lives in Markdown, not code.
