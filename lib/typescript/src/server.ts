import {
  existsSync,
  readFileSync,
  readdirSync,
  renameSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
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
import { rebuildIndex } from "./relations.js";
import {
  buildEntityOutputSchema,
  buildListOutputSchema,
  loadSchema,
  validateSchemaChange,
} from "./schema.js";

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
  const { $schema: _, $id: __, ...result } = structuredClone(schema);

  if (result.properties) {
    result.properties = Object.fromEntries(
      Object.entries(result.properties).filter(([k]) => !BASE_ENTITY_KEYS.has(k)),
    );
  }

  if (opts?.forUpdate) {
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
// Tool listing filter
// ---------------------------------------------------------------------------

const CATEGORY_TO_TOOL: Record<string, string> = {
  create: "create_{name}",
  get: "get_{name}",
  update: "update_{name}",
  list: "list_{plural}",
  search: "search_{plural}",
  delete: "delete_{name}",
  query_by_relationship: "query_{plural}_by_relationship",
  get_related: "get_related_{name}",
  get_composite: "get_{name}_composite",
};

const ALL_UTILITY_TOOLS = new Set(["seed_data", "add_field", "rebuild_index"]);

function resolveListedTools(
  name: string,
  plural: string | undefined,
  categories: string[],
): Set<string> {
  const p = plural ?? `${name}s`;
  const result = new Set<string>();
  for (const cat of categories) {
    const tmpl = CATEGORY_TO_TOOL[cat];
    if (tmpl) {
      result.add(tmpl.replace("{name}", name).replace("{plural}", p));
    }
  }
  return result;
}

function resolveUtilityTools(utilityTools: string[] | undefined): Set<string> {
  if (utilityTools === undefined) return new Set(ALL_UTILITY_TOOLS);
  return new Set([...utilityTools].filter((t) => ALL_UTILITY_TOOLS.has(t)));
}

// ---------------------------------------------------------------------------
// Tool definition builders
// ---------------------------------------------------------------------------

interface ToolDefinition {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
  outputSchema?: Record<string, unknown>;
}

type ToolHandler = (args: Record<string, unknown>) => unknown;

function wrapList(entities: unknown[]): { entities: unknown[]; count: number } {
  return { entities, count: entities.length };
}

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

  const entityOut = schema ? buildEntityOutputSchema(schema) : undefined;
  const listOut = schema ? buildListOutputSchema(schema) : undefined;

  const definitions: ToolDefinition[] = [
    {
      name: `create_${name}`,
      description: `Create a new ${name}. ${idHint}.`,
      inputSchema: {
        type: "object",
        properties: { data: dataSchema },
        required: ["data"],
      },
      ...(entityOut ? { outputSchema: entityOut } : {}),
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
      ...(entityOut ? { outputSchema: entityOut } : {}),
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
      ...(entityOut ? { outputSchema: entityOut } : {}),
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
      ...(listOut ? { outputSchema: listOut } : {}),
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
      ...(listOut ? { outputSchema: listOut } : {}),
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
      ...(entityOut ? { outputSchema: entityOut } : {}),
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
      wrapList(
        app.listEntities(name, (args.status as string) ?? "active", (args.limit as number) ?? 50),
      ),
    [`search_${plural}`]: (args) =>
      wrapList(
        app.searchEntities(name, {
          query: args.query as string | undefined,
          filter: args.filter as Record<string, unknown> | undefined,
          sort: (args.sort as string) ?? "-updated_at",
          limit: (args.limit as number) ?? 20,
        }),
      ),
    [`delete_${name}`]: (args) =>
      app.deleteEntity(name, args.entity_id as string, (args.hard as boolean) ?? false),
  };

  return { definitions, handlers };
}

// ---------------------------------------------------------------------------
// Relationship tools
// ---------------------------------------------------------------------------

function buildRelationshipTools(
  app: UpjackApp,
  entityDef: { name: string; plural?: string; prefix: string; schema: string },
  schema: Record<string, unknown> | undefined,
): { definitions: ToolDefinition[]; handlers: Record<string, ToolHandler> } {
  const name = entityDef.name;
  const plural = entityDef.plural ?? `${name}s`;
  const idParam = `${name}_id`;

  const listOut = schema ? buildListOutputSchema(schema) : undefined;
  const entityOut = schema ? buildEntityOutputSchema(schema) : undefined;

  const definitions: ToolDefinition[] = [
    {
      name: `query_${plural}_by_relationship`,
      description:
        `Find ${plural} that have a specific relationship pointing to a target entity. ` +
        `For example, find all ${plural} that 'belongs_to' a given entity.`,
      inputSchema: {
        type: "object",
        properties: {
          rel: { type: "string", description: "Relationship type to query" },
          target_id: { type: "string", description: "Target entity ID" },
          filter: { type: "object", description: "Optional equality filters" },
          limit: { type: "number", default: 50, description: "Max results" },
        },
        required: ["rel", "target_id"],
      },
      ...(listOut ? { outputSchema: listOut } : {}),
    },
    {
      name: `get_related_${name}`,
      description:
        `Follow relationship edges from a ${name}. ` +
        `'forward' returns entities this ${name} points to. ` +
        `'reverse' returns entities that point to this ${name}.`,
      inputSchema: {
        type: "object",
        properties: {
          [idParam]: {
            type: "string",
            description: `${name} ID (${entityDef.prefix}_...)`,
          },
          rel: { type: "string", description: "Relationship type to follow. Omit to follow all." },
          direction: {
            type: "string",
            description: "'forward' or 'reverse'.",
            default: "forward",
          },
        },
        required: [idParam],
      },
      ...(listOut ? { outputSchema: listOut } : {}),
    },
    {
      name: `get_${name}_composite`,
      description: `Load a ${name} with all related entities in one call. Returns the entity with a '_related' key containing forward relationships (keyed by rel name) and reverse relationships (keyed by ~rel name).`,
      inputSchema: {
        type: "object",
        properties: {
          [idParam]: {
            type: "string",
            description: `${name} ID (${entityDef.prefix}_...)`,
          },
          depth: { type: "integer", description: "Traversal depth (default 1).", default: 1 },
        },
        required: [idParam],
      },
      ...(entityOut ? { outputSchema: entityOut } : {}),
    },
  ];

  const handlers: Record<string, ToolHandler> = {
    [`query_${plural}_by_relationship`]: (args) =>
      wrapList(
        app.queryByRelationship(
          name,
          args.rel as string,
          args.target_id as string,
          args.filter as Record<string, unknown> | undefined,
          (args.limit as number) ?? 50,
        ),
      ),
    [`get_related_${name}`]: (args) =>
      wrapList(
        app.getRelated(
          args[idParam] as string,
          args.rel as string | undefined,
          (args.direction as "forward" | "reverse") ?? "forward",
        ),
      ),
    [`get_${name}_composite`]: (args) =>
      app.getComposite(name, args[idParam] as string, (args.depth as number) ?? 1),
  };

  return { definitions, handlers };
}

// ---------------------------------------------------------------------------
// Activity tools
// ---------------------------------------------------------------------------

function buildActivityTools(app: UpjackApp): {
  definitions: ToolDefinition[];
  handlers: Record<string, ToolHandler>;
} {
  const definitions: ToolDefinition[] = [
    {
      name: "log_activity",
      description:
        "Log an activity against an entity. Auto-wires a 'subject' relationship " +
        "to the given entity. Use this instead of create_activity when you want " +
        "the relationship set up automatically.",
      inputSchema: {
        type: "object",
        properties: {
          subject_id: { type: "string", description: "The entity ID this activity is about." },
          action: {
            type: "string",
            description: "What happened (e.g., 'email_sent', 'meeting_held').",
          },
          detail: { type: "object", description: "Optional structured data about the activity." },
        },
        required: ["subject_id", "action"],
      },
    },
    {
      name: "get_activities",
      description:
        "Get activities recorded against an entity. Returns activities sorted " +
        "most-recent first. Optionally filter by action type.",
      inputSchema: {
        type: "object",
        properties: {
          subject_id: { type: "string", description: "The entity ID to get activities for." },
          action: {
            type: "string",
            description: "Optional filter — only return activities with this action.",
          },
          limit: {
            type: "integer",
            description: "Maximum number of results (default 50).",
            default: 50,
          },
        },
        required: ["subject_id"],
      },
    },
  ];

  const handlers: Record<string, ToolHandler> = {
    log_activity: (args) =>
      app.logActivity(
        args.subject_id as string,
        args.action as string,
        args.detail as Record<string, unknown> | undefined,
      ),
    get_activities: (args) =>
      wrapList(
        app.getActivities(
          args.subject_id as string,
          args.action as string | undefined,
          (args.limit as number) ?? 50,
        ),
      ),
  };

  return { definitions, handlers };
}

// ---------------------------------------------------------------------------
// Utility tools
// ---------------------------------------------------------------------------

const FIELD_NAME_RE = /^[a-z][a-z0-9_]*$/;
const BASE_ENTITY_FIELD_NAMES = new Set([
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

// Fields stripped from seed data before create — matches Python behavior.
// Preserves relationships and tags so seed data can set up a connected graph.
const SEED_STRIP_FIELDS = new Set(["type", "created_at", "updated_at", "created_by"]);
const ALLOWED_FIELD_TYPES = new Set(["string", "number", "integer", "boolean", "array", "object"]);
const TYPE_VALIDATORS: Record<string, (v: unknown) => boolean> = {
  string: (v) => typeof v === "string",
  number: (v) => typeof v === "number",
  integer: (v) => typeof v === "number" && Number.isInteger(v),
  boolean: (v) => typeof v === "boolean",
  array: (v) => Array.isArray(v),
  object: (v) => typeof v === "object" && v !== null && !Array.isArray(v),
};

function buildUtilityTools(
  app: UpjackApp,
  manifestDir: string,
  upjack: UpjackManifestExtension,
): { definitions: ToolDefinition[]; handlers: Record<string, ToolHandler> } {
  const definitions: ToolDefinition[] = [];
  const handlers: Record<string, ToolHandler> = {};

  // seed_data
  if (upjack.seed?.data) {
    const seedDir = join(manifestDir, upjack.seed.data);
    definitions.push({
      name: "seed_data",
      description: "Load sample data from the seed directory.",
      inputSchema: { type: "object", properties: {} },
    });
    handlers.seed_data = () => {
      const loaded: string[] = [];
      const errors: string[] = [];
      if (!existsSync(seedDir)) {
        return { loaded, errors: ["Seed directory not found"] };
      }
      // Build plural→name map
      const pluralToName: Record<string, string> = {};
      for (const eDef of app._entityDefsList()) {
        const p = eDef.plural ?? `${eDef.name}s`;
        pluralToName[p] = eDef.name;
      }
      for (const file of readdirSync(seedDir)) {
        if (!file.endsWith(".json")) continue;
        try {
          const raw = JSON.parse(readFileSync(join(seedDir, file), "utf-8"));
          const entities = Array.isArray(raw) ? raw : [raw];
          const baseName = file.replace(".json", "");
          const entityName = pluralToName[baseName] ?? baseName;
          for (const entity of entities) {
            // Strip system metadata but preserve relationships and tags
            for (const k of SEED_STRIP_FIELDS) {
              delete entity[k];
            }
            app.createEntity(entityName, entity);
          }
          loaded.push(file);
        } catch (err) {
          errors.push(`${file}: ${err instanceof Error ? err.message : String(err)}`);
        }
      }
      return { loaded, errors };
    };
  }

  // add_field
  definitions.push({
    name: "add_field",
    description:
      "Add a new field to an entity schema. Validates the change is safe, " +
      "writes the updated schema to disk, and reloads it.",
    inputSchema: {
      type: "object",
      properties: {
        entity_type: { type: "string" },
        field_name: { type: "string" },
        field_type: { type: "string" },
        default: {},
        description: { type: "string" },
        required: { type: "boolean", default: true },
      },
      required: ["entity_type", "field_name", "field_type", "default"],
    },
  });
  handlers.add_field = (args) => {
    const entityType = args.entity_type as string;
    const fieldName = args.field_name as string;
    const fieldType = args.field_type as string;
    const defaultValue = args.default;
    const description = args.description as string | undefined;
    const isRequired = (args.required as boolean) ?? true;

    if (!FIELD_NAME_RE.test(fieldName)) {
      return { error: `Invalid field_name '${fieldName}'. Must match [a-z][a-z0-9_]*` };
    }
    if (BASE_ENTITY_FIELD_NAMES.has(fieldName)) {
      return { error: `Field '${fieldName}' is a reserved base entity field` };
    }
    if (!ALLOWED_FIELD_TYPES.has(fieldType)) {
      return {
        error: `Invalid field_type '${fieldType}'. Allowed: ${[...ALLOWED_FIELD_TYPES].sort().join(", ")}`,
      };
    }
    const validator = TYPE_VALIDATORS[fieldType];
    if (validator && !validator(defaultValue)) {
      return {
        error: `Default value ${JSON.stringify(defaultValue)} is not compatible with type '${fieldType}'`,
      };
    }

    const entityDefs = app._entityDefsList();
    const entityDef = entityDefs.find((e) => e.name === entityType);
    if (!entityDef) {
      return { error: `Unknown entity type '${entityType}'` };
    }

    const schemaPath = resolve(join(manifestDir, entityDef.schema));
    if (!schemaPath.startsWith(resolve(manifestDir))) {
      return { error: "Schema path escapes the manifest directory" };
    }

    const oldSchema = loadSchema(schemaPath) as Record<string, unknown>;
    const oldProps = (oldSchema.properties ?? {}) as Record<string, Record<string, unknown>>;
    if (fieldName in oldProps) {
      const existingType = oldProps[fieldName].type;
      if (existingType && existingType !== fieldType) {
        return { error: `Field '${fieldName}' already exists with type '${existingType}'` };
      }
      return { error: `Field '${fieldName}' already exists` };
    }

    const newSchema = structuredClone(oldSchema);
    if (!newSchema.properties) newSchema.properties = {};
    const props = newSchema.properties as Record<string, Record<string, unknown>>;
    const propDef: Record<string, unknown> = { type: fieldType, default: defaultValue };
    if (description) propDef.description = description;
    props[fieldName] = propDef;

    if (isRequired) {
      const req = (newSchema.required ?? []) as string[];
      if (!req.includes(fieldName)) {
        req.push(fieldName);
        newSchema.required = req;
      }
    }

    const diagnostics = validateSchemaChange(oldSchema, newSchema);
    const errs = diagnostics.filter((d) => d.severity === "error");
    if (errs.length > 0) {
      return { error: "Schema change validation failed", diagnostics: errs };
    }

    const warnings = diagnostics.filter((d) => d.severity === "warning");
    const tmpPath = `${schemaPath}.tmp`;
    try {
      writeFileSync(tmpPath, `${JSON.stringify(newSchema, null, 2)}\n`);
      renameSync(tmpPath, schemaPath);
    } catch (err) {
      try {
        if (existsSync(tmpPath)) unlinkSync(tmpPath);
      } catch {
        // ignore cleanup errors
      }
      throw err;
    }
    app.reloadSchema(entityType);

    const result: Record<string, unknown> = {
      success: true,
      entity_type: entityType,
      field: { name: fieldName, type: fieldType, default: defaultValue, required: isRequired },
    };
    if (warnings.length > 0) result.warnings = warnings;
    return result;
  };

  // rebuild_index
  definitions.push({
    name: "rebuild_index",
    description:
      "Force a full rebuild of the relationship index from entity files. " +
      "Use this if the index seems stale or after manual file edits.",
    inputSchema: { type: "object", properties: {} },
  });
  handlers.rebuild_index = () => {
    const index = rebuildIndex(app.root, app.namespace, app._entityDefsList());
    const total = Object.values(index.reverse).reduce((sum, entries) => sum + entries.length, 0);
    return { success: true, entries: total };
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

  const contextFile = upjack.context;
  if (contextFile) {
    const contextPath = join(manifestDir, contextFile);
    try {
      readFileSync(contextPath, "utf-8");
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

  for (const skill of upjack.skills ?? []) {
    if (skill.source !== "bundled") continue;
    const skillPath = join(manifestDir, skill.path);
    try {
      readFileSync(skillPath, "utf-8");
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

export function createServer(manifestPath: string, root?: string): Server {
  const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
  const manifestDir = dirname(manifestPath);

  const upjack = (manifest._meta?.["ai.nimblebrain/upjack"] ?? {}) as UpjackManifestExtension;
  const appName = upjack.display?.name ?? manifest.title ?? "Upjack App";

  const app = UpjackApp.fromManifest(manifestPath, root);

  // Collect all tool definitions and handlers
  const allDefinitions: ToolDefinition[] = [];
  const allHandlers: Record<string, ToolHandler> = {};

  // Per-entity: CRUD + relationship tools
  for (const entityDef of upjack.entities ?? []) {
    const schema = app._schemas[entityDef.name];
    const { definitions, handlers } = buildEntityTools(app, entityDef, schema);
    const { definitions: relDefs, handlers: relHandlers } = buildRelationshipTools(
      app,
      entityDef,
      schema,
    );

    allDefinitions.push(...definitions, ...relDefs);
    Object.assign(allHandlers, handlers, relHandlers);
  }

  // Activity entity: CRUD + relationship + convenience tools
  const activitiesEnabled = Boolean(upjack.activities);
  if (activitiesEnabled) {
    const activityDef = { name: "activity", plural: "activities", prefix: "act", schema: "" };
    const activitySchema = app._schemas.activity;
    const { definitions: actDefs, handlers: actHandlers } = buildEntityTools(
      app,
      activityDef,
      activitySchema,
    );
    const { definitions: actRelDefs, handlers: actRelHandlers } = buildRelationshipTools(
      app,
      activityDef,
      activitySchema,
    );
    const { definitions: actConvDefs, handlers: actConvHandlers } = buildActivityTools(app);

    allDefinitions.push(...actDefs, ...actRelDefs, ...actConvDefs);
    Object.assign(allHandlers, actHandlers, actRelHandlers, actConvHandlers);
  }

  // Utility tools
  const { definitions: utilDefs, handlers: utilHandlers } = buildUtilityTools(
    app,
    manifestDir,
    upjack,
  );
  allDefinitions.push(...utilDefs);
  Object.assign(allHandlers, utilHandlers);

  // Apply tool listing filter
  let listedDefinitions = allDefinitions;

  const hasFilter =
    (upjack.entities ?? []).some(
      (e) => (e as unknown as Record<string, unknown>).tools !== undefined,
    ) || upjack.utility_tools !== undefined;

  if (hasFilter) {
    // Build allowed tool set
    const listedTools = new Set<string>();
    for (const entityDef of upjack.entities ?? []) {
      const toolsFilter = (entityDef as unknown as Record<string, unknown>).tools as
        | string[]
        | undefined;
      const name = entityDef.name;
      const plural = entityDef.plural ?? `${name}s`;
      if (toolsFilter) {
        for (const t of resolveListedTools(name, plural, toolsFilter)) listedTools.add(t);
      } else {
        // No filter for this entity: list all categories
        for (const t of resolveListedTools(name, plural, Object.keys(CATEGORY_TO_TOOL)))
          listedTools.add(t);
      }
    }
    if (activitiesEnabled) {
      for (const t of resolveListedTools("activity", "activities", Object.keys(CATEGORY_TO_TOOL)))
        listedTools.add(t);
      listedTools.add("log_activity");
      listedTools.add("get_activities");
    }
    for (const t of resolveUtilityTools(upjack.utility_tools)) listedTools.add(t);

    // Build full set of auto-generated names (for custom tool detection)
    const allAuto = new Set<string>();
    for (const entityDef of upjack.entities ?? []) {
      for (const t of resolveListedTools(
        entityDef.name,
        entityDef.plural,
        Object.keys(CATEGORY_TO_TOOL),
      ))
        allAuto.add(t);
    }
    if (activitiesEnabled) {
      for (const t of resolveListedTools("activity", "activities", Object.keys(CATEGORY_TO_TOOL)))
        allAuto.add(t);
      allAuto.add("log_activity");
      allAuto.add("get_activities");
    }
    for (const t of ALL_UTILITY_TOOLS) allAuto.add(t);

    listedDefinitions = allDefinitions.filter(
      (d) => listedTools.has(d.name) || !allAuto.has(d.name),
    );
  }

  // Collect resources
  const { definitions: resourceDefs, readers: resourceReaders } = buildResources(
    manifestDir,
    upjack,
  );

  // Determine capabilities
  const capabilities: Record<string, Record<string, unknown>> = {};
  if (Object.keys(allHandlers).length > 0) capabilities.tools = {};
  if (resourceDefs.length > 0) capabilities.resources = {};

  const server = new Server(
    { name: appName, version: manifest.version ?? "0.1.0" },
    { capabilities, instructions: buildInstructions(upjack) },
  );

  // tools/list
  if (Object.keys(allHandlers).length > 0) {
    server.setRequestHandler(ListToolsRequestSchema, () => ({
      tools: listedDefinitions.map((d) => ({
        name: d.name,
        description: d.description,
        inputSchema: d.inputSchema,
        ...(d.outputSchema ? { outputSchema: d.outputSchema } : {}),
      })),
    }));

    // tools/call
    server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;
      const handler = allHandlers[name];
      if (!handler) {
        return {
          content: [{ type: "text" as const, text: `Tool ${name} not found` }],
          isError: true,
        };
      }
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

export async function startServer(manifestPath: string, root?: string): Promise<void> {
  const server = createServer(manifestPath, root);
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

// Export for testing
export { prepareEntitySchema as _prepareEntitySchema, buildInstructions as _buildInstructions };
