---
title: "Lifecycle"
description: "Install, update, and uninstall operations for Upjack apps: steps, git commits, error recovery, and the app registry."
draft: false
---

:::note[Platform specification]
This page documents the Upjack platform runtime behavior. The `upjack` library handles entity CRUD and server generation; lifecycle operations (install, update, uninstall) are implemented by the NimbleBrain platform.
:::

## Overview

Upjack apps have a managed lifecycle: install, update, and uninstall. Each lifecycle operation is performed by the platform installer, produces git commits, and updates the system registry. This document specifies the exact steps for each operation.

## Install

Installation transforms a downloaded MCPB package into a fully operational Upjack app in the tenant workspace.

### Steps

```
1. Download         Fetch MCPB package from mpak registry (or local path)
2. Validate         Validate manifest against upjack-manifest schema
3. Scaffold         Create workspace directory structure
4. Install Skills   Download/copy skill files into workspace
5. Install Schemas  Copy entity schemas into workspace
6. Resolve Bundles  Resolve bundle dependencies to exact versions
7. Register         Register schedules, hooks, and views
8. Seed Data        Create initial entities from seed data (if configured)
9. Write Lock       Write upjack.lock.json with resolved state
10. Update Registry  Add app entry to system/apps.json
11. Git Commit       Commit all changes as a single install commit
```

### Detailed Behavior

#### 1. Download

Fetch the MCPB package from the mpak registry using the package name and version. Alternatively, accept a local file path for development. Extract the package contents to a temporary directory.

#### 2. Validate

Validate `manifest.json` against both the MCPB manifest schema and the Upjack [manifest schema](/reference/manifest/) (`_meta["ai.nimblebrain/upjack"]`). Fail immediately on validation errors.

Validation checks:
- `upjack_version` matches a supported version
- `namespace` is not already in use by another installed app
- All `entities` have unique `name` and `prefix` values within the app
- All referenced skill paths and schema paths exist in the package
- All `bundles` have at least one tool in `tools_used`

#### 3. Scaffold

Create the workspace directory structure under the app's namespace:

```
{namespace}/
    data/
        {plural}/               (one per entity)
    skills/
    views/
    schemas/
```

For example, a CRM app with leads, companies, and deals:

```
apps/crm/
    data/
        leads/
        companies/
        deals/
        activities/
        pipeline_configs/
    skills/
    views/
    schemas/
```

#### 4. Install Skills

For each skill reference in the manifest:

- **bundled**: Copy the file from the package into `{namespace}/skills/{app}--{skill-name}.md`
- **mpak**: Download the skill package from the registry, verify integrity hash, extract and copy
- **github**: Fetch the file from the GitHub API at the specified ref, copy into skills directory

All skills are renamed with the app prefix (double-dash convention) to prevent collisions. See [Bundles & Skills](/reference/bundles-and-skills/) for details on skill sources and naming.

#### 5. Install Schemas

Copy all entity schema files from the package into `{namespace}/schemas/`. These are used by the [runtime tools](/reference/runtime-tools/) for validation.

#### 6. Resolve Bundles

For each bundle dependency:

1. Check if the user has a preference for an alternative package. Use the default if no preference.
2. Resolve the semver range to an exact version from the mpak registry.
3. Verify the resolved package exposes all tools listed in `tools_used`. Fail with an explicit error if any tool is missing.
4. If the bundle is `required: true` and resolution fails, abort installation.
5. If the bundle is `required: false` and resolution fails, warn and continue.
6. Record the resolved binding (alias to exact package version).

#### 7. Register

Register the app's runtime components with the platform:

- **Schedules**: Register each schedule with the platform's cron scheduler. Honor `enabled_by_default`.
- **Hooks**: Register each hook with the platform's event dispatcher.
- **Views**: Register view definitions for materialization.

#### 8. Seed Data

If `seed` is configured and `run_on_install: true`:

1. Read seed data files from the specified path in the package.
2. For each seed entity, call `entity_create` (which handles ID generation, validation, and indexing).
3. Seed entities are created with `created_by: "system"`.
4. Failures in individual seed entities are logged but do not abort installation.

#### 9. Write Lock

Write `upjack.lock.json` to `{namespace}/upjack.lock.json`. The lock file captures the complete resolved state:

```json
{
  "upjack_version": "0.1",
  "package": {
    "name": "@nimblebrain/crm",
    "version": "0.1.0",
    "integrity": "sha256-..."
  },
  "resolved_at": "2026-02-15T10:30:00Z",
  "namespace": "apps/crm",
  "entities": [
    {
      "name": "lead",
      "prefix": "ld",
      "schema": "schemas/lead.schema.json",
      "schema_version": 1
    }
  ],
  "bundles": {
    "email": {
      "resolved": "@nimblebrain/aws-ses",
      "version": "1.2.3",
      "integrity": "sha256-..."
    },
    "enrichment": {
      "resolved": null,
      "reason": "optional, not configured"
    }
  },
  "skills": [
    {
      "name": "crm--lead-qualification",
      "source": "bundled",
      "integrity": "sha256-..."
    },
    {
      "name": "crm--objection-handling",
      "source": "github",
      "repo": "NimbleBrainInc/skills",
      "ref": "v1.2.0",
      "resolved_sha": "abc123def456..."
    }
  ],
  "schedules": [
    {
      "name": "weekly-pipeline-review",
      "cron": "0 9 * * 1",
      "enabled": true
    }
  ]
}
```

