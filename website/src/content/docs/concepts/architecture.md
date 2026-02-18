---
title: Architecture
description: "Design philosophy, core concepts, runtime architecture, and how Upjack relates to MCPB, mpak, and MCP."
draft: false
---

## Overview

The NimbleBrain Upjack Framework is a system for building declarative AI-native applications. Apps are standard MCPB packages with an upjack extension in `_meta["ai.nimblebrain/upjack"]`. There is no fork of the MCPB spec. Upjack is purely an extension layer.

An Upjack app declares **what** it needs (entity schemas, skills, bundle dependencies, schedules, hooks) and the `upjack` library handles **how** those declarations are realized at runtime: storage, validation, ID generation, and search. Add FastMCP to serve it as a standalone MCP server.

## Design Philosophy

### Declarative-First

Apps are defined by data, not code. A manifest declares entity schemas, skill references, bundle dependencies, and runtime behavior. The library interprets these declarations. Most apps require zero custom code beyond a server entry point.

### Schema-Driven

Every entity conforms to a JSON Schema (draft 2020-12). Schemas are composed via `allOf`: a base entity schema provides common fields (`id`, `type`, `version`, `created_at`, `updated_at`), and the app schema adds domain-specific fields. Validation is enforced at write time. No invalid data enters the workspace.

### Git-Friendly

All entity data lives as JSON files, one file per entity in a structured directory layout. The layout is optimized for git-backed workflows: the hosting platform (such as NimbleBrain) commits each write, providing a complete audit trail, branch-based workflows, and natural conflict resolution. The `upjack` library handles file I/O; git integration is a platform-level concern.

### Skills Over Code

Domain expertise lives in Markdown skill files, not Python or JavaScript. Skills describe procedures, decision criteria, qualification rubrics, and domain knowledge in natural language. The agent reads skills to understand how to operate the app. Code is reserved for cases where declarative schemas and skills are insufficient.

## Core Concepts

### Upjack App

An Upjack app is an installable MCPB package that defines a domain-specific application (CRM, research tracker, content pipeline). It contains:

- A **manifest** describing entities, skills, dependencies, and runtime behavior
- **Entity schemas** (JSON Schema files) defining data structures
- **Skills** (Markdown files) encoding domain expertise
- Optionally, a **custom MCP server** for business logic beyond CRUD

### Entity

An entity is a typed data record conforming to a JSON Schema. Every entity has a type-prefixed ULID identifier (e.g., `ld_01HZ3QKBN9YWVJ0RPFA7MT8C5X`), base metadata fields, and domain-specific fields defined by the app schema. Entities are stored as individual JSON files in the workspace.

See [Entity Model](/reference/entity-model/) for the full entity specification.

### Skill

A skill is a Markdown document that encodes domain expertise for the agent. Skills describe procedures (how to qualify a lead), decision criteria (when to escalate a deal), templates (email follow-up format), and domain knowledge (industry terminology). Skills are installed into the workspace and referenced by the agent during reasoning.

### Bundle Dependency

A bundle dependency is an external MCPB package that provides MCP tools the app needs. Dependencies are declared by **alias** (e.g., `email`) rather than by specific package name, enabling swappability. The manifest specifies a default package, alternative packages, and the specific tools used, forming a compatibility contract.

See [Bundles & Skills](/reference/bundles-and-skills/) for the full dependency specification.

### View

A view is a named, pre-filtered perspective on entities. Views define a filter expression (JSONPath), sort order, and storage location. The platform materializes views for efficient access (e.g., "my open deals sorted by close date").

### Hook

A hook is a reactive trigger that fires a skill when an entity lifecycle event occurs. Supported events include entity creation, update, deletion, and status changes, as well as app-level events (installed, updated). Hooks can be filtered by entity type and conditional expressions.

### Schedule

A schedule is a cron-based trigger that runs a skill at regular intervals. Schedules enable periodic workflows like weekly pipeline reviews, daily research digests, or monthly reporting.

## Architecture

The Upjack runtime follows a linear flow from manifest to MCP server:

```
manifest.json
    |
    v
[upjack library]
    |-- reads manifest and entity definitions
    |-- loads and composes JSON Schemas (base + app via allOf)
    |-- provides UpjackApp with entity CRUD operations
    |
    v
[MCP Server (FastMCP / MCP SDK)]
    create_server(manifest) / createServer(manifest) generates:
        create_{entity}, get_{entity}, update_{entity},
        list_{plural}, search_{plural}, delete_{entity}
    + context and skill resources
    |
    v
[Agent Reasoning]
    Agent reads skills, uses entity tools,
    invokes bundle tools via alias routing
```

