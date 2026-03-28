import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListResourcesRequestSchema,
  ListToolsRequestSchema,
  ReadResourceRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { UpjackApp } from "./app.js";
import type { UpjackManifestExtension } from "./app.js";

// Base entity fields auto-managed by the framework — stripped from tool input schemas
const BASE_ENTITY_KEYS = new Set([
  "id",
  "type",
  "version",
  "created_at",
  "updated_at",
  "created_by",
  "status",
  "tags",
  "source",
  "relationships",
]);

// ---------------------------------------------------------------------------
// Schema preparation
// ---------------------------------------------------------------------------

interface JsonSchema {
  type?: string;
  properties?: Record<string, unknown>;
  required?: string[];
  $schema?: string;
  $id?: string;
  [key: string]: unknown;
}

function prepareEntitySchema(schema: JsonSchema, opts?: { forUpdate?: boolean }): JsonSchema {
  // Strip JSON Schema meta keywords not applicable inside tool input
  const { $schema: _, $id: __, ...result } = structuredClone(schema);

  if (result.properties) {
    result.properties = Object.fromEntries(
      Object.entries(result.properties).filter(([k]) => !BASE_ENTITY_KEYS.has(k)),
    );
  }

  if (opts?.forUpdate) {
    // Updates are partial merges — all fields optional
    const { required: _req, ...rest } = result;
    return rest;
  }

  if (result.required) {
    const filtered = result.required.filter((r) => !BASE_ENTITY_KEYS.has(r));
    if (filtered.length === 0) {
      const { required: _req, ...rest } = result;
      return rest;
    }
    result.required = filtered;
  }

  return result;
}

// ---------------------------------------------------------------------------
// Tool definition builders
// ---------------------------------------------------------------------------

