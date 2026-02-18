import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { _buildInstructions, _describeSchemaFields, createServer } from "../src/server.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeManifest(
  tmpDir: string,
  entities: Array<Record<string, unknown>>,
  opts: {
    context?: string;
    skills?: Array<Record<string, unknown>>;
    seed?: Record<string, unknown>;
    displayName?: string;
  } = {},
): string {
  const schemasDir = join(tmpDir, "schemas");
  mkdirSync(schemasDir, { recursive: true });

  for (const ent of entities) {
    const schema = {
      $schema: "https://json-schema.org/draft/2020-12/schema",
      type: "object",
      properties: { name: { type: "string" } },
      required: ["name"],
    };
    const schemaFile = `schemas/${ent.name}.schema.json`;
    writeFileSync(join(tmpDir, schemaFile), JSON.stringify(schema));
    if (!ent.schema) ent.schema = schemaFile;
  }

  const upjack: Record<string, unknown> = {
    upjack_version: "0.1",
    namespace: "test",
    display: { name: opts.displayName ?? "Test App" },
    entities: [...entities],
  };
  if (opts.context) upjack.context = opts.context;
  if (opts.skills) upjack.skills = opts.skills;
  if (opts.seed) upjack.seed = opts.seed;

  const manifest = {
    manifest_version: "0.4",
    name: "test-app",
    version: "1.0.0",
    title: "Test App",
    server: null,
    _meta: { "ai.nimblebrain/upjack": upjack },
  };

  const manifestPath = join(tmpDir, "manifest.json");
  writeFileSync(manifestPath, JSON.stringify(manifest));
  return manifestPath;
}

async function connectClient(manifestPath: string, workspace: string): Promise<Client> {
  const server = createServer(manifestPath, workspace);
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await server.connect(serverTransport);

  const client = new Client({ name: "test-client", version: "1.0.0" });
  await client.connect(clientTransport);
  return client;
}

// ---------------------------------------------------------------------------
// Unit tests for pure functions
// ---------------------------------------------------------------------------

describe("describeSchemaFields", () => {
  it("returns empty for null", () => {
    expect(_describeSchemaFields(undefined)).toBe("");
  });

  it("returns empty for no properties", () => {
    expect(_describeSchemaFields({})).toBe("");
    expect(_describeSchemaFields({ properties: {} })).toBe("");
  });

  it("skips base entity fields", () => {
    const schema = {
      properties: {
        id: { type: "string" },
        type: { type: "string" },
        version: { type: "integer" },
        created_at: { type: "string" },
        updated_at: { type: "string" },
        created_by: { type: "string" },
        status: { type: "string" },
        tags: { type: "array" },
        source: { type: "object" },
        relationships: { type: "array" },
      },
    };
    expect(_describeSchemaFields(schema)).toBe("");
  });

  it("separates required and optional", () => {
    const schema = {
      properties: { name: { type: "string" }, score: { type: "integer" } },
      required: ["name"],
    };
    const result = _describeSchemaFields(schema);
    expect(result).toContain("Required fields:");
    expect(result).toContain("name (string)");
    expect(result).toContain("Optional fields:");
    expect(result).toContain("score (integer)");
  });

  it("includes enum, min, max, format, description", () => {
    const schema = {
      properties: {
        priority: { type: "string", enum: ["low", "high"] },
        score: { type: "integer", minimum: 0, maximum: 100, description: "Lead score" },
        email: { type: "string", format: "email" },
      },
    };
    const result = _describeSchemaFields(schema);
    expect(result).toContain("one of:");
    expect(result).toContain("min: 0");
    expect(result).toContain("max: 100");
    expect(result).toContain("Lead score");
    expect(result).toContain("format: email");
  });
});