**Standalone usage:** Import `UpjackApp` directly for entity management without an MCP server. See [Runtime Tools](/reference/runtime-tools/) for tool specifications. Both [Python](/libraries/python/) and [TypeScript](/libraries/typescript/) libraries provide identical functionality.

## What the Library Handles vs. What a Runtime Handles

The `upjack` library provides the core entity engine. Manifest fields like hooks, schedules, views, and bundle resolution are declarative metadata. They describe *desired* runtime behavior but require a hosting runtime to act on them. Any runtime that reads the manifest can implement these features; the NimbleBrain platform is one such runtime.

| Feature | `upjack` library | Hosting runtime |
|---------|---------------------|-----------------|
| Entity CRUD (create, get, update, list, delete) | Yes | Yes |
| Schema validation (JSON Schema 2020-12) | Yes | Yes |
| Full-text search and structured filters | Yes | Yes |
| MCP server generation (`create_server()`) | Yes | Yes |
| Git commits on entity writes | No (file I/O only) | Yes |
| Hook dispatch (react to entity events) | No (manifest metadata) | Yes |
| Schedule execution (cron triggers) | No (manifest metadata) | Yes |
| View materialization (named queries) | No (manifest metadata) | Yes |
| Bundle dependency resolution | No (manifest metadata) | Yes |
| App lifecycle (install, update, uninstall) | No | Yes |

When using `upjack` standalone, hooks, schedules, views, and bundle declarations are stored in the manifest and available for inspection, but they have no effect unless a runtime interprets them.

## Relationship to Existing Systems

### MCPB

The Model Context Protocol Bundle (MCPB) spec defines a standard package format for MCP servers. Upjack apps **are** MCPB packages. They include a valid `manifest.json` with the standard MCPB fields (`name`, `version`, `description`, `mcp_config`, etc.). The upjack extension lives entirely within `_meta["ai.nimblebrain/upjack"]`, which MCPB treats as opaque vendor metadata. Non-NimbleBrain tools can install an Upjack app as a regular MCP server and simply ignore the extension.

### mpak

mpak is the MCPB package registry. Upjack apps are published to mpak like any other bundle. The mpak registry indexes them, and the mpak CLI can download and install them. The NimbleBrain platform's installer adds the Upjack-specific scaffolding on top of standard mpak installation.

### MCP (Model Context Protocol)

MCP is the underlying protocol for tool communication. Upjack apps may include a custom MCP server, and bundle dependencies are MCP servers. The `upjack` library's `create_server()` function generates a FastMCP server that exposes entity CRUD tools over MCP. Upjack does not modify or extend the MCP protocol itself.

### NimbleBrain Platform (Optional)

Upjack apps can run standalone or on the NimbleBrain agent platform. The platform adds workspace management (git-backed repos), schedule execution, hook dispatch, and bundle routing. These are optional. An Upjack app works as a standalone MCP server without the platform.

## Why This Approach

**Apps define WHAT; the library handles HOW.**

Traditional application frameworks require developers to write storage layers, validation logic, API endpoints, and deployment configuration. Upjack inverts this: the app author declares entity schemas and domain expertise, and the library provides storage (JSON files), validation (JSON Schema), search, and MCP tool generation.

1. **AI agents reason about structure.** Schemas and skills give the agent a clear, typed understanding of the domain. The agent knows what fields a lead has, what "qualified" means, and how to follow up, all from declarative definitions.

2. **Git is the database.** When backed by a platform that commits each write, entity changes become audit trails, branching, and rollback. No database to manage, no migrations to run. The tradeoff: git-backed JSON works for hundreds to low thousands of entities. High-volume or low-latency workloads need a real database.

3. **Skills are the differentiator.** The value of a CRM app is not CRUD operations. It is the qualification criteria, the follow-up procedures, the industry knowledge. Skills capture this in a form the agent can use directly. The risk is that poorly written skills produce poor agent behavior, and debugging "the skill was ambiguous" is a different problem than debugging code.

4. **Swappable dependencies.** Aliasing bundle dependencies makes apps portable across email providers, search engines, and other services. The compatibility contract (`tools_used`) catches mismatches at install time, not at runtime.

5. **Fast onboarding.** Install an app, seed data, and the agent is operational. The scope is intentionally narrow: structured-data apps where the entity count stays manageable and the value is in domain expertise, not data volume.
