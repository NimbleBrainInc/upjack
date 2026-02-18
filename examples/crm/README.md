# CRM: Upjack Example App

A full-featured CRM (Customer Relationship Management) app built with the Upjack framework. Near-zero code: just schemas, skills, a manifest, and a 3-line server entry point.

## What This Demonstrates

This example shows every major Upjack feature:

- **5 entity types** with JSON Schema definitions and `allOf` composition
- **Singleton entity** (pipeline configuration, only one can exist)
- **3 bundled skills** (lead qualification, deal forecasting, follow-up emails)
- **3 bundle dependencies** with alias-based swappability (email, enrichment, PDF)
- **2 hooks** (auto-score new contacts, trigger forecast on closed deals)
- **3 schedules** (daily pipeline review, weekly stale alerts, nightly scoring)
- **3 views** (hot leads, stale deals, weekly pipeline)
- **Seed data** (default pipeline stages, sample contacts, company, and deal)

## Entity Types

| Entity | Prefix | Schema | Notes |
|--------|--------|--------|-------|
| Contact | `ct_` | [contact.schema.json](schemas/contact.schema.json) | People tracked in the CRM |
| Company | `co_` | [company.schema.json](schemas/company.schema.json) | Organizations |
| Deal | `dl_` | [deal.schema.json](schemas/deal.schema.json) | Sales opportunities |
| Pipeline | `pl_` | [pipeline.schema.json](schemas/pipeline.schema.json) | Stage configuration (singleton) |
| Activity | `act_` | [activity.schema.json](schemas/activity.schema.json) | Logged interactions (not indexed) |

## Skills

### [Lead Qualification](skills/lead-qualification/SKILL.md)

Scores contacts 0-100 based on title seniority, company size, email domain, engagement signals. Fired automatically when a contact is created (hook) and nightly at 2 AM (schedule).

### [Deal Forecasting](skills/deal-forecasting/SKILL.md)

Analyzes pipeline health: flags stale deals, calculates weighted pipeline value, identifies at-risk opportunities. Runs weekdays at 9 AM and triggers when a deal reaches "closed-won."

### [Follow-up Email](skills/follow-up-email/SKILL.md)

Drafts contextual follow-up emails based on contact history, deal status, and last interaction. Runs weekly on Mondays and on demand. Uses the `email` bundle dependency for sending.

## Bundle Dependencies

| Alias | Purpose | Default | Alternatives |
|-------|---------|---------|--------------|
| `email` | Send follow-up emails | `@nimblebraininc/aws-ses` | SendGrid, Resend |
| `enrichment` | Enrich contact/company data | `@nimblebraininc/clearbit` | Apollo, FullContact |
| `pdf` | Generate proposals/reports | `@nimblebraininc/pdfco` | — |

The `email` dependency is required. `enrichment` and `pdf` are optional. The app works without them, but skills will skip enrichment steps if unavailable.

Skills reference `email__send_email` (the alias), not `ses__send_email` (the package). The alias indirection means swapping providers requires no skill changes.

## Hooks

| Event | Entity | Condition | Skill |
|-------|--------|-----------|-------|
| `entity.created` | contact | — | Lead qualification |
| `entity.updated` | deal | `$.stage == 'closed-won'` | Deal forecasting |

## Schedules

| Name | Cron | Skill |
|------|------|-------|
| `pipeline-review` | `0 9 * * 1-5` (weekdays 9 AM) | Deal forecasting |
| `stale-deal-alert` | `0 10 * * 1` (Monday 10 AM) | Follow-up email |
| `lead-scoring` | `0 2 * * *` (nightly 2 AM) | Lead qualification |

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
cd examples/crm
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

It exposes 31 tools (6 per entity type plus `seed_data`). It validates every write against the composed schema (base entity + your app schema), stores entities as JSON files in `./workspace/` (relative to where you run the command), and serves `context.md` and bundled skills as MCP resources.

### 3. Connect to your editor

**Claude Desktop**: add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "crm": {
      "command": "python",
      "args": ["/absolute/path/to/upjack/examples/crm/server.py"]
    }
  }
}
```

**Claude Code:**

```bash
claude mcp add crm -- python /absolute/path/to/upjack/examples/crm/server.py
```

**Cursor**: add to `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "crm": {
      "command": "python",
      "args": ["/absolute/path/to/upjack/examples/crm/server.py"]
    }
  }
}
```

**Codex:**

```bash
codex --mcp-config '{"mcpServers":{"crm":{"command":"python","args":["/absolute/path/to/upjack/examples/crm/server.py"]}}}'
```

Replace `/absolute/path/to/upjack` with the actual path where you cloned the repo.

### What to try

Once connected, ask your agent:

- "Load the seed data" (populates pipeline stages, sample contacts, a company, and a deal)
- "Create a contact named Jane Smith at Acme Corp with email jane@acme.com"
- "List all contacts"
- "Search contacts for acme"
- "Create a deal for Jane: 'Enterprise License', qualification stage, $50k value"
- "List all deals and their stages"
- "Update Jane's lead score to 85"

For custom logic (computed fields, external API calls), see the commented manual wiring example in `server.py`.

## File Structure

```
crm/
├── manifest.json                    # MCPB manifest with upjack extension
├── context.md                       # Domain knowledge (always loaded)
├── server.py                        # 3-line Python MCP server
├── server.ts                        # 3-line TypeScript MCP server
├── schemas/
│   ├── contact.schema.json          # Contact entity schema
│   ├── company.schema.json          # Company entity schema
│   ├── deal.schema.json             # Deal entity schema
│   ├── pipeline.schema.json         # Pipeline config (singleton)
│   └── activity.schema.json         # Activity log schema
├── skills/
│   ├── lead-qualification/SKILL.md  # Lead scoring rubric and process
│   ├── deal-forecasting/SKILL.md    # Pipeline analysis and forecasting
│   └── follow-up-email/SKILL.md     # Email drafting and sending
└── seed/
    ├── default-pipeline.json        # Pipeline stages (Prospecting → Closed)
    ├── sample-company.json          # Example company
    ├── sample-contacts.json         # Example contacts
    └── sample-deal.json             # Example deal
```