interface ToolDefinition {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

type ToolHandler = (args: Record<string, unknown>) => unknown;

function buildEntityTools(
  app: UpjackApp,
  entityDef: { name: string; plural?: string; prefix: string; schema: string },
  schema: Record<string, unknown> | undefined,
): { definitions: ToolDefinition[]; handlers: Record<string, ToolHandler> } {
  const name = entityDef.name;
  const plural = entityDef.plural ?? `${name}s`;
  const prefix = entityDef.prefix;
  const idHint = `IDs start with ${prefix}_`;

  const dataSchema = schema ? prepareEntitySchema(schema as JsonSchema) : { type: "object" };
  const updateDataSchema = schema
    ? prepareEntitySchema(schema as JsonSchema, { forUpdate: true })
    : { type: "object" };

  const definitions: ToolDefinition[] = [
    {
      name: `create_${name}`,
      description: `Create a new ${name}. ${idHint}.`,
      inputSchema: {
        type: "object",
        properties: { data: dataSchema },
        required: ["data"],
      },
    },
    {
      name: `get_${name}`,
      description: `Get a ${name} by ID. ${idHint}.`,
      inputSchema: {
        type: "object",
        properties: {
          entity_id: { type: "string", description: `${name} ID (${prefix}_...)` },
        },
        required: ["entity_id"],
      },
    },
    {
      name: `update_${name}`,
      description: `Update a ${name} by ID. Merges fields by default. ${idHint}.`,
      inputSchema: {
        type: "object",
        properties: {
          entity_id: { type: "string", description: `${name} ID (${prefix}_...)` },
          data: updateDataSchema,
        },
        required: ["entity_id", "data"],
      },
    },
    {
      name: `list_${plural}`,
      description: `List ${plural}. Filters by status (default: active). Returns newest first. ${idHint}.`,
      inputSchema: {
        type: "object",
        properties: {
          status: { type: "string", default: "active", description: "Status filter" },
          limit: { type: "number", default: 50, description: "Max results" },
        },
      },
    },
    {
      name: `search_${plural}`,
      description: `Search ${plural} with text query and/or structured filters. Text query matches across all string fields (case-insensitive). Filters support: direct equality, $gt, $gte, $lt, $lte, $ne, $in, $contains, $exists. Sort with '-field' for descending. ${idHint}.`,
      inputSchema: {
        type: "object",
        properties: {
          query: { type: "string", description: "Text search query" },
          filter: { type: "object", description: "Structured filters" },
          sort: { type: "string", default: "-updated_at", description: "Sort field" },
          limit: { type: "number", default: 20, description: "Max results" },
        },
      },
    },
    {
      name: `delete_${name}`,
      description:
        `Delete a ${name} by ID. Soft delete by default (sets status to 'deleted'). ` +
        `Set hard=true to permanently remove. ${idHint}.`,
      inputSchema: {
        type: "object",
        properties: {
          entity_id: { type: "string", description: `${name} ID` },
          hard: { type: "boolean", default: false, description: "Hard delete" },
        },
        required: ["entity_id"],
      },
    },
  ];

  const handlers: Record<string, ToolHandler> = {
    [`create_${name}`]: (args) =>
      app.createEntity(name, (args.data ?? {}) as Record<string, unknown>),
    [`get_${name}`]: (args) => app.getEntity(name, args.entity_id as string),
    [`update_${name}`]: (args) =>
      app.updateEntity(
        name,
        args.entity_id as string,
        (args.data ?? {}) as Record<string, unknown>,
      ),
    [`list_${plural}`]: (args) =>
      app.listEntities(name, (args.status as string) ?? "active", (args.limit as number) ?? 50),
    [`search_${plural}`]: (args) =>
      app.searchEntities(name, {
        query: args.query as string | undefined,
        filter: args.filter as Record<string, unknown> | undefined,
        sort: (args.sort as string) ?? "-updated_at",
        limit: (args.limit as number) ?? 20,
      }),
    [`delete_${name}`]: (args) =>
      app.deleteEntity(name, args.entity_id as string, (args.hard as boolean) ?? false),
  };

  return { definitions, handlers };
}

// ---------------------------------------------------------------------------
// Resource builders
// ---------------------------------------------------------------------------

interface ResourceDefinition {
  uri: string;
  name: string;
  description: string;
}

type ResourceReader = () => string;

function buildResources(
  manifestDir: string,
  upjack: UpjackManifestExtension,
): { definitions: ResourceDefinition[]; readers: Record<string, ResourceReader> } {
  const definitions: ResourceDefinition[] = [];
  const readers: Record<string, ResourceReader> = {};

  // Context resource
  const contextFile = upjack.context;
  if (contextFile) {
    const contextPath = join(manifestDir, contextFile);
    try {
      readFileSync(contextPath, "utf-8"); // Check it exists
      definitions.push({
        uri: "upjack://context",
        name: "Context",
        description: "App domain knowledge",
      });
      readers["upjack://context"] = () => readFileSync(contextPath, "utf-8");
    } catch {
      // Context file doesn't exist — skip
    }
  }

  // Skill resources
  for (const skill of upjack.skills ?? []) {
    if (skill.source !== "bundled") continue;
    const skillPath = join(manifestDir, skill.path);
    try {
      readFileSync(skillPath, "utf-8"); // Check it exists
      const skillName = skillPath.split("/").slice(-2, -1)[0];
      const uri = `upjack://skills/${skillName}`;
      definitions.push({
        uri,
        name: skillName,
        description: `Skill: ${skillName}`,
      });
      readers[uri] = () => readFileSync(skillPath, "utf-8");
    } catch {
      // Skill file doesn't exist — skip
    }
  }

  return { definitions, readers };
}

// ---------------------------------------------------------------------------
// Instructions
// ---------------------------------------------------------------------------

function buildInstructions(upjack: UpjackManifestExtension): string {
  const appName = upjack.display?.name ?? "App";
  const entities = upjack.entities ?? [];
  const summaries = entities.map((e) => `${e.name} (${e.prefix}_)`);

  let instructions = `${appName} with ${entities.length} entity types: ${summaries.join(", ")}.`;

  if (upjack.context) {
    instructions += "\nRead the upjack://context resource for domain knowledge.";
  }

  return instructions;
}

// ---------------------------------------------------------------------------
// Server factory
// ---------------------------------------------------------------------------

/**
 * Create an MCP server from an Upjack manifest.
 *
 * Uses the low-level Server class directly so entity JSON Schemas can be
 * passed as raw tool inputSchema — no Zod conversion, no translation layer.
 *
 * @param manifestPath - Path to manifest.json.
 * @param root - Workspace root directory.
 * @returns Configured Server instance.
 */
export function createServer(manifestPath: string, root?: string): Server {
  const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
  const manifestDir = dirname(manifestPath);

  const upjack = (manifest._meta?.["ai.nimblebrain/upjack"] ?? {}) as UpjackManifestExtension;
  const appName = upjack.display?.name ?? manifest.title ?? "Upjack App";

  const app = UpjackApp.fromManifest(manifestPath, root);

  // Collect all tool definitions and handlers
  const allDefinitions: ToolDefinition[] = [];
  const allHandlers: Record<string, ToolHandler> = {};

  for (const entityDef of upjack.entities ?? []) {
    const schema = app._schemas[entityDef.name];
    const { definitions, handlers } = buildEntityTools(app, entityDef, schema);
    allDefinitions.push(...definitions);
    Object.assign(allHandlers, handlers);
  }

  // Collect resources
  const { definitions: resourceDefs, readers: resourceReaders } = buildResources(
    manifestDir,
    upjack,
  );

  // Determine capabilities
  const capabilities: Record<string, Record<string, unknown>> = {};
  if (allDefinitions.length > 0) capabilities.tools = {};
  if (resourceDefs.length > 0) capabilities.resources = {};

  // Create the low-level Server — raw JSON Schema, no Zod
  const server = new Server(
    { name: appName, version: manifest.version ?? "0.1.0" },
    { capabilities, instructions: buildInstructions(upjack) },
  );

  // tools/list — return tool definitions with raw entity JSON Schema
  if (allDefinitions.length > 0) {
    server.setRequestHandler(ListToolsRequestSchema, () => ({
      tools: allDefinitions,
    }));

    // tools/call — dispatch to the right entity operation
    server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;
      const handler = allHandlers[name];
      if (!handler) {
        return {
          content: [{ type: "text" as const, text: `Tool ${name} not found` }],
          isError: true,
        };
      }
      // Raw Server bypasses SDK's Zod deserialization —
      // object arguments may arrive as JSON strings over stdio transport
      const parsed: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(args ?? {})) {
        if (typeof v === "string" && (v.startsWith("{") || v.startsWith("["))) {
          try {
            parsed[k] = JSON.parse(v);
          } catch {
            parsed[k] = v;
          }
        } else {
          parsed[k] = v;
        }
      }
      try {
        const result = handler(parsed);
        return {
          content: [{ type: "text" as const, text: JSON.stringify(result) }],
        };
      } catch (err) {
        return {
          content: [
            { type: "text" as const, text: err instanceof Error ? err.message : String(err) },
          ],
          isError: true,
        };
      }
    });
  }

  // resources/list + resources/read
  if (resourceDefs.length > 0) {
    server.setRequestHandler(ListResourcesRequestSchema, () => ({
      resources: resourceDefs,
    }));

    server.setRequestHandler(ReadResourceRequestSchema, (request) => {
      const uri = request.params.uri;
      const reader = resourceReaders[uri];
      if (!reader) {
        throw new Error(`Resource not found: ${uri}`);
      }
      return {
        contents: [{ uri, text: reader() }],
      };
    });
  }

  return server;
}

/**
 * Start the MCP server with stdio transport.
 */
export async function startServer(manifestPath: string, root?: string): Promise<void> {
  const server = createServer(manifestPath, root);
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

// Export for testing
export { prepareEntitySchema as _prepareEntitySchema, buildInstructions as _buildInstructions };
