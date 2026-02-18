# NimbleBrain Upjack Framework

Declarative AI-native application framework. Apps are MCPB packages with a `_meta["ai.nimblebrain/upjack"]` extension.

**Current version**: 0.1.0
**Package names**: `upjack` on PyPI, `upjack` on npm

## Directory Layout

```
lib/python/       Python library (upjack) — source in src/upjack/
lib/typescript/   TypeScript library (upjack) — source in src/
schemas/          JSON Schemas (upjack-entity, upjack-manifest) + validation tooling
skills/           Publishable skills (upjack-app-builder) — symlinked from .claude/skills/
examples/         Reference apps (CRM, Todo, Research Assistant)
website/          Documentation site (Astro/Starlight) — upjack.dev
workspace/        Runtime entity data (gitignored, created at runtime)
```

## Verification

**Always run before considering work done:**

```bash
make check    # from repo root — validates schemas + runs Python + TS tests
```

For a single library:

```bash
make -C lib/python check       # format + lint + typecheck + tests
make -C lib/typescript check   # format + lint + typecheck + tests
make -C schemas validate       # bundle + AJV validation
```

Individual targets:

```bash
# Python (from lib/python/)
make install      # uv sync --group dev
make test         # pytest
make format       # ruff format
make lint         # ruff check
make typecheck    # ty check
make test-cov     # pytest with coverage
make test-e2e     # end-to-end tests (builds MCPB bundles)

# TypeScript (from lib/typescript/)
make install      # npm install
make test         # vitest
make format       # biome format
make lint         # biome lint
make typecheck    # tsc --noEmit
make build        # tsup → dist/ (ESM + .d.ts)
```

## Version Locations

Version must be updated in all locations when releasing:

- `lib/python/pyproject.toml` → `version`
- `lib/python/src/upjack/__init__.py` → `__version__`
- `lib/typescript/package.json` → `version`
- `skills/upjack-app-builder/SKILL.md` → `metadata.version`
- `skills/upjack-app-builder/version.txt`

## Releasing

Tag-triggered via GitHub Actions with trusted publishers. See `CONTRIBUTING.md` for full process.

| Library | Tag format | Workflow | Registry |
|---------|-----------|----------|----------|
| Python | `python-v{semver}` | `publish-python.yml` | PyPI (`upjack`) |
| TypeScript | `typescript-v{semver}` | `publish-typescript.yml` | npm (`upjack`) |
| Skill | `skill-v{semver}` | `publish-skill.yml` | mpak (`@nimblebraininc/upjack-app-builder`) |

Quick release:
```bash
# After bumping versions and updating CHANGELOG.md:
git tag python-v0.1.0 && git tag typescript-v0.1.0
git push origin main --tags
```

## Key Design Decisions

- **Apps are MCPB packages** — no fork of the MCPB spec, just a `_meta` extension
- **Schema-driven** — JSON Schema (draft 2020-12) for entities, `allOf` composition for layering
- **Skills over code** — domain expertise lives in Markdown, not Python/TypeScript
- **Three tiers**: schemas + skills (no code) → MCP server (`create_server()` / `createServer()`) → custom server (optional)
- **Entity IDs**: `{prefix}_{ULID}` where prefix is 2-4 lowercase chars
- **Storage**: JSON files at `{namespace}/data/{plural}/{id}.json`
- **FastMCP is optional** — Python core works without it; install `upjack[mcp]` for server support
- **@modelcontextprotocol/sdk is optional** — TypeScript core works without it; import `upjack/server` for server support

## Tooling

| Concern | Python | TypeScript |
|---------|--------|------------|
| Lint + format | ruff | Biome |
| Type checking | ty | tsc |
| Testing | pytest | vitest |
| Build | hatchling (wheel) | tsup (ESM + .d.ts) |
| Package manager | uv | npm |

**Do not use**: black, flake8, isort, mypy, pyright (Python) or ESLint, Prettier, Jest (TypeScript).

## Schema Workflow

1. Edit source schemas in `schemas/v1/*.schema.json`
2. Run `make -C schemas validate` to bundle and test
3. Commit both source and bundled schemas

## Examples

Three reference apps in `examples/` — each has a manifest, schemas, skills, context, seed data, and server entry points for both Python and TypeScript. See `examples/README.md` for overview.

| Example | Entities | Complexity |
|---------|----------|-----------|
| `examples/todo/` | task, project, label | Starter — hooks, schedules, views |
| `examples/crm/` | contact, company, deal, pipeline, activity | Full — skills, bundles, schedules, hooks, views |
| `examples/research-assistant/` | topic, source, note, report | Minimal |

## Website

Astro/Starlight documentation site in `website/`. Specs that were previously in `docs/` are now pages in `website/src/content/docs/`.

```bash
cd website && npm install && npm run dev    # local dev server
cd website && npm run build                 # production build → dist/
```

## Skills

`skills/upjack-app-builder/SKILL.md` (symlinked from `.claude/skills/`) — generates complete, spec-compliant example apps from natural language descriptions. Produces manifest, schemas, skills, context, seed data, server entry points, and E2E tests. Published to mpak as `@nimblebraininc/upjack-app-builder`.
