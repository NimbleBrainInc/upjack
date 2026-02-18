import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { UpjackApp } from "./app.js";
import type { UpjackManifestExtension } from "./app.js";

function describeSchemaFields(schema: Record<string, unknown> | undefined): string {
  if (!schema) return "";

  const props = (schema.properties ?? {}) as Record<string, Record<string, unknown>>;
  const required = new Set((schema.required ?? []) as string[]);

  const baseKeys = new Set([
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

  const reqFields: string[] = [];
  const optFields: string[] = [];

  for (const [name, prop] of Object.entries(props)) {
    if (baseKeys.has(name)) continue;

    const ptype = (prop.type as string) ?? "any";
    const parts = [`${name} (${ptype})`];

    if (prop.enum) parts.push(`one of: ${JSON.stringify(prop.enum)}`);
    if (prop.minimum !== undefined) parts.push(`min: ${prop.minimum}`);
    if (prop.maximum !== undefined) parts.push(`max: ${prop.maximum}`);
    if (prop.format) parts.push(`format: ${prop.format}`);
    if (prop.description) parts.push(prop.description as string);

    const desc = parts.join(" — ");
    if (required.has(name)) {
      reqFields.push(desc);
    } else {
      optFields.push(desc);
    }
  }

  const lines: string[] = [];
  if (reqFields.length) lines.push(`Required fields: ${reqFields.join("; ")}`);
  if (optFields.length) lines.push(`Optional fields: ${optFields.join("; ")}`);
  return lines.join(". ");
}

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

function registerEntityTools(
  server: McpServer,
  app: UpjackApp,
  entityDef: { name: string; plural?: string; prefix: string; schema: string },
  schema: Record<string, unknown> | undefined,
): void {
  const name = entityDef.name;
  const plural = entityDef.plural ?? `${name}s`;
  const prefix = entityDef.prefix;

  const fieldDesc = describeSchemaFields(schema);
  const idHint = `IDs start with ${prefix}_`;

  // create_{name}
  const createDesc = `Create a new ${name}. ${idHint}.${fieldDesc ? ` ${fieldDesc}.` : ""}`;
  server.tool(
    `create_${name}`,
    createDesc,
    { data: z.record(z.string(), z.unknown()).describe(`Fields for the new ${name}`) },
    ({ data }) => ({
      content: [{ type: "text", text: JSON.stringify(app.createEntity(name, data)) }],
    }),
  );

  // get_{name}
  server.tool(
    `get_${name}`,
    `Get a ${name} by ID. ${idHint}.`,
    { entity_id: z.string().describe(`${name} ID (${prefix}_...)`) },
    ({ entity_id }) => ({
      content: [{ type: "text", text: JSON.stringify(app.getEntity(name, entity_id)) }],
    }),
  );

  // update_{name}
  const updateDesc = `Update a ${name} by ID. Merges fields by default. ${idHint}.${fieldDesc ? ` ${fieldDesc}.` : ""}`;
  server.tool(
    `update_${name}`,
    updateDesc,
    {
      entity_id: z.string().describe(`${name} ID`),
      data: z.record(z.string(), z.unknown()).describe("Fields to update"),
    },
    ({ entity_id, data }) => ({
      content: [
        {
          type: "text",
          text: JSON.stringify(app.updateEntity(name, entity_id, data)),
        },
      ],
    }),
  );

  // list_{plural}
  server.tool(
    `list_${plural}`,
    `List ${plural}. Filters by status (default: active). Returns newest first. ${idHint}.`,
    {
      status: z.string().optional().default("active").describe("Status filter"),
      limit: z.number().optional().default(50).describe("Max results"),
    },
    ({ status, limit }) => ({
      content: [
        {
          type: "text",
          text: JSON.stringify(app.listEntities(name, status, limit)),
        },
      ],
    }),
  );

  // search_{plural}
  server.tool(
    `search_${plural}`,
    `Search ${plural} with text query and/or structured filters. Text query matches across all string fields (case-insensitive). Filters support: direct equality, $gt, $gte, $lt, $lte, $ne, $in, $contains, $exists. Sort with '-field' for descending. ${idHint}.`,
    {
      query: z.string().optional().describe("Text search query"),
      filter: z.record(z.string(), z.unknown()).optional().describe("Structured filters"),
      sort: z.string().optional().default("-updated_at").describe("Sort field"),
      limit: z.number().optional().default(20).describe("Max results"),
    },
    ({ query, filter, sort, limit }) => ({
      content: [
        {
          type: "text",
          text: JSON.stringify(app.searchEntities(name, { query, filter, sort, limit })),
        },
      ],
    }),
  );

  // delete_{name}
  server.tool(
    `delete_${name}`,
    `Delete a ${name} by ID. Soft delete by default (sets status to 'deleted'). ` +
      `Set hard=true to permanently remove. ${idHint}.`,
    {
      entity_id: z.string().describe(`${name} ID`),
      hard: z.boolean().optional().default(false).describe("Hard delete"),
    },
    ({ entity_id, hard }) => ({
      content: [
        {
          type: "text",
          text: JSON.stringify(app.deleteEntity(name, entity_id, hard)),
        },
      ],
    }),
  );
}

/**
 * Create an MCP server from an Upjack manifest.
 *
 * @param manifestPath - Path to manifest.json.
 * @param root - Workspace root directory.
 * @returns Configured McpServer instance.
 */
export function createServer(manifestPath: string, root = "."): McpServer {
  const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
  const manifestDir = dirname(manifestPath);

  const upjack = (manifest._meta?.["ai.nimblebrain/upjack"] ?? {}) as UpjackManifestExtension;
  const appName = upjack.display?.name ?? manifest.title ?? "Upjack App";

  const app = UpjackApp.fromManifest(manifestPath, root);

  const server = new McpServer({
    name: appName,
    version: manifest.version ?? "0.1.0",
  });

  // Register tools for each entity type
  for (const entityDef of upjack.entities ?? []) {
    const schema = app._schemas[entityDef.name];
    registerEntityTools(server, app, entityDef, schema);
  }

  // Register context resource
  const contextFile = upjack.context;
  if (contextFile) {
    const contextPath = join(manifestDir, contextFile);
    try {
      readFileSync(contextPath, "utf-8"); // Check it exists
      server.resource(
        "context",
        "upjack://context",
        { description: "App domain knowledge" },
        () => ({
          contents: [
            {
              uri: "upjack://context",
              text: readFileSync(contextPath, "utf-8"),
            },
          ],
        }),
      );
    } catch {
      // Context file doesn't exist — skip
    }
  }

  // Register skill resources
  for (const skill of upjack.skills ?? []) {
    if (skill.source !== "bundled") continue;
    const skillPath = join(manifestDir, skill.path);
    try {
      readFileSync(skillPath, "utf-8"); // Check it exists
      const skillName = skillPath.split("/").slice(-2, -1)[0];
      server.resource(
        skillName,
        `upjack://skills/${skillName}`,
        { description: `Skill: ${skillName}` },
        () => ({
          contents: [
            {
              uri: `upjack://skills/${skillName}`,
              text: readFileSync(skillPath, "utf-8"),
            },
          ],
        }),
      );
    } catch {
      // Skill file doesn't exist — skip
    }
  }

  return server;
}

/**
 * Start the MCP server with stdio transport.
 */
export async function startServer(manifestPath: string, root = "."): Promise<void> {
  const server = createServer(manifestPath, root);
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

// Export for testing
export { describeSchemaFields as _describeSchemaFields, buildInstructions as _buildInstructions };
