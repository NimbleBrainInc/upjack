---
title: Thesis
description: "Why AI-native applications are fundamentally different from traditional software, and why that demands a new framework."
draft: false
---

## The State of Things

Software applications have been built the same way for decades. A developer writes code that defines behavior: if this, then that. The code is compiled, deployed, and run on a server. Users interact through interfaces that were designed in advance. Every capability the application has was anticipated, specified, and implemented by a human.

This model assumes the runtime is dumb. The server executes instructions. It does not understand the domain. It does not reason about what to do next. It does not know the difference between a qualified lead and a tire kicker. Every decision that requires judgment must be encoded as logic (`if lead_score > 80 and last_contacted < 14_days_ago`) or delegated back to the user through a UI.

The result: applications are expensive to build, rigid once built, and generic by default. A CRM knows what a contact is but has no opinion on how to qualify one. A project tracker knows what a task is but has no sense of priority. The intelligence lives in the heads of the people using the software, not in the software itself.

AI changes the runtime.

## The Shift

Large language models introduced something new to computing: a runtime that can reason. Not just execute. Reason. An agent can read a lead qualification rubric, understand it, and apply it to a specific contact with specific context. It can read a follow-up email template and adapt it for a deal that stalled at the negotiation stage. It can look at a research methodology and apply it across dozens of sources, synthesizing what it finds.

That changes what an "application" needs to be.

When the runtime is dumb, the application must encode every decision as code. When the runtime can reason, the application only needs to provide two things:

1. **Structure**: what entities exist, what fields they have, how they relate
2. **Expertise**: how to think about the domain, what good looks like, what procedures to follow

Everything else (storage, validation, retrieval, indexing) is mechanical. The agent already knows how to read files, call tools, and chain operations. What it lacks is domain structure: what a "deal" is, what "qualification" means, what stages a pipeline has, when to follow up.

Upjack provides that structure.

## What an Upjack App Is

An Upjack app is not software in the traditional sense. There is no compiled binary. There is no server to deploy. There is no API to call.

An Upjack app is a **domain blueprint**: a package of schemas, skills, and declarations that gives an AI agent a mental model for a specific domain.

- **Schemas** describe what the data looks like: what fields a contact has, what's required, what's optional. JSON Schema, draft 2020-12. Strict types. Validation at write time. The agent cannot create a contact without a name, cannot set a lead score above 100, cannot skip the ID.

- **Skills** encode domain expertise in Markdown: how to qualify a lead, when to escalate a deal, what makes a good follow-up email, how to evaluate research sources. Natural language. No code. The agent reads these and understands how to operate in the domain.

- **Declarations** wire the runtime: what tools the app needs, what connections it requires, when schedules should fire, what hooks trigger on data changes. The platform interprets these at install time and configures accordingly.

Together, these three layers (structure, expertise, wiring) constitute an application that an AI agent can operate. No procedural business logic. No imperative code. No event handlers. The agent reads the schemas and knows what data to create. It reads the skills and knows how to reason about the domain. The platform provides the mechanical operations (CRUD, search, indexing, git commits) automatically.

## Why This Is Better (and Where It Isn't)

### Domain experts become app builders

The most valuable CRM is not the one with the best code. It's the one with the best qualification criteria, the best follow-up procedures, the best pipeline definitions. That expertise has traditionally been trapped in people's heads or buried in wikis that no software can act on.

Upjack makes domain expertise the product. A sales leader who knows how to qualify leads can write a skill that teaches an agent to qualify leads. No Python. No JavaScript. No APIs. Just structured knowledge that an agent can act on.

The cost of building an application drops from "hire a development team" to "describe your domain well."

The catch: this only works if the domain expert can describe their domain clearly. Bad skills produce bad agent behavior, the same way bad code produces bad software. The failure mode shifts from "the code has a bug" to "the skill is ambiguous," which is a different kind of problem to debug.

### The app does the thinking

Traditional applications are inert containers. They store data and present it. The user provides all the intelligence: deciding which leads to pursue, which deals to escalate, which research sources are credible.

An Upjack app embeds that intelligence in skills. The agent scores leads using criteria from the qualification skill. It drafts follow-up emails when deals go stale. It evaluates source credibility against the methodology. The app participates in the work instead of just holding data.

### Git is the database

Every entity in an Upjack app is a JSON file in a git repository. Every create, update, and delete is a commit.