describe("buildInstructions", () => {
  it("includes app name and entity count", () => {
    const upjack = {
      upjack_version: "0.1",
      namespace: "test",
      display: { name: "My CRM" },
      entities: [
        { name: "contact", prefix: "ct", schema: "s" },
        { name: "deal", prefix: "dl", schema: "s" },
      ],
    };
    const result = _buildInstructions(upjack);
    expect(result).toContain("My CRM");
    expect(result).toContain("2 entity types");
    expect(result).toContain("contact (ct_)");
    expect(result).toContain("deal (dl_)");
  });

  it("adds context hint when present", () => {
    const upjack = {
      upjack_version: "0.1",
      namespace: "test",
      display: { name: "App" },
      entities: [],
      context: "context.md",
    };
    expect(_buildInstructions(upjack)).toContain("upjack://context");
  });

  it("no context hint when absent", () => {
    const upjack = {
      upjack_version: "0.1",
      namespace: "test",
      display: { name: "App" },
      entities: [],
    };
    expect(_buildInstructions(upjack)).not.toContain("upjack://context");
  });
});

// ---------------------------------------------------------------------------
// Integration tests
// ---------------------------------------------------------------------------

let tmpDir: string;
let workspace: string;

beforeEach(() => {
  tmpDir = mkdtempSync(join(tmpdir(), "upjack-server-"));
  workspace = join(tmpDir, "workspace");
  mkdirSync(workspace);
});

describe("createServer", () => {
  it("registers 6 tools per entity", async () => {
    const manifestPath = makeManifest(tmpDir, [
      { name: "widget", plural: "widgets", prefix: "wg" },
    ]);
    const client = await connectClient(manifestPath, workspace);
    const tools = await client.listTools();
    const names = new Set(tools.tools.map((t) => t.name));

    expect(names).toEqual(
      new Set([
        "create_widget",
        "get_widget",
        "update_widget",
        "list_widgets",
        "search_widgets",
        "delete_widget",
      ]),
    );
    await client.close();
  });

  it("registers tools for multiple entity types", async () => {
    const manifestPath = makeManifest(tmpDir, [
      { name: "contact", plural: "contacts", prefix: "ct" },
      { name: "deal", plural: "deals", prefix: "dl" },
    ]);
    const client = await connectClient(manifestPath, workspace);
    const tools = await client.listTools();

    expect(tools.tools).toHaveLength(12);
    const names = new Set(tools.tools.map((t) => t.name));
    expect(names.has("create_contact")).toBe(true);
    expect(names.has("search_deals")).toBe(true);
    await client.close();
  });
});

describe("tool CRUD", () => {
  let client: Client;

  beforeEach(async () => {
    const manifestPath = makeManifest(tmpDir, [{ name: "item", plural: "items", prefix: "it" }]);
    client = await connectClient(manifestPath, workspace);
  });

  afterEach(async () => {
    await client.close();
  });

  it("create + get roundtrip", async () => {
    const createResult = await client.callTool({
      name: "create_item",
      arguments: { data: { name: "Widget" } },
    });
    const created = JSON.parse((createResult.content as Array<{ text: string }>)[0].text);
    expect(created.id.startsWith("it_")).toBe(true);
    expect(created.name).toBe("Widget");

    const getResult = await client.callTool({
      name: "get_item",
      arguments: { entity_id: created.id },
    });
    const fetched = JSON.parse((getResult.content as Array<{ text: string }>)[0].text);
    expect(fetched.id).toBe(created.id);
  });

  it("update merges fields", async () => {
    const createResult = await client.callTool({
      name: "create_item",
      arguments: { data: { name: "Old" } },
    });
    const created = JSON.parse((createResult.content as Array<{ text: string }>)[0].text);

    const updateResult = await client.callTool({
      name: "update_item",
      arguments: { entity_id: created.id, data: { name: "New", extra: "field" } },
    });
    const updated = JSON.parse((updateResult.content as Array<{ text: string }>)[0].text);
    expect(updated.name).toBe("New");
    expect(updated.extra).toBe("field");
  });

  it("list returns created entities", async () => {
    await client.callTool({ name: "create_item", arguments: { data: { name: "A" } } });
    await client.callTool({ name: "create_item", arguments: { data: { name: "B" } } });

    const listResult = await client.callTool({ name: "list_items", arguments: {} });
    const items = JSON.parse((listResult.content as Array<{ text: string }>)[0].text);
    expect(items).toHaveLength(2);
  });

  it("search finds by text", async () => {
    await client.callTool({ name: "create_item", arguments: { data: { name: "Alpha" } } });
    await client.callTool({ name: "create_item", arguments: { data: { name: "Beta" } } });

    const searchResult = await client.callTool({
      name: "search_items",
      arguments: { query: "Alpha" },
    });
    const results = JSON.parse((searchResult.content as Array<{ text: string }>)[0].text);
    expect(results).toHaveLength(1);
    expect(results[0].name).toBe("Alpha");
  });

  it("soft delete", async () => {
    const createResult = await client.callTool({
      name: "create_item",
      arguments: { data: { name: "Doomed" } },
    });
    const created = JSON.parse((createResult.content as Array<{ text: string }>)[0].text);

    const deleteResult = await client.callTool({
      name: "delete_item",
      arguments: { entity_id: created.id },
    });
    const deleted = JSON.parse((deleteResult.content as Array<{ text: string }>)[0].text);
    expect(deleted.status).toBe("deleted");

    const listResult = await client.callTool({ name: "list_items", arguments: {} });
    const items = JSON.parse((listResult.content as Array<{ text: string }>)[0].text);
    expect(items).toHaveLength(0);
  });
});

