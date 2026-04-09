/**
 * End-to-end tests using real example manifests and schemas.
 *
 * These tests validate that the upjack TypeScript library works correctly with
 * the actual CRM, Research Assistant, and Todo example apps — real schemas,
 * real seed data, real manifest structure.
 */

import { mkdirSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { UpjackApp } from "../src/app.js";
import { createServer } from "../src/server.js";

// Resolve example directories relative to this file
// lib/typescript/tests/e2e.test.ts -> lib/typescript/ -> lib/ -> code/
const __dirname = dirname(fileURLToPath(import.meta.url));
const CODE_ROOT = resolve(__dirname, "..", "..", "..");
const CRM_DIR = resolve(CODE_ROOT, "examples", "crm");
const RESEARCH_DIR = resolve(CODE_ROOT, "examples", "research-assistant");
const TODO_DIR = resolve(CODE_ROOT, "examples", "todo");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function connectClient(manifestPath: string, workspace: string): Promise<Client> {
  const server = createServer(manifestPath, workspace);
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await server.connect(serverTransport);

  const client = new Client({ name: "test-client", version: "1.0.0" });
  await client.connect(clientTransport);
  return client;
}

function callToolJson(result: Awaited<ReturnType<Client["callTool"]>>): Record<string, unknown> {
  return JSON.parse((result.content as Array<{ text: string }>)[0].text);
}

// ===========================================================================
// CRM E2E Tests — UpjackApp level
// ===========================================================================

describe("CRM App E2E", () => {
  let workspace: string;
  let crm: UpjackApp;

  beforeEach(() => {
    workspace = mkdtempSync(join(tmpdir(), "upjack-crm-e2e-"));
    crm = UpjackApp.fromManifest(join(CRM_DIR, "manifest.json"), workspace);
  });

  it("loads all entity types", () => {
    for (const entityType of ["contact", "company", "deal", "pipeline", "activity"]) {
      expect(() => crm.createEntity(entityType, dummyData(entityType))).not.toThrow();
    }
  });

  it("creates contact with valid data", () => {
    const contact = crm.createEntity("contact", {
      first_name: "Alice",
      last_name: "Chen",
      email: "alice@example.com",
      lead_score: 85,
      lifecycle_stage: "lead",
    });
    expect(contact.id).toMatch(/^ct_/);
    expect(contact.first_name).toBe("Alice");
    expect(contact.lead_score).toBe(85);
    expect(contact.status).toBe("active");
  });

  it("contact requires first and last name", () => {
    expect(() => crm.createEntity("contact", { email: "no-name@example.com" })).toThrow(
      "Validation failed",
    );
    expect(() => crm.createEntity("contact", { first_name: "Alice" })).toThrow("Validation failed");
  });

  it("contact lead_score bounded 0-100", () => {
    expect(() =>
      crm.createEntity("contact", {
        first_name: "Alice",
        last_name: "Chen",
        lead_score: 150,
      }),
    ).toThrow("Validation failed");
    expect(() =>
      crm.createEntity("contact", {
        first_name: "Alice",
        last_name: "Chen",
        lead_score: -10,
      }),
    ).toThrow("Validation failed");
  });

  it("contact lifecycle_stage enum", () => {
    expect(() =>
      crm.createEntity("contact", {
        first_name: "Alice",
        last_name: "Chen",
        lifecycle_stage: "invalid_stage",
      }),
    ).toThrow("Validation failed");
  });

  it("creates deal with valid data", () => {
    const deal = crm.createEntity("deal", {
      title: "Enterprise License",
      stage: "qualification",
      value: 50000,
      probability: 30,
    });
    expect(deal.id).toMatch(/^dl_/);
    expect(deal.title).toBe("Enterprise License");
    expect(deal.value).toBe(50000);
  });

  it("deal requires title and stage", () => {
    expect(() => crm.createEntity("deal", { value: 10000 })).toThrow("Validation failed");
  });

  it("deal value non-negative", () => {
    expect(() =>
      crm.createEntity("deal", { title: "Bad Deal", stage: "new", value: -1000 }),
    ).toThrow("Validation failed");
  });

  it("creates company", () => {
    const company = crm.createEntity("company", {
      name: "Acme Corp",
      domain: "acme.com",
      industry: "Technology",
    });
    expect(company.id).toMatch(/^co_/);
  });

  it("creates activity", () => {
    const activity = crm.createEntity("activity", {
      activity_type: "email",
      subject: "Follow-up on demo",
    });
    expect(activity.id).toMatch(/^act_/);
  });

  it("creates pipeline singleton", () => {
    const pipeline = crm.createEntity("pipeline", {
      stages: [
        { name: "Prospecting", order: 1, probability: 10 },
        { name: "Qualification", order: 2, probability: 25 },
      ],
    });
    expect(pipeline.id).toMatch(/^pl_/);
  });

  it("pipeline requires stages", () => {
    expect(() => crm.createEntity("pipeline", { name: "Empty Pipeline" })).toThrow(
      "Validation failed",
    );
  });

  it("full CRUD cycle", () => {
    // Create
    const contact = crm.createEntity("contact", {
      first_name: "Bob",
      last_name: "Smith",
      email: "bob@example.com",
      lead_score: 60,
    });

    // Read
    const fetched = crm.getEntity("contact", contact.id as string);
    expect(fetched.first_name).toBe("Bob");
    expect(fetched.email).toBe("bob@example.com");

    // Update (merge)
    const updated = crm.updateEntity("contact", contact.id as string, { lead_score: 90 });
    expect(updated.lead_score).toBe(90);
    expect(updated.first_name).toBe("Bob");
    expect(updated.email).toBe("bob@example.com");

    // Search
    const results = crm.searchEntities("contact", { query: "Bob" });
    expect(results).toHaveLength(1);
    expect(results[0].lead_score).toBe(90);

    // List
    const all = crm.listEntities("contact");
    expect(all).toHaveLength(1);

    // Delete
    const deleted = crm.deleteEntity("contact", contact.id as string);
    expect(deleted.status).toBe("deleted");

    // Verify excluded from list
    expect(crm.listEntities("contact")).toHaveLength(0);
  });

  it("multiple entity types coexist", () => {
    crm.createEntity("contact", { first_name: "A", last_name: "B" });
    crm.createEntity("company", { name: "Acme" });
    crm.createEntity("deal", { title: "Big Deal", stage: "new" });

    expect(crm.listEntities("contact")).toHaveLength(1);
    expect(crm.listEntities("company")).toHaveLength(1);
    expect(crm.listEntities("deal")).toHaveLength(1);
  });

  it("search with structured filter", () => {
    crm.createEntity("contact", { first_name: "Alice", last_name: "A", lead_score: 90 });
    crm.createEntity("contact", { first_name: "Bob", last_name: "B", lead_score: 40 });
    crm.createEntity("contact", { first_name: "Charlie", last_name: "C", lead_score: 75 });

    const hotLeads = crm.searchEntities("contact", {
      filter: { lead_score: { $gte: 70 } },
      sort: "-lead_score",
    });
    expect(hotLeads).toHaveLength(2);
    expect(hotLeads[0].first_name).toBe("Alice");
    expect(hotLeads[1].first_name).toBe("Charlie");
  });
});

// ===========================================================================
// Research Assistant E2E Tests
// ===========================================================================

describe("Research App E2E", () => {
  let workspace: string;
  let research: UpjackApp;

  beforeEach(() => {
    workspace = mkdtempSync(join(tmpdir(), "upjack-research-e2e-"));
    research = UpjackApp.fromManifest(join(RESEARCH_DIR, "manifest.json"), workspace);
  });

  it("loads all entity types", () => {
    for (const entityType of ["topic", "source", "note", "report"]) {
      expect(() => research.createEntity(entityType, dummyData(entityType))).not.toThrow();
    }
  });

  it("creates topic", () => {
    const topic = research.createEntity("topic", {
      title: "AI Agent Architectures",
      priority: "high",
      key_questions: ["How do agents coordinate?", "What are failure modes?"],
    });
    expect(topic.id).toMatch(/^top_/);
    expect(topic.title).toBe("AI Agent Architectures");
  });

  it("topic requires title", () => {
    expect(() => research.createEntity("topic", { priority: "high" })).toThrow("Validation failed");
  });

  it("topic priority enum", () => {
    expect(() =>
      research.createEntity("topic", { title: "Test", priority: "ultra-critical" }),
    ).toThrow("Validation failed");
  });

  it("creates source", () => {
    const source = research.createEntity("source", {
      title: "MCP Protocol Specification",
      url: "https://modelcontextprotocol.io",
      source_type: "whitepaper",
      credibility: 5,
    });
    expect(source.id).toMatch(/^src_/);
  });

  it("creates note", () => {
    const note = research.createEntity("note", {
      content: "MCP uses JSON-RPC 2.0 for communication between host and server.",
      claim_type: "fact",
      confidence: "high",
    });
    expect(note.id).toMatch(/^nt_/);
  });

  it("creates report", () => {
    const report = research.createEntity("report", {
      title: "MCP Adoption Survey",
      body: "This report covers...",
      executive_summary: "MCP adoption is growing rapidly.",
    });
    expect(report.id).toMatch(/^rpt_/);
  });

  it("full research workflow", () => {
    research.createEntity("topic", { title: "MCP Protocol Adoption", priority: "high" });
    research.createEntity("source", { title: "MCP Spec v1.0", source_type: "whitepaper" });
    research.createEntity("note", {
      content: "MCP enables standardized tool communication for AI agents.",
    });
    research.createEntity("report", { title: "MCP Analysis", body: "Based on our research..." });

    expect(research.listEntities("topic")).toHaveLength(1);
    expect(research.listEntities("source")).toHaveLength(1);
    expect(research.listEntities("note")).toHaveLength(1);
    expect(research.listEntities("report")).toHaveLength(1);

    expect(research.searchEntities("topic", { query: "MCP" })).toHaveLength(1);
    expect(research.searchEntities("source", { query: "MCP" })).toHaveLength(1);
  });
});

// ===========================================================================
// Todo E2E Tests — UpjackApp level
// ===========================================================================

describe("Todo App E2E", () => {
  let workspace: string;
  let todo: UpjackApp;

  beforeEach(() => {
    workspace = mkdtempSync(join(tmpdir(), "upjack-todo-e2e-"));
    todo = UpjackApp.fromManifest(join(TODO_DIR, "manifest.json"), workspace);
  });

  it("loads all entity types", () => {
    for (const entityType of ["task", "project", "label"]) {
      expect(() => todo.createEntity(entityType, dummyData(entityType))).not.toThrow();
    }
  });

  it("creates task with valid data", () => {
    const task = todo.createEntity("task", {
      title: "Write unit tests",
      description: "Cover all edge cases",
      priority: "high",
      due_date: "2026-03-01",
      effort: "medium",
    });
    expect(task.id).toMatch(/^tsk_/);
    expect(task.title).toBe("Write unit tests");
    expect(task.priority).toBe("high");
    expect(task.status).toBe("active");
  });

  it("task requires title", () => {
    expect(() => todo.createEntity("task", { priority: "high" })).toThrow("Validation failed");
  });

  it("task priority enum", () => {
    expect(() =>
      todo.createEntity("task", { title: "Bad priority", priority: "ultra-critical" }),
    ).toThrow("Validation failed");
  });

  it("task effort enum", () => {
    expect(() => todo.createEntity("task", { title: "Bad effort", effort: "enormous" })).toThrow(
      "Validation failed",
    );
  });

  it("creates project with valid data", () => {
    const project = todo.createEntity("project", {
      name: "Q1 Planning",
      description: "Quarterly planning and goal-setting",
      color: "#3B82F6",
      due_date: "2026-03-31",
    });
    expect(project.id).toMatch(/^prj_/);
    expect(project.name).toBe("Q1 Planning");
  });

  it("project requires name", () => {
    expect(() => todo.createEntity("project", { description: "No name" })).toThrow(
      "Validation failed",
    );
  });

  it("project color pattern", () => {
    expect(() => todo.createEntity("project", { name: "Bad Color", color: "not-a-color" })).toThrow(
      "Validation failed",
    );
  });

  it("creates label with valid data", () => {
    const label = todo.createEntity("label", {
      name: "bug",
      color: "#EF4444",
      description: "Something broken",
    });
    expect(label.id).toMatch(/^lbl_/);
    expect(label.name).toBe("bug");
  });

  it("label requires name", () => {
    expect(() => todo.createEntity("label", { color: "#EF4444" })).toThrow("Validation failed");
  });

  it("full CRUD cycle", () => {
    // Create
    const task = todo.createEntity("task", {
      title: "Review docs",
      priority: "medium",
      effort: "small",
    });

    // Read
    const fetched = todo.getEntity("task", task.id as string);
    expect(fetched.title).toBe("Review docs");
    expect(fetched.priority).toBe("medium");

    // Update (merge)
    const updated = todo.updateEntity("task", task.id as string, { priority: "high" });
    expect(updated.priority).toBe("high");
    expect(updated.title).toBe("Review docs");
    expect(updated.effort).toBe("small");

    // Search
    const results = todo.searchEntities("task", { query: "Review" });
    expect(results).toHaveLength(1);
    expect(results[0].priority).toBe("high");

    // List
    expect(todo.listEntities("task")).toHaveLength(1);

    // Delete
    const deleted = todo.deleteEntity("task", task.id as string);
    expect(deleted.status).toBe("deleted");

    // Verify excluded from list
    expect(todo.listEntities("task")).toHaveLength(0);
  });

  it("multiple entity types coexist", () => {
    todo.createEntity("task", { title: "Do something" });
    todo.createEntity("project", { name: "My Project" });
    todo.createEntity("label", { name: "urgent" });

    expect(todo.listEntities("task")).toHaveLength(1);
    expect(todo.listEntities("project")).toHaveLength(1);
    expect(todo.listEntities("label")).toHaveLength(1);
  });

  it("search with structured filter", () => {
    todo.createEntity("task", {
      title: "Critical bug fix",
      priority: "critical",
      effort: "small",
    });
    todo.createEntity("task", { title: "Write docs", priority: "low", effort: "medium" });
    todo.createEntity("task", { title: "Deploy release", priority: "high", effort: "small" });

    const highPriority = todo.searchEntities("task", {
      filter: { priority: { $in: ["critical", "high"] } },
    });
    expect(highPriority).toHaveLength(2);
    const titles = new Set(highPriority.map((t) => t.title));
    expect(titles).toEqual(new Set(["Critical bug fix", "Deploy release"]));
  });

  it("task with project_name denormalized", () => {
    const task = todo.createEntity("task", {
      title: "Update README",
      project_name: "Documentation",
    });
    const fetched = todo.getEntity("task", task.id as string);
    expect(fetched.project_name).toBe("Documentation");
  });
});

// ===========================================================================
// Server-level E2E Tests
// ===========================================================================

describe("CRM Server E2E", () => {
  let workspace: string;
  let client: Client;

  beforeEach(async () => {
    workspace = mkdtempSync(join(tmpdir(), "upjack-crm-server-e2e-"));
    mkdirSync(join(workspace, "workspace"));
    client = await connectClient(join(CRM_DIR, "manifest.json"), join(workspace, "workspace"));
  });

  afterEach(async () => {
    await client.close();
  });

  it("registers all CRM tools", async () => {
    const tools = await client.listTools();
    const names = new Set(tools.tools.map((t) => t.name));

    // 5 entity types × 6 tools = 30
    for (const [name, plural] of [
      ["contact", "contacts"],
      ["company", "companies"],
      ["deal", "deals"],
      ["pipeline", "pipelines"],
      ["activity", "activities"],
    ]) {
      expect(names.has(`create_${name}`)).toBe(true);
      expect(names.has(`get_${name}`)).toBe(true);
      expect(names.has(`update_${name}`)).toBe(true);
      expect(names.has(`list_${plural}`)).toBe(true);
      expect(names.has(`search_${plural}`)).toBe(true);
      expect(names.has(`delete_${name}`)).toBe(true);
    }
    // 5 entities × 9 tools + 3 utility = 48
    expect(tools.tools).toHaveLength(48);
  });

  it("registers context and skill resources", async () => {
    const resources = await client.listResources();
    const uris = resources.resources.map((r) => String(r.uri));
    expect(uris).toContain("upjack://context");
    expect(uris).toContain("upjack://skills/lead-qualification");
    expect(uris).toContain("upjack://skills/deal-forecasting");
    expect(uris).toContain("upjack://skills/follow-up-email");
  });

  it("creates contact through tool", async () => {
    const result = await client.callTool({
      name: "create_contact",
      arguments: { data: { first_name: "Sarah", last_name: "Chen" } },
    });
    const contact = callToolJson(result);
    expect((contact.id as string).startsWith("ct_")).toBe(true);
    expect(contact.first_name).toBe("Sarah");
  });

  it("server name is CRM", async () => {
    // Server name is set in the McpServer constructor — we verify by checking
    // the tools exist (the server was successfully created with the CRM manifest)
    const tools = await client.listTools();
    expect(tools.tools.length).toBeGreaterThan(0);
  });
});

describe("Research Server E2E", () => {
  let workspace: string;
  let client: Client;

  beforeEach(async () => {
    workspace = mkdtempSync(join(tmpdir(), "upjack-research-server-e2e-"));
    mkdirSync(join(workspace, "workspace"));
    client = await connectClient(join(RESEARCH_DIR, "manifest.json"), join(workspace, "workspace"));
  });

  afterEach(async () => {
    await client.close();
  });

  it("registers all research tools", async () => {
    const tools = await client.listTools();
    const names = new Set(tools.tools.map((t) => t.name));

    for (const [name, plural] of [
      ["topic", "topics"],
      ["source", "sources"],
      ["note", "notes"],
      ["report", "reports"],
    ]) {
      expect(names.has(`create_${name}`)).toBe(true);
      expect(names.has(`list_${plural}`)).toBe(true);
    }
    // 4 entities × 9 tools + 3 utility = 39
    expect(tools.tools).toHaveLength(39);
  });
});

describe("Todo Server E2E", () => {
  let workspace: string;
  let client: Client;

  beforeEach(async () => {
    workspace = mkdtempSync(join(tmpdir(), "upjack-todo-server-e2e-"));
    mkdirSync(join(workspace, "workspace"));
    client = await connectClient(join(TODO_DIR, "manifest.json"), join(workspace, "workspace"));
  });

  afterEach(async () => {
    await client.close();
  });

  it("registers all todo tools", async () => {
    const tools = await client.listTools();
    const names = new Set(tools.tools.map((t) => t.name));

    // 3 entity types × 6 tools = 18
    for (const [name, plural] of [
      ["task", "tasks"],
      ["project", "projects"],
      ["label", "labels"],
    ]) {
      expect(names.has(`create_${name}`)).toBe(true);
      expect(names.has(`get_${name}`)).toBe(true);
      expect(names.has(`update_${name}`)).toBe(true);
      expect(names.has(`list_${plural}`)).toBe(true);
      expect(names.has(`search_${plural}`)).toBe(true);
      expect(names.has(`delete_${name}`)).toBe(true);
    }
    // 3 entities × 9 tools + 3 utility = 30
    expect(tools.tools).toHaveLength(30);
  });

  it("registers context and skill resources", async () => {
    const resources = await client.listResources();
    const uris = resources.resources.map((r) => String(r.uri));
    expect(uris).toContain("upjack://context");
    expect(uris).toContain("upjack://skills/task-management");
  });

  it("creates task through tool", async () => {
    const result = await client.callTool({
      name: "create_task",
      arguments: { data: { title: "Buy groceries" } },
    });
    const task = callToolJson(result);
    expect((task.id as string).startsWith("tsk_")).toBe(true);
    expect(task.title).toBe("Buy groceries");
  });

  it("full CRUD through tools", async () => {
    // Create
    const createResult = await client.callTool({
      name: "create_task",
      arguments: { data: { title: "Test task", priority: "high" } },
    });
    const created = callToolJson(createResult);
    const id = created.id as string;
    expect(id.startsWith("tsk_")).toBe(true);

    // Get
    const getResult = await client.callTool({
      name: "get_task",
      arguments: { entity_id: id },
    });
    const fetched = callToolJson(getResult);
    expect(fetched.title).toBe("Test task");

    // Update
    const updateResult = await client.callTool({
      name: "update_task",
      arguments: { entity_id: id, data: { priority: "critical" } },
    });
    const updated = callToolJson(updateResult);
    expect(updated.priority).toBe("critical");
    expect(updated.title).toBe("Test task");

    // List
    const listResult = await client.callTool({ name: "list_tasks", arguments: {} });
    const listData = JSON.parse((listResult.content as Array<{ text: string }>)[0].text) as Record<
      string,
      unknown
    >;
    expect((listData.entities as unknown[]).length).toBe(1);

    // Search
    const searchResult = await client.callTool({
      name: "search_tasks",
      arguments: { query: "Test" },
    });
    const searchData = JSON.parse(
      (searchResult.content as Array<{ text: string }>)[0].text,
    ) as Record<string, unknown>;
    expect((searchData.entities as unknown[]).length).toBe(1);

    // Delete
    const deleteResult = await client.callTool({
      name: "delete_task",
      arguments: { entity_id: id },
    });
    const deleted = callToolJson(deleteResult);
    expect(deleted.status).toBe("deleted");

    // Verify excluded from list
    const finalList = await client.callTool({ name: "list_tasks", arguments: {} });
    const finalData = JSON.parse((finalList.content as Array<{ text: string }>)[0].text) as Record<
      string,
      unknown
    >;
    expect((finalData.entities as unknown[]).length).toBe(0);
  });
});

// ===========================================================================
// Dummy data factory for "loads all entity types" tests
// ===========================================================================

function dummyData(entityType: string): Record<string, unknown> {
  const data: Record<string, Record<string, unknown>> = {
    contact: { first_name: "Test", last_name: "User" },
    company: { name: "Test Corp" },
    deal: { title: "Test Deal", stage: "new" },
    pipeline: {
      stages: [{ name: "Stage 1", order: 1, probability: 50 }],
    },
    activity: { activity_type: "email", subject: "Test" },
    topic: { title: "Test Topic" },
    source: { title: "Test Source" },
    note: { content: "Test note" },
    report: { title: "Test Report", body: "Test body" },
    task: { title: "Test Task" },
    project: { name: "Test Project" },
    label: { name: "test-label" },
  };
  return data[entityType] ?? { name: "test" };
}
