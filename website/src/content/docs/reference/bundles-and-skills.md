---
title: "Bundles & Skills"
description: "How Upjack apps declare external capabilities through bundle dependencies and encode domain expertise in skills."
draft: false
---

:::note[Library vs. platform]
The `upjack` library reads bundled skill files and serves them as MCP resources. Dependency resolution, alias routing, platform tools, and connection management are platform-level features implemented by the NimbleBrain runtime.
:::

## Overview

Upjack apps declare external capabilities through three dependency layers: platform tools, connections, and bundle dependencies. Domain expertise is encoded in skills. This document specifies how dependencies are declared, resolved, and routed at runtime.

## Three Dependency Layers

| Layer | What It Provides | Declaration | Resolution |
|-------|-----------------|-------------|------------|
| **Platform tools** | Always-available capabilities (web search, file operations) | `required_tools[]` | Pre-installed by platform |
| **Connections** | OAuth/API access to external services (Google, LinkedIn) | `required_connections[]` | User configures in settings |
| **Bundle dependencies** | MCP tools from MCPB packages (email, enrichment) | `bundles{}` | Installed during app install |

### Platform Tools

Platform tools are capabilities provided by the NimbleBrain platform itself. They are always available and do not require installation. Apps declare which platform tools they depend on for documentation and compatibility checking.

```json
{
  "required_tools": [
    "platform:web_search",
    "platform:file_read",
    "platform:git_commit"
  ]
}
```

The `platform:` prefix distinguishes these from bundle tools. The installer verifies that the platform version supports all declared tools.

### Connections

Connections are user-configured OAuth or API credentials for external services. The app declares what connections it needs and whether they are required or optional.

```json
{
  "required_connections": [
    {
      "type": "google-workspace",
      "required": true,
      "purpose": "Access Google Calendar for meeting scheduling"
    },
    {
      "type": "linkedin",
      "required": false,
      "purpose": "Enrich lead profiles with LinkedIn data"
    }
  ]
}
```

If a required connection is not configured, the installer warns the user. The app can still be installed, but functionality depending on the connection will not work until the user completes the connection setup.

### Bundle Dependencies

Bundle dependencies are MCPB packages that provide MCP tools. They are the most complex dependency layer and are detailed in the sections below.

## Bundle Dependencies

### Alias-Based Declaration

Bundle dependencies are declared by **logical alias**, not by package name. Alias-based declaration is the key design decision enabling swappability.

```json
{
  "bundles": {
    "email": {
      "description": "Email sending capability",
      "default": { "name": "@nimblebrain/aws-ses", "version": "^1.0.0" },
      "alternatives": [
        { "name": "@nimblebrain/sendgrid", "version": "^1.0.0" }
      ],
      "tools_used": ["send_email", "list_templates"]
    }
  }
}
```

In this example, `email` is the alias. The app does not hardcode a dependency on AWS SES or SendGrid. It depends on the `email` capability. The user (or admin) can choose which concrete package fulfills that capability.

### Alias Routing

At runtime, tools are referenced through their alias using a double-underscore convention:

```
{alias}__{tool_name}
```

Skills and the agent reference `email__send_email`, not `aws-ses__send_email`. The platform's tool router resolves the alias to the currently bound package and dispatches the call.

**Examples:**

| Alias Reference | Resolved To (if default) |
|----------------|------------------------|
| `email__send_email` | `@nimblebrain/aws-ses` > `send_email` |
| `email__list_templates` | `@nimblebrain/aws-ses` > `list_templates` |
| `enrichment__enrich_company` | `@nimblebrain/clearbit` > `enrich_company` |

### Compatibility Contract

The `tools_used` array is the compatibility contract between the app and any package that fulfills the alias. It lists every tool name the app will invoke through this alias.

```json
{
  "tools_used": ["send_email", "list_templates"]
}
```

**During installation**, the installer checks that the chosen package exposes all tools listed in `tools_used`. If any tool is missing, installation fails with an explicit error:

```
Error: Bundle "email" resolved to @nimblebrain/sendgrid@1.2.0,
but it does not expose tool "list_templates".
Required tools: send_email, list_templates
Available tools: send_email, send_template_email
```

The check ensures that alternative packages are actually compatible before they are used.

### Bundle Dependency Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `description` | string | Yes | — | Human-readable purpose of this dependency. |
| `required` | boolean | No | `true` | Whether the app can function without this bundle. |
| `default` | object | Yes | — | Default package reference. |
| `default.name` | string | Yes | — | MCPB package name. |
| `default.version` | string | Yes | — | Semver range. |
| `alternatives` | array | No | `[]` | Alternative packages that satisfy the same contract. |
| `tools_used` | array | Yes | — | Tool names the app invokes through this alias. minItems: 1. |
| `config_map` | object | No | `{}` | Configuration keys the bundle expects, with descriptions as values. |

### Required vs Optional Bundles

When `required: true` (the default), the installer ensures a package is resolved and its tools are available before completing installation. When `required: false`, the app can be installed without the bundle. Tools invoked through the alias will return an error at runtime if the bundle is not configured.

```json
{
  "enrichment": {
    "description": "Company and contact data enrichment",
    "required": false,
    "default": { "name": "@nimblebrain/clearbit", "version": "^0.2.0" },
    "tools_used": ["enrich_company", "enrich_person"]
  }
}
```