- **Audit trail**: Who changed this lead score? When? Why? `git log` tells you.
- **Branching**: Want to try a different pipeline structure? Branch, experiment, merge or discard. Try that with Postgres.
- **Portability**: The entire application state is a directory of JSON files. Copy it, grep it, version it. No proprietary format.
- **Transparency**: Users can inspect every entity. No hidden state. No "contact your admin."

No database to manage, no migrations to run, no replication to configure. Git already solved versioning, collaboration, and conflict resolution.

The tradeoff is scale. Git-backed JSON files work well for hundreds or low thousands of entities. If you need millions of records or sub-millisecond queries, this is the wrong tool. Upjack is designed for domain-specific apps where the entity count stays manageable and the value is in the skills, not the data volume.

### Schemas as contracts, dependencies as aliases

In traditional apps, the data model is implicit, scattered across ORM definitions, API schemas, frontend types, and database migrations that may or may not agree with each other.

In an Upjack app, the JSON Schema is the single source of truth. The schema defines what's valid. The runtime enforces it at write time. When the schema changes, the version number increments and old records can be lazily migrated. No big-bang migrations. No downtime.

Dependencies work similarly. Apps declare them by alias, not by package name. An app says "I need an email sender," not "I need AWS SES." Switch providers by changing one line in the manifest. The skills and schemas stay the same.

## How Upjack Apps Differ from Conventional Applications

| Dimension | Conventional Application | Upjack App |
|-----------|------------------------|-------------|
| **Built from** | Code (Python, JS, SQL) | Schemas (JSON Schema) + Skills (Markdown) |
| **Business logic** | Procedural code, event handlers | Natural language skills the agent interprets |
| **Runtime** | Dumb server executing instructions | AI agent reasoning over structure and expertise |
| **Storage** | Database (Postgres, MongoDB, etc.) | Git-backed JSON files |
| **Data model** | Implicit (scattered across ORM, API, frontend) | Explicit JSON Schema, single source of truth |
| **Validation** | Code-level checks, middleware | Schema enforcement at write time |
| **API** | Custom REST/GraphQL endpoints | 6 universal entity tools (create, get, update, list, search, delete) |
| **Deployment** | Server provisioning, CI/CD, infrastructure | `install` (the platform handles the rest) |
| **Updates** | Database migrations, downtime, rollbacks | Schema version bump, lazy migration, git history |
| **Who can build** | Developers | Anyone who can describe a domain well |
| **Intelligence** | In the user's head | In the skills the agent reads |
| **Audit trail** | Logging middleware (if built) | Automatic (every change is a git commit) |
| **Extensibility** | Write more code | Write more skills, add more schemas |

## The Three Tiers

Not every app needs the same level of complexity. Upjack provides three tiers:

**Tier 1: Schemas + Skills.** Define your entities and write your expertise. No code. The agent reads the schemas to understand data structure and the skills to understand domain procedures. CRMs, trackers, knowledge bases, and research tools all fit here.

**Tier 2: Runtime Tools.** Automatic for any app with entities. The platform adds six universal tools (entity_create, entity_get, entity_update, entity_list, entity_search, entity_delete) that handle validation, ID generation, storage, indexing, and git commits. The app author writes nothing. These tools are derived from the manifest.

**Tier 3: Custom Server.** For apps that need computed fields, batch operations, external API integrations, or complex validation. Write a custom Python or TypeScript MCP server using the `upjack` library. The escape hatch, not the default.

The remarkable thing about an intelligent runtime is how much can be expressed without code.

## The Deeper Argument

The software industry has spent decades building increasingly sophisticated tools to help developers write code faster: frameworks, ORMs, code generators, CI/CD pipelines, infrastructure-as-code. All of it assumes that code is the medium.

But code was never the point. The point was always the domain knowledge: what a qualified lead looks like, when a deal needs attention, how to evaluate a research source. Code was just the only way to make a computer act on that knowledge.

AI agents change the equation. An agent can read a skill file that says "leads with decision-maker titles, recent engagement, and companies over 50 employees score 70-100" and apply that criteria as effectively as a hardcoded scoring function. More effectively, in some cases, because it can handle edge cases, weigh context, and explain its reasoning.

When the runtime can reason, the medium shifts from code to knowledge. The app author's job is no longer "implement the logic" but "describe the domain." The people best equipped to describe a domain are the people who work in it, not the developers hired to translate their knowledge into if-statements.

Upjack is a bet on that shift. Write schemas. Write skills. Let the runtime handle the plumbing. It won't replace every application, but for the class of problems where domain expertise matters more than custom logic, it changes who can build and how fast they can ship.
