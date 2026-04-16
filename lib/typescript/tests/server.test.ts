import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { _buildInstructions, _prepareEntitySchema, createServer } from "../src/server.js";

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

describe("prepareEntitySchema", () => {
  it("strips base entity fields", () => {
    const schema = {
      type: "object",
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
        name: { type: "string" },
      },
      required: ["name"],
    };
    const result = _prepareEntitySchema(schema);
    expect(result.properties).toHaveProperty("name");
    expect(result.properties).not.toHaveProperty("id");
    expect(result.properties).not.toHaveProperty("type");
    expect(result.properties).not.toHaveProperty("status");
  });

  it("strips JSON Schema meta keywords", () => {
    const schema = {
      $schema: "https://json-schema.org/draft/2020-12/schema",
      $id: "https://example.com/schema",
      type: "object",
      properties: { name: { type: "string" } },
    };
    const result = _prepareEntitySchema(schema);
    expect(result).not.toHaveProperty("$schema");
    expect(result).not.toHaveProperty("$id");
    expect(result.type).toBe("object");
  });

  it("preserves required for create", () => {
    const schema = {
      type: "object",
      properties: { name: { type: "string" }, score: { type: "integer" } },
      required: ["name"],
    };
    const result = _prepareEntitySchema(schema);
    expect(result.required).toEqual(["name"]);
  });

  it("strips base fields from required", () => {
    const schema = {
      type: "object",
      properties: { id: { type: "string" }, name: { type: "string" } },
      required: ["id", "name"],
    };
    const result = _prepareEntitySchema(schema);
    expect(result.required).toEqual(["name"]);
  });

  it("removes empty required array", () => {
    const schema = {
      type: "object",
      properties: { id: { type: "string" } },
      required: ["id"],
    };
    const result = _prepareEntitySchema(schema);
    expect(result).not.toHaveProperty("required");
  });

  it("strips required for update", () => {
    const schema = {
      type: "object",
      properties: { name: { type: "string" } },
      required: ["name"],
    };
    const result = _prepareEntitySchema(schema, { forUpdate: true });
    expect(result).not.toHaveProperty("required");
  });

  it("preserves nested structure", () => {
    const schema = {
      type: "object",
      properties: {
        emotional_drivers: {
          type: "object",
          properties: {
            fear: {
              type: "object",
              properties: {
                theme: { type: "string" },
                trigger: { type: "string" },
              },
              required: ["theme", "trigger"],
            },
          },
        },
        scoring_signals: {
          type: "array",
          items: {
            type: "object",
            properties: { signal: { type: "string" }, points: { type: "integer" } },
            required: ["signal", "points"],
          },
        },
      },
    };
    const result = _prepareEntitySchema(schema) as Record<string, unknown>;
    const props = result.properties as Record<string, Record<string, unknown>>;
    const fear = (props.emotional_drivers.properties as Record<string, Record<string, unknown>>)
      .fear;
    expect(fear.required).toEqual(["theme", "trigger"]);
    const items = props.scoring_signals.items as Record<string, unknown>;
    expect(items.required).toEqual(["signal", "points"]);
  });

  it("does not mutate original", () => {
    const schema = {
      $schema: "https://json-schema.org/draft/2020-12/schema",
      type: "object",
      properties: { id: { type: "string" }, name: { type: "string" } },
      required: ["id", "name"],
    };
    _prepareEntitySchema(schema);
    expect(schema).toHaveProperty("$schema");
    expect(schema.properties).toHaveProperty("id");
    expect(schema.required).toContain("id");
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
  it("registers 9 entity tools + utility tools per entity", async () => {
    const manifestPath = makeManifest(tmpDir, [
      { name: "widget", plural: "widgets", prefix: "wg" },
    ]);
    const client = await connectClient(manifestPath, workspace);
    const tools = await client.listTools();
    const names = new Set(tools.tools.map((t) => t.name));

    // 6 CRUD + 3 relationship + 2 utility (add_field, rebuild_index)
    expect(names).toContain("create_widget");
    expect(names).toContain("get_widget");
    expect(names).toContain("update_widget");
    expect(names).toContain("list_widgets");
    expect(names).toContain("search_widgets");
    expect(names).toContain("delete_widget");
    expect(names).toContain("query_widgets_by_relationship");
    expect(names).toContain("get_related_widget");
    expect(names).toContain("get_widget_composite");
    expect(names).toContain("add_field");
    expect(names).toContain("rebuild_index");
    await client.close();
  });

  it("registers tools for multiple entity types", async () => {
    const manifestPath = makeManifest(tmpDir, [
      { name: "contact", plural: "contacts", prefix: "ct" },
      { name: "deal", plural: "deals", prefix: "dl" },
    ]);
    const client = await connectClient(manifestPath, workspace);
    const tools = await client.listTools();

    // 9 per entity * 2 + 2 utility = 20
    const names = new Set(tools.tools.map((t) => t.name));
    expect(names.has("create_contact")).toBe(true);
    expect(names.has("search_deals")).toBe(true);
    expect(names.has("query_contacts_by_relationship")).toBe(true);
    expect(names.has("get_related_deal")).toBe(true);
    await client.close();
  });
});

describe("tool input schemas", () => {
  it("create tool exposes entity fields at top level (no data wrapper)", async () => {
    const entitySchema = {
      $schema: "https://json-schema.org/draft/2020-12/schema",
      type: "object",
      properties: {
        id: { type: "string" },
        type: { type: "string" },
        name: { type: "string", description: "Campaign name" },
        score: { type: "integer", minimum: 0, maximum: 100 },
        emotional_drivers: {
          type: "object",
          properties: {
            fear: { type: "object", properties: { theme: { type: "string" } } },
          },
        },
      },
      required: ["name"],
    };

    const manifestPath = makeManifest(tmpDir, [
      { name: "campaign", plural: "campaigns", prefix: "cp" },
    ]);
    writeFileSync(join(tmpDir, "schemas", "campaign.schema.json"), JSON.stringify(entitySchema));
    const client = await connectClient(manifestPath, workspace);
    const tools = await client.listTools();
    const createTool = tools.tools.find((t) => t.name === "create_campaign");
    expect(createTool).toBeDefined();
    const inputSchema = createTool?.inputSchema;
    const props = inputSchema?.properties as Record<string, Record<string, unknown>>;

    // No `data` wrapper — fields are flat at the top level
    expect(props).not.toHaveProperty("data");
    expect(props.name.description).toBe("Campaign name");
    expect(props.score.minimum).toBe(0);
    // Nested structure preserved
    const drivers = props.emotional_drivers;
    expect((drivers.properties as Record<string, Record<string, unknown>>).fear).toBeDefined();
    // Base fields stripped
    expect(props).not.toHaveProperty("id");
    expect(props).not.toHaveProperty("type");
    // $schema stripped at top level
    expect(inputSchema).not.toHaveProperty("$schema");
    // Required preserved (minus base fields)
    expect(inputSchema?.required).toEqual(["name"]);

    await client.close();
  });

  it("update tool has flat fields and entity id, no data wrapper", async () => {
    const entitySchema = {
      $schema: "https://json-schema.org/draft/2020-12/schema",
      type: "object",
      properties: {
        name: { type: "string" },
        score: { type: "integer" },
      },
      required: ["name"],
    };

    const manifestPath = makeManifest(tmpDir, [{ name: "item", plural: "items", prefix: "it" }]);
    writeFileSync(join(tmpDir, "schemas", "item.schema.json"), JSON.stringify(entitySchema));
    const client = await connectClient(manifestPath, workspace);
    const tools = await client.listTools();
    const updateTool = tools.tools.find((t) => t.name === "update_item");
    expect(updateTool).toBeDefined();
    const inputSchema = updateTool?.inputSchema;
    const props = inputSchema?.properties as Record<string, Record<string, unknown>>;

    // Flat: item_id + fields at top level, no `data` wrapper
    expect(props).not.toHaveProperty("data");
    expect(props).toHaveProperty("item_id");
    expect(props).toHaveProperty("name");
    expect(props).toHaveProperty("score");
    // Only the id is required (partial-merge semantics for everything else)
    expect(inputSchema?.required).toEqual(["item_id"]);

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
      arguments: { name: "Widget" },
    });
    const created = JSON.parse((createResult.content as Array<{ text: string }>)[0].text);
    expect(created.id.startsWith("it_")).toBe(true);
    expect(created.name).toBe("Widget");

    const getResult = await client.callTool({
      name: "get_item",
      arguments: { item_id: created.id },
    });
    const fetched = JSON.parse((getResult.content as Array<{ text: string }>)[0].text);
    expect(fetched.id).toBe(created.id);
  });

  it("update merges fields", async () => {
    const createResult = await client.callTool({
      name: "create_item",
      arguments: { name: "Old" },
    });
    const created = JSON.parse((createResult.content as Array<{ text: string }>)[0].text);

    const updateResult = await client.callTool({
      name: "update_item",
      arguments: { item_id: created.id, name: "New", extra: "field" },
    });
    const updated = JSON.parse((updateResult.content as Array<{ text: string }>)[0].text);
    expect(updated.name).toBe("New");
    expect(updated.extra).toBe("field");
  });

  it("list returns created entities in envelope", async () => {
    await client.callTool({ name: "create_item", arguments: { name: "A" } });
    await client.callTool({ name: "create_item", arguments: { name: "B" } });

    const listResult = await client.callTool({ name: "list_items", arguments: {} });
    const result = JSON.parse((listResult.content as Array<{ text: string }>)[0].text);
    expect(result.entities).toHaveLength(2);
    expect(result.count).toBe(2);
  });

  it("search finds by text in envelope", async () => {
    await client.callTool({ name: "create_item", arguments: { name: "Alpha" } });
    await client.callTool({ name: "create_item", arguments: { name: "Beta" } });

    const searchResult = await client.callTool({
      name: "search_items",
      arguments: { query: "Alpha" },
    });
    const result = JSON.parse((searchResult.content as Array<{ text: string }>)[0].text);
    expect(result.entities).toHaveLength(1);
    expect(result.entities[0].name).toBe("Alpha");
  });

  it("soft delete", async () => {
    const createResult = await client.callTool({
      name: "create_item",
      arguments: { name: "Doomed" },
    });
    const created = JSON.parse((createResult.content as Array<{ text: string }>)[0].text);

    const deleteResult = await client.callTool({
      name: "delete_item",
      arguments: { item_id: created.id },
    });
    const deleted = JSON.parse((deleteResult.content as Array<{ text: string }>)[0].text);
    expect(deleted.status).toBe("deleted");

    const listResult = await client.callTool({ name: "list_items", arguments: {} });
    const result = JSON.parse((listResult.content as Array<{ text: string }>)[0].text);
    expect(result.entities).toHaveLength(0);
  });

  it("legacy {data: {...}} shape is rejected", async () => {
    // 0.5.0 removed the data wrapper. A call using the old shape is missing
    // the required `name` field at the top level, so the schema validator
    // rejects it rather than silently succeeding.
    const result = await client.callTool({
      name: "create_item",
      arguments: { data: { name: "Wrapped" } },
    });
    expect(result.isError).toBeTruthy();
  });
});