#### 10. Update Registry

Add an entry to `system/apps.json` (creating the file if it does not exist). See [App Registry](#app-registry) below for the full schema.

#### 11. Git Commit

Commit all changes (scaffolded directories, skills, schemas, lock file, registry update, seed data) as a single atomic commit:

```
upjack: install @nimblebrain/crm@0.1.0 → apps/crm
```

## Update

Updating an app installs a new version while preserving existing entity data.

### Steps

```
1. Download         Fetch new version of the MCPB package
2. Validate         Validate new manifest
3. Diff Manifests   Compare old and new upjack manifests
4. Migrate Schemas  Update entity schemas (lazy migration)
5. Update Skills    Add/remove/update skill files
6. Re-resolve       Re-resolve bundle dependencies
7. Update Registry  Update schedules, hooks, views
8. Write Lock       Update upjack.lock.json
9. Update Registry  Update system/apps.json entry
10. Git Commit       Commit all changes
```

### Detailed Behavior

#### 3. Diff Manifests

Compare the old manifest (from the current lock file) with the new manifest to determine:

- **Added entities**: New entity types. Scaffold directories and schemas.
- **Removed entities**: Deleted entity types. Data is preserved but no longer managed (warn user).
- **Modified entities**: Schema changes. Update schema files, increment schema version.
- **Added/removed skills**: Install new skills, remove old skill files
- **Changed bundles**: Re-resolve if version range or tools_used changed
- **Changed schedules/hooks**: Update registrations

#### 4. Migrate Schemas (Lazy)

Schema migration is **lazy**, not eager:

1. Copy new schema files to `{namespace}/schemas/`.
2. Update the `schema_version` in the lock file.
3. Existing entity files are **not** modified.
4. When an entity is next read, the runtime detects `entity.version < current_schema_version`.
5. If a migration function exists in the app package, it is applied and the entity is rewritten.
6. If no migration function exists, the entity is validated against the new schema. If valid, its version is bumped. If invalid, a warning is logged.

This avoids potentially expensive bulk migrations of large datasets. See [Entity Model](/reference/entity-model/) for details on the version field and lazy migration.

#### 5. Update Skills

- **New skills**: Install into the skills directory with app prefix
- **Removed skills**: Delete the skill file from the workspace
- **Updated skills**: Overwrite the existing file with the new version

#### 10. Git Commit

```
upjack: update @nimblebrain/crm 0.1.0 → 0.2.0
```

## Uninstall

Uninstalling an app removes it from the workspace while offering data export.

### Steps

```
1. Export Data      Offer to export entity data before removal
2. Remove Skills    Delete all app-prefixed skill files
3. Remove Schedules Deregister all schedules from the cron scheduler
4. Remove Hooks     Deregister all hooks from the event dispatcher
5. Clean Workspace  Remove app directory structure
6. Update Registry  Remove app entry from system/apps.json
7. Git Commit       Commit all changes
```

### Detailed Behavior

#### 1. Export Data

Before removing any files, the installer offers to export entity data:

- Export to a ZIP file: `{app}-export-{timestamp}.zip` containing all entity JSON files
- Export location: user's configured export directory or workspace root
- The user can skip export if the data is not needed

This is a safety net, since the workspace is git-backed and data can also be recovered from git history.

#### 5. Clean Workspace

Remove the entire app directory tree:

```
{namespace}/           (removed)
    data/              (all entity files)
    skills/            (all skill files)
    views/             (all view files)
    schemas/           (all schema files)
    upjack.lock.json  (lock file)
```

#### 7. Git Commit

```
upjack: uninstall @nimblebrain/crm@0.1.0 from apps/crm
```

## App Registry

The file `system/apps.json` is the central registry of all installed Upjack apps. It is maintained by the installer and read by the runtime.

### Schema

```json
{
  "apps": {
    "crm": {
      "package": {
        "name": "@nimblebrain/crm",
        "version": "0.1.0"
      },
      "namespace": "apps/crm",
      "installed_at": "2026-02-15T10:30:00Z",
      "updated_at": "2026-02-15T10:30:00Z",
      "status": "active",
      "skills": [
        "crm--lead-qualification",
        "crm--deal-review",
        "crm--follow-up-composer",
        "crm--objection-handling"
      ],
      "schedules": [
        {
          "name": "weekly-pipeline-review",
          "enabled": true
        },
        {
          "name": "daily-follow-up-check",
          "enabled": true
        }
      ],
      "entity_counts": {
        "lead": 42,
        "company": 15,
        "deal": 8,
        "activity": 156,
        "pipeline_config": 1
      },
      "bundles": {
        "email": {
          "resolved": "@nimblebrain/aws-ses",
          "version": "1.2.3"
        },
        "enrichment": {
          "resolved": null
        }
      }
    }
  }
}
```

### Registry Fields

| Field | Type | Description |
|-------|------|-------------|
| `package.name` | string | MCPB package name. |
| `package.version` | string | Installed version (exact, not range). |
| `namespace` | string | Workspace path. |
| `installed_at` | string (date-time) | When the app was first installed. |
| `updated_at` | string (date-time) | When the app was last installed or updated. |
| `status` | string | App status: `active`, `disabled`, `error`. |
| `skills` | array of strings | Installed skill names (app-prefixed). |
| `schedules` | array of objects | Registered schedules with enabled state. |
| `entity_counts` | object | Current count of entities per type. Updated periodically, not on every write. |
| `bundles` | object | Resolved bundle bindings. `null` for unresolved optional bundles. |

### Registry Operations

- **Install**: Add new entry with `installed_at` = now, `status` = `"active"`.
- **Update**: Update `package.version`, `updated_at`, `skills`, `schedules`, `bundles` as needed.
- **Uninstall**: Remove the entry entirely.
- **Disable**: Set `status` to `"disabled"`. Schedules and hooks stop firing, but data is preserved.

## Lock File

The file `upjack.lock.json` lives at `{namespace}/upjack.lock.json` and captures the complete resolved state of the app at install or update time.

### Purpose

- **Reproducibility**: Reinstalling from the lock file produces identical results.
- **Runtime reference**: The entity tools read the lock file to find entity definitions, schemas, and bundle bindings.
- **Diff source**: During updates, the installer diffs the old lock against the new manifest.

### Lock File vs Manifest

| Aspect | Manifest (`_meta`) | Lock File (`upjack.lock.json`) |
|--------|-------------------|---------------------------------|
| Version ranges | Semver ranges (e.g., `^1.0.0`) | Exact versions (e.g., `1.2.3`) |
| Bundle resolution | Default + alternatives | Single resolved package |
| Skill refs | Source references | Resolved with integrity hashes |
| Location | Inside MCPB package | In workspace at `{namespace}/` |
| Mutability | Immutable (part of package) | Written/updated by installer |

## Lifecycle State Machine

```
                        install
  (not installed) ─────────────────> active
                                       |
                          update       |  disable
                    ┌──────────────┐   |  ┌──────────────┐
                    |              |   v  v              |
                    |           active <──── disabled    |
                    |              |         |           |
                    └──────────────┘         └───────────┘
                                       |          enable
                                       |
                          uninstall    |
                                       v
                               (not installed)
```

| Transition | Trigger | What Happens |
|------------|---------|-------------|
| install | `upjack install <package>` | Full install flow |
| update | `upjack update <app>` | Diff + migrate + update |
| disable | `upjack disable <app>` | Set status, stop schedules/hooks |
| enable | `upjack enable <app>` | Restore status, restart schedules/hooks |
| uninstall | `upjack uninstall <app>` | Export + remove + clean |

## Error Recovery

### Install Failure

If installation fails at any step after scaffold:

1. All created files are removed (workspace directory cleaned).
2. No entry is added to `system/apps.json`.
3. No git commit is created.
4. The error is reported with the failing step and reason.

Installation is atomic: either the entire install succeeds or nothing changes.

### Update Failure

If update fails:

1. The workspace is restored to its pre-update state (using git).
2. The old lock file is preserved.
3. The registry entry is unchanged.
4. The error is reported.

### Uninstall with Uncommitted Changes

If the workspace has uncommitted changes when uninstall is requested:

1. The installer warns about uncommitted changes.
2. The user must confirm to proceed.
3. If confirmed, changes are committed before uninstall begins.

## Git Commit Conventions

All lifecycle operations produce git commits with a consistent format:

| Operation | Commit Message |
|-----------|---------------|
| Install | `upjack: install {package}@{version} → {namespace}` |
| Update | `upjack: update {package} {old_version} → {new_version}` |
| Uninstall | `upjack: uninstall {package}@{version} from {namespace}` |
| Disable | `upjack: disable {namespace}` |
| Enable | `upjack: enable {namespace}` |

Entity operations (performed by [runtime tools](/reference/runtime-tools/), not the installer) use a different format:

| Operation | Commit Message |
|-----------|---------------|
| Create | `{app}: create {entity_type} {id}` |
| Update | `{app}: update {entity_type} {id}` |
| Delete (soft) | `{app}: delete {entity_type} {id}` |
| Delete (hard) | `{app}: hard-delete {entity_type} {id}` |
