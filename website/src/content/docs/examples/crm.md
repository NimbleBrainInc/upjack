---
title: CRM
description: "A full-featured CRM example app with 5 entity types, skills, bundle dependencies, hooks, and schedules."
draft: false
---

The CRM example demonstrates the full range of Upjack features. It's a Tier 2 app: schemas, skills, and a generated MCP server.

[View on GitHub](https://github.com/NimbleBrainInc/upjack/tree/main/examples/crm/)

## What's Included

- **5 entity types**: contact (`ct_`), company (`co_`), deal (`dl_`), pipeline (`pl_`, singleton), activity (`act_`)
- **3 bundled skills**: lead qualification (scoring rubric), deal forecasting, follow-up emails
- **3 schedules**: daily pipeline review, weekly stale deal alert, nightly lead scoring
- **2 hooks**: auto-score new contacts, trigger forecast on closed deals
- **3 swappable dependencies**: email (SES/SendGrid/Resend), enrichment (Clearbit/Apollo), PDF generation

## Entity Types

| Entity | Prefix | Purpose |
|--------|--------|---------|
| `contact` | `ct_` | People: leads, customers, partners |
| `company` | `co_` | Organizations contacts belong to |
| `deal` | `dl_` | Sales opportunities with value and stage |
| `pipeline` | `pl_` | Pipeline configuration (singleton) |
| `activity` | `act_` | Interaction log: emails, calls, notes |

## Key Patterns

**Relationships**: Contacts link to companies via `relationships` array. Deals link to both contacts and companies.

**Skills as decision logic**: The lead qualification skill defines scoring criteria. The agent reads it and applies the rubric, so no hardcoded scoring function is needed.

**Swappable bundles**: Email sending is declared by alias (`email`), not package name. The default is AWS SES, but SendGrid is listed as an alternative. Switch providers by changing one manifest field.

## Running It

```bash
cd examples/crm
uv run python server.py
```

This starts an MCP server with 30 tools (6 per entity type) plus context and skill resources.