describe("resources", () => {
  it("registers context resource", async () => {
    writeFileSync(join(tmpDir, "context.md"), "# CRM Knowledge\nThis is context.");
    const manifestPath = makeManifest(tmpDir, [{ name: "item", plural: "items", prefix: "it" }], {
      context: "context.md",
    });
    const client = await connectClient(manifestPath, workspace);
    const resources = await client.listResources();
    const uris = resources.resources.map((r) => r.uri);
    expect(uris).toContain("upjack://context");

    const content = await client.readResource({ uri: "upjack://context" });
    expect((content.contents[0] as { text: string }).text).toContain("CRM Knowledge");
    await client.close();
  });

  it("registers skill resources", async () => {
    const skillDir = join(tmpDir, "skills", "lead-qual");
    mkdirSync(skillDir, { recursive: true });
    writeFileSync(join(skillDir, "SKILL.md"), "# Lead Qualification\nScore leads 0-100.");

    const manifestPath = makeManifest(tmpDir, [{ name: "item", plural: "items", prefix: "it" }], {
      skills: [{ source: "bundled", path: "skills/lead-qual/SKILL.md" }],
    });
    const client = await connectClient(manifestPath, workspace);
    const resources = await client.listResources();
    const uris = resources.resources.map((r) => r.uri);
    expect(uris).toContain("upjack://skills/lead-qual");
    await client.close();
  });

  it("skips non-bundled skills", async () => {
    const manifestPath = makeManifest(tmpDir, [{ name: "item", plural: "items", prefix: "it" }], {
      skills: [{ source: "mpak", name: "@external/skill", version: "^1.0" }],
    });
    const client = await connectClient(manifestPath, workspace);
    // When no resources are registered, the MCP SDK doesn't enable the resources
    // capability, so listResources() throws "Method not found". This is expected.
    try {
      const resources = await client.listResources();
      const uris = resources.resources.map((r) => String(r.uri));
      expect(uris.some((u) => u.includes("skills"))).toBe(false);
    } catch (err: unknown) {
      // "Method not found" means no resources capability — no skills registered, which is correct
      expect(String(err)).toContain("Method not found");
    }
    await client.close();
  });

  it("skips missing context file", async () => {
    const manifestPath = makeManifest(tmpDir, [{ name: "item", plural: "items", prefix: "it" }], {
      context: "nonexistent.md",
    });
    const client = await connectClient(manifestPath, workspace);
    try {
      const resources = await client.listResources();
      const uris = resources.resources.map((r) => String(r.uri));
      expect(uris).not.toContain("upjack://context");
    } catch (err: unknown) {
      // "Method not found" means no resources capability — context not registered, which is correct
      expect(String(err)).toContain("Method not found");
    }
    await client.close();
  });
});