### Configuration Map

The `config_map` documents configuration keys the bundle expects. These are passed to the bundle's MCP server as environment variables or configuration at startup.

```json
{
  "config_map": {
    "from_address": "Default sender email address",
    "reply_to": "Reply-to address for outbound emails"
  }
}
```

The installer prompts the user for these values during installation if they are not already configured.

## Skill References

Skills encode domain expertise in Markdown. They are referenced in the manifest and installed into the workspace during app installation.

### Three Skill Sources

#### mpak

Skills published as mpak packages. Versioned, integrity-checked, distributed through the mpak registry.

```json
{
  "source": "mpak",
  "name": "@nimblebrain/lead-qualification",
  "version": "^1.0.0",
  "integrity": "sha256-abc123..."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | string | Yes | Const `"mpak"`. |
| `name` | string | Yes | Scoped name. Pattern: `^@[a-z0-9-]+/[a-z0-9-]+$` |
| `version` | string | Yes | Semver range. |
| `integrity` | string | No | SHA-256 hash for content verification. |

#### GitHub

Skills hosted in GitHub repositories. Useful for shared skill libraries and community contributions.

```json
{
  "source": "github",
  "repo": "NimbleBrainInc/skills",
  "path": "sales/lead-qualification.md",
  "ref": "v1.2.0"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | string | Yes | Const `"github"`. |
| `repo` | string | Yes | GitHub repo in `owner/repo` format. |
| `path` | string | Yes | Path to skill file within the repo. |
| `ref` | string | No | Git ref (branch, tag, SHA). Defaults to default branch. |

#### Bundled

Skills included directly in the MCPB package. The simplest option for app-specific expertise.

```json
{
  "source": "bundled",
  "path": "skills/deal-review.md"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | string | Yes | Const `"bundled"`. |
| `path` | string | Yes | Relative path within the package to the SKILL.md file. |

### Skill Installation

Skills are installed into the workspace under the app's namespace with an **app-prefixed name** using a double-dash convention:

```
{namespace}/skills/{app}--{skill-name}.md
```

**Examples:**

| Skill | Installed Path |
|-------|---------------|
| CRM lead qualification | `apps/crm/skills/crm--lead-qualification.md` |
| CRM deal review | `apps/crm/skills/crm--deal-review.md` |
| CRM objection handling | `apps/crm/skills/crm--objection-handling.md` |

The double-dash prefix (`crm--`) prevents name collisions when multiple apps install skills into the same workspace. The agent discovers skills by scanning the workspace skills directory.

### Skill File Format

Skills are Markdown documents. There is no enforced structure, but the recommended format includes:

```markdown
# Lead Qualification

## Purpose
Evaluate incoming leads and assign a qualification score.

## Criteria
- **Budget**: Does the lead have purchasing authority?
- **Need**: Does the lead have a clear use case?
- **Timeline**: Is there urgency?
- **Fit**: Does the lead match our ICP?

## Scoring
- 80-100: Hot lead, prioritize immediate outreach
- 60-79: Warm lead, schedule follow-up within 48 hours
- 40-59: Cool lead, add to nurture sequence
- 0-39: Cold lead, archive

## Procedure
1. Review the lead's company and title
2. Check for existing relationship (search companies)
3. Score each criterion 0-25
4. Sum scores and set `score` field
5. Update `stage` based on score threshold
6. If score >= 60, create a follow-up activity
```

## Resolution and Lock File

During installation, all dependencies are resolved to exact versions and recorded in `upjack.lock.json`:

```json
{
  "resolved_at": "2026-02-15T10:30:00Z",
  "bundles": {
    "email": {
      "resolved": "@nimblebrain/aws-ses",
      "version": "1.2.3",
      "integrity": "sha256-def456..."
    }
  },
  "skills": [
    {
      "name": "lead-qualification",
      "source": "bundled",
      "path": "skills/lead-qualification.md",
      "integrity": "sha256-ghi789..."
    },
    {
      "name": "objection-handling",
      "source": "github",
      "repo": "NimbleBrainInc/skills",
      "path": "sales/objection-handling.md",
      "ref": "v1.2.0",
      "resolved_sha": "abc123def456..."
    }
  ]
}
```

The lock file ensures reproducible installations. Subsequent installs (or reinstalls) use the locked versions unless explicitly updated. See [Lifecycle](/reference/lifecycle/) for details on lock file management during install, update, and uninstall.

## Intentionally Undefined

The following dependency features are explicitly out of scope:

| Feature | Reason |
|---------|--------|
| **Transitive dependencies** | Bundle A depending on Bundle B. Adds significant complexity to resolution. Defer until real-world usage demonstrates need. |
| **Version conflict resolution** | Two apps requiring incompatible versions of the same bundle. Rare in practice (single-app workspaces are the norm). |
| **Capability interfaces** | Abstract interface definitions (e.g., "EmailProvider") that packages can implement. Premature abstraction. `tools_used` provides sufficient compatibility checking. |
| **Skill versioning** | Semantic versioning for bundled skills. Skills are Markdown and change semantically, not structurally. Pin by content hash or git ref instead. |
| **Bundle hot-swap** | Changing the bound package for an alias without reinstalling the app. Requires careful state migration. |

These features may be added in future versions as the ecosystem matures.
