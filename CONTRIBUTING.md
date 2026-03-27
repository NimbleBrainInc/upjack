# Contributing to Upjack

Thanks for your interest in contributing to the Upjack framework.

## Development Setup

### Prerequisites

- Python >= 3.13
- Node.js >= 18
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### Clone and Install

```bash
git clone https://github.com/NimbleBrainInc/upjack.git
cd upjack

# Python library
cd lib/python
uv sync --group dev

# TypeScript library
cd ../typescript
npm install

# Schema tooling
cd ../../schemas
npm install
```

### Run All Checks

```bash
# From repo root
make check
```

This validates schemas and runs both library test suites. For the full check (format, lint, typecheck, tests), run `make check` from within each library directory.

## Python Library Development (`lib/python/`)

```bash
cd lib/python

# Run tests
make test

# Format code
make format

# Lint
make lint

# Type check
make typecheck

# All checks (format, lint, typecheck, tests)
make check
```

### Tooling

| Tool | Purpose |
|------|---------|
| [ruff](https://docs.astral.sh/ruff/) | Linting and formatting |
| [ty](https://docs.astral.sh/ty/) | Type checking |
| [pytest](https://docs.pytest.org/) | Testing |
| [uv](https://docs.astral.sh/uv/) | Package management |

Do not use black, flake8, isort, mypy, or pyright — we use ruff and ty exclusively.

## TypeScript Library Development (`lib/typescript/`)

```bash
cd lib/typescript

# Run tests
make test

# Format code
make format

# Lint
make lint

# Type check
make typecheck

# Build (ESM + .d.ts)
make build

# All checks (format, lint, typecheck, tests)
make check
```

### Tooling

| Tool | Purpose |
|------|---------|
| [Biome](https://biomejs.dev/) | Linting and formatting |
| [tsc](https://www.typescriptlang.org/) | Type checking |
| [vitest](https://vitest.dev/) | Testing |
| [tsup](https://tsup.egoist.dev/) | Build (ESM + .d.ts) |

Do not use ESLint, Prettier, or Jest — we use Biome and vitest exclusively.

## Schema Development (`schemas/`)

```bash
cd schemas

# Bundle schemas (dereference $refs)
make bundle

# Validate with AJV
make validate
```

Schemas are JSON Schema draft 2020-12. Edit source schemas in `schemas/v1/`, then run `make validate` to verify.

## Example Apps (`examples/`)

Example apps demonstrate Upjack features. Each example should include:

- `manifest.json` — Complete manifest with upjack extension
- `schemas/` — Entity schemas using `allOf` composition with the base entity schema
- `skills/` — Markdown skill documents
- `context.md` — Domain knowledge
- `seed/` — Initial data (optional)

When adding or modifying examples, ensure schemas validate against `upjack-manifest.schema.json`.

### Scaffolding a new example with Claude Code

A skill is included that generates a complete, spec-compliant example app from a description:

```
> create me a todo app
```

This produces the full directory structure (manifest, schemas, skills, context, seed data, server entry point, README) and adds E2E tests to `lib/tests/test_e2e.py`. See `skills/upjack-app-builder/SKILL.md` for the full spec it follows.

## Pull Requests

1. Fork the repo and create a feature branch
2. Make your changes
3. Run `make check` from the repo root — all checks must pass
4. Submit a PR with a clear description of what changed and why

### Commit Messages

Use concise, imperative commit messages:

```
Fix schema validation for singleton entities
Add recruitment pipeline example app
Update entity model to support custom ID prefixes
```

## Code Style

- Python: ruff handles formatting and linting. Run `make format` before committing.
- JSON: 2-space indentation, trailing newline.
- Markdown: No hard line wrapping. One sentence per line is fine but not required.

## Releasing

Releases are automated via GitHub Actions with trusted publishers. Each library is released independently using prefixed tags.

### Tag conventions

| Library | Tag format | Example | Workflow |
|---------|-----------|---------|----------|
| Python (`lib/python/`) | `python-v{semver}` | `python-v0.1.0` | `publish-python.yml` |
| TypeScript (`lib/typescript/`) | `typescript-v{semver}` | `typescript-v0.1.0` | `publish-typescript.yml` |
| Skill (`skills/`) | `skill-v{semver}` | `skill-v0.1.0` | `publish-skill.yml` |

### Release process

1. Update the version in the library's manifest:
   - **Python**: `lib/python/pyproject.toml` (`version`) and `lib/python/src/upjack/__init__.py` (`__version__`)
   - **TypeScript**: `lib/typescript/package.json` (`version`)
   - **Skill**: `skills/upjack-app-builder/SKILL.md` (`metadata.version`) and `skills/upjack-app-builder/version.txt`
2. Update `CHANGELOG.md` with the new version and date
3. Run `make check` from the repo root
4. Commit: `git commit -m "Release python-v0.X.Y"` (or `typescript-v0.X.Y`)
5. Tag and push:
   ```bash
   git tag python-v0.X.Y
   git push origin main --tags
   ```
6. The workflow verifies the tag version matches the manifest, runs all checks, and publishes
7. Create a GitHub release with the changelog entry:
   ```bash
   gh release create v0.X.Y --title "v0.X.Y" --notes "<changelog entry>" --target main --latest
   ```

### Prerequisites (one-time setup)

- **PyPI**: Configure a [trusted publisher](https://docs.pypi.org/trusted-publishers/) for the `upjack` project. Set the GitHub repository to `NimbleBrainInc/upjack`, workflow to `publish-python.yml`, and environment to `pypi`.
- **npm**: Configure [provenance](https://docs.npmjs.com/generating-provenance-statements) for the `upjack` package. Create a GitHub environment called `npm` in the repository settings.

## Reporting Issues

Open an issue on GitHub. Include:

- What you expected to happen
- What actually happened
- Steps to reproduce
- Python version and OS

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 license.