describe("JSON string deserialization", () => {
  // Raw Server bypasses SDK's Zod deserialization — object arguments may
  // arrive as JSON strings over stdio transport.  The server must handle both.

  let client: Client;

  beforeEach(async () => {
    const manifestPath = makeManifest(tmpDir, [{ name: "item", plural: "items", prefix: "it" }]);
    client = await connectClient(manifestPath, workspace);
  });

  afterEach(async () => {
    await client.close();
  });

  it("create works when array arg arrives as a JSON string", async () => {
    // Over stdio transport, nested arrays/objects can arrive as JSON-serialized
    // strings. The server parses these transparently.
    const relsStr = JSON.stringify([{ rel: "belongs_to", target: "it_abc" }]);
    const result = await client.callTool({
      name: "create_item",
      arguments: { name: "StringWidget", relationships: relsStr },
    });
    const created = JSON.parse((result.content as Array<{ text: string }>)[0].text);
    expect(created.name).toBe("StringWidget");
    expect(Array.isArray(created.relationships)).toBe(true);
    expect(created.relationships[0].rel).toBe("belongs_to");
  });

  it("update works when object arg arrives as a JSON string", async () => {
    const createResult = await client.callTool({
      name: "create_item",
      arguments: { name: "Original" },
    });
    const created = JSON.parse((createResult.content as Array<{ text: string }>)[0].text);

    const detailStr = JSON.stringify({ nested: "value" });
    const updateResult = await client.callTool({
      name: "update_item",
      arguments: { item_id: created.id, name: "Updated", detail: detailStr },
    });
    const updated = JSON.parse((updateResult.content as Array<{ text: string }>)[0].text);
    expect(updated.name).toBe("Updated");
    expect(updated.detail).toEqual({ nested: "value" });
  });

  it("search works when filter is a JSON string", async () => {
    await client.callTool({
      name: "create_item",
      arguments: { name: "Findme" },
    });

    const searchResult = await client.callTool({
      name: "search_items",
      arguments: { filter: JSON.stringify({ name: "Findme" }) },
    });
    const result = JSON.parse((searchResult.content as Array<{ text: string }>)[0].text);
    expect(result.entities).toHaveLength(1);
    expect(result.entities[0].name).toBe("Findme");
  });

  it("plain string args are not mangled", async () => {
    const createResult = await client.callTool({
      name: "create_item",
      arguments: { name: "Test" },
    });
    const created = JSON.parse((createResult.content as Array<{ text: string }>)[0].text);

    const getResult = await client.callTool({
      name: "get_item",
      arguments: { item_id: created.id },
    });
    const fetched = JSON.parse((getResult.content as Array<{ text: string }>)[0].text);
    expect(fetched.id).toBe(created.id);
  });

  it("dict args still work (normal in-process path)", async () => {
    const result = await client.callTool({
      name: "create_item",
      arguments: { name: "DictWidget" },
    });
    const created = JSON.parse((result.content as Array<{ text: string }>)[0].text);
    expect(created.name).toBe("DictWidget");
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

describe("tool listing filter", () => {
  it("tools array filters listed tools", async () => {
    const manifestPath = makeManifest(tmpDir, [
      { name: "session", plural: "sessions", prefix: "ss", tools: ["get", "search"] },
    ]);
    const client = await connectClient(manifestPath, workspace);
    const tools = await client.listTools();
    const names = new Set(tools.tools.map((t) => t.name));

    // Only get + search for session, plus utility tools
    expect(names.has("get_session")).toBe(true);
    expect(names.has("search_sessions")).toBe(true);
    expect(names.has("create_session")).toBe(false);
    expect(names.has("query_sessions_by_relationship")).toBe(false);

    // Hidden tools are still callable
    const result = await client.callTool({
      name: "create_session",
      arguments: { name: "Test" },
    });
    expect(result.isError).toBeFalsy();

    await client.close();
  });

  it("no tools array lists all entity + utility tools", async () => {
    const manifestPath = makeManifest(tmpDir, [
      { name: "widget", plural: "widgets", prefix: "wg" },
    ]);
    const client = await connectClient(manifestPath, workspace);
    const tools = await client.listTools();
    const names = new Set(tools.tools.map((t) => t.name));

    // All 9 entity tools + utility tools
    expect(names.has("create_widget")).toBe(true);
    expect(names.has("query_widgets_by_relationship")).toBe(true);
    expect(names.has("add_field")).toBe(true);
    expect(names.has("rebuild_index")).toBe(true);
    await client.close();
  });

  it("mixed tools arrays across entities", async () => {
    const manifestPath = makeManifest(tmpDir, [
      { name: "session", plural: "sessions", prefix: "ss", tools: ["get"] },
      { name: "bookmark", plural: "bookmarks", prefix: "bk" },
    ]);
    const client = await connectClient(manifestPath, workspace);
    const tools = await client.listTools();
    const names = new Set(tools.tools.map((t) => t.name));

    // session: only get
    expect(names.has("get_session")).toBe(true);
    expect(names.has("create_session")).toBe(false);

    // bookmark: all 6
    expect(names.has("create_bookmark")).toBe(true);
    expect(names.has("delete_bookmark")).toBe(true);

    await client.close();
  });

  it("empty tools array lists no entity tools", async () => {
    const manifestPath = makeManifest(tmpDir, [
      { name: "session", plural: "sessions", prefix: "ss", tools: [] },
    ]);
    const client = await connectClient(manifestPath, workspace);
    const tools = await client.listTools();
    const names = new Set(tools.tools.map((t) => t.name));

    // No session tools listed
    const sessionTools = [...names].filter((n) => n.includes("session"));
    expect(sessionTools).toEqual([]);

    // But tools are still callable
    const result = await client.callTool({
      name: "create_session",
      arguments: { name: "Test" },
    });
    expect(result.isError).toBeFalsy();

    await client.close();
  });
});

describe("add_field tool", () => {
  let client: Awaited<ReturnType<typeof connectClient>>;

  beforeEach(async () => {
    const manifestPath = makeManifest(tmpDir, [
      { name: "widget", plural: "widgets", prefix: "wg" },
    ]);
    client = await connectClient(manifestPath, workspace);
  });

  afterEach(async () => {
    await client.close();
  });

  it("adds a new field to entity schema", async () => {
    const result = await client.callTool({
      name: "add_field",
      arguments: {
        entity_type: "widget",
        field_name: "priority",
        field_type: "string",
        default: "medium",
        description: "Priority level",
      },
    });
    const parsed = JSON.parse((result.content as Array<{ text: string }>)[0].text);
    expect(parsed.success).toBe(true);
    expect(parsed.field.name).toBe("priority");
    expect(parsed.field.type).toBe("string");
    expect(parsed.field.default).toBe("medium");
  });

  it("new field is usable after add", async () => {
    await client.callTool({
      name: "add_field",
      arguments: {
        entity_type: "widget",
        field_name: "color",
        field_type: "string",
        default: "blue",
      },
    });

    // Create an entity — the new field should be accepted
    const createResult = await client.callTool({
      name: "create_widget",
      arguments: { name: "Test", color: "red" },
    });
    const created = JSON.parse((createResult.content as Array<{ text: string }>)[0].text);
    expect(created.color).toBe("red");
  });

  it("rejects invalid field name", async () => {
    const result = await client.callTool({
      name: "add_field",
      arguments: {
        entity_type: "widget",
        field_name: "BadName",
        field_type: "string",
        default: "",
      },
    });
    const parsed = JSON.parse((result.content as Array<{ text: string }>)[0].text);
    expect(parsed.error).toContain("Invalid field_name");
  });

  it("rejects reserved field name", async () => {
    const result = await client.callTool({
      name: "add_field",
      arguments: {
        entity_type: "widget",
        field_name: "status",
        field_type: "string",
        default: "active",
      },
    });
    const parsed = JSON.parse((result.content as Array<{ text: string }>)[0].text);
    expect(parsed.error).toContain("reserved base entity field");
  });

  it("rejects invalid field type", async () => {
    const result = await client.callTool({
      name: "add_field",
      arguments: {
        entity_type: "widget",
        field_name: "score",
        field_type: "float",
        default: 0,
      },
    });
    const parsed = JSON.parse((result.content as Array<{ text: string }>)[0].text);
    expect(parsed.error).toContain("Invalid field_type");
  });

  it("rejects type mismatch between default and field_type", async () => {
    const result = await client.callTool({
      name: "add_field",
      arguments: {
        entity_type: "widget",
        field_name: "count",
        field_type: "integer",
        default: "not a number",
      },
    });
    const parsed = JSON.parse((result.content as Array<{ text: string }>)[0].text);
    expect(parsed.error).toContain("not compatible with type");
  });

  it("rejects duplicate field", async () => {
    const result = await client.callTool({
      name: "add_field",
      arguments: {
        entity_type: "widget",
        field_name: "name",
        field_type: "string",
        default: "",
      },
    });
    const parsed = JSON.parse((result.content as Array<{ text: string }>)[0].text);
    expect(parsed.error).toContain("already exists");
  });

  it("rejects unknown entity type", async () => {
    const result = await client.callTool({
      name: "add_field",
      arguments: {
        entity_type: "nonexistent",
        field_name: "foo",
        field_type: "string",
        default: "",
      },
    });
    const parsed = JSON.parse((result.content as Array<{ text: string }>)[0].text);
    expect(parsed.error).toContain("Unknown entity type");
  });
});
