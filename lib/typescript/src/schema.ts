import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
// eslint-disable-next-line @typescript-eslint/no-require-imports -- ajv-formats CJS interop
import addFormatsModule from "ajv-formats";
// eslint-disable-next-line @typescript-eslint/no-require-imports -- AJV CJS interop
import Ajv2020Module from "ajv/dist/2020.js";

// CJS default export interop
const Ajv2020 =
  (Ajv2020Module as unknown as { default: typeof Ajv2020Module }).default ?? Ajv2020Module;
const addFormats =
  (addFormatsModule as unknown as { default: typeof addFormatsModule }).default ?? addFormatsModule;

const __dirname = dirname(fileURLToPath(import.meta.url));

/**
 * Canonical `$id` / `$ref` URL for the bundled base entity schema. App
 * schemas reference this via `allOf: [{"$ref": BASE_ENTITY_REF}]` so apps
 * can layer their own fields on top of the framework-managed ones.
 */
export const BASE_ENTITY_REF = "https://upjack.dev/schemas/v1/upjack-entity.schema.json";

/**
 * Non-standard marker attached to the inlined base-entity schema so
 * downstream code can identify it without the `$ref` or `$id` (both of
 * which cause problems for JSON Schema validators that auto-register
 * schemas by `$id`). Consumers should treat any allOf member with this
 * field as "the base entity schema, inlined by loadSchema".
 */
export const BASE_ENTITY_MARKER = "x-upjack-base-entity";

const BASE_SCHEMA_PATH = join(__dirname, "schemas", "upjack-entity.schema.json");
const BASE_SCHEMA = JSON.parse(readFileSync(BASE_SCHEMA_PATH, "utf-8")) as Record<string, unknown>;

// @ts-expect-error -- AJV constructor works at runtime despite CJS type mismatch
const ajv = new Ajv2020({ allErrors: true, strict: false });
// @ts-expect-error -- ajv-formats works at runtime despite CJS type mismatch
addFormats(ajv);

// Register the base schema so AJV resolves $ref to it locally (defensive
// guard against schemas that bypass loadSchema).
ajv.addSchema(BASE_SCHEMA, BASE_ENTITY_REF);

/**
 * Load a JSON Schema from disk and inline the base-entity `$ref`.
 *
 * Any `allOf: [{"$ref": BASE_ENTITY_REF}]` entry is replaced with the
 * bundled base-entity schema inline, so every downstream consumer sees a
 * fully self-contained schema. This is the single source of truth for
 * $ref resolution — no caller needs to do it again.
 */
export function loadSchema(path: string): Record<string, unknown> {
  const schema = JSON.parse(readFileSync(path, "utf-8"));
  inlineBaseEntityRef(schema);
  return schema;
}

function inlineBaseEntityRef(node: unknown): void {
  if (Array.isArray(node)) {
    for (const item of node) inlineBaseEntityRef(item);
    return;
  }
  if (node === null || typeof node !== "object") return;

  const obj = node as Record<string, unknown>;
  const allOf = obj.allOf;
  if (Array.isArray(allOf)) {
    for (let i = 0; i < allOf.length; i++) {
      const sub = allOf[i];
      if (
        sub &&
        typeof sub === "object" &&
        (sub as Record<string, unknown>).$ref === BASE_ENTITY_REF
      ) {
        // Drop $schema and $id — the inlined copy sharing its $id with the
        // pre-registered schema in AJV's registry triggers a "resolves to
        // more than one schema" error. Our own marker lets downstream code
        // recognise this member without those identifiers.
        const {
          $schema: _s,
          $id: _i,
          ...inlined
        } = structuredClone(BASE_SCHEMA) as Record<string, unknown>;
        inlined[BASE_ENTITY_MARKER] = true;
        allOf[i] = inlined;
      }
    }
  }
  for (const value of Object.values(obj)) {
    inlineBaseEntityRef(value);
  }
}

/**
 * Validate entity data against a JSON Schema.
 *
 * The AJV registry resolves any remaining `$ref` to the base entity schema
 * locally, so validation works even if the caller handed us a schema that
 * bypassed `loadSchema`.
 */
export function validateEntity(
  data: Record<string, unknown>,
  schema: Record<string, unknown>,
): void {
  const validate = ajv.compile(schema);
  if (!validate(data)) {
    const errors = validate.errors
      ?.map((e: { instancePath: string; message?: string }) => `${e.instancePath} ${e.message}`)
      .join("; ");
    throw new Error(`Validation failed: ${errors}`);
  }
}

/**
 * Create a composed schema from base entity schema and app-specific schema.
 *
 * Uses allOf composition so both base and app constraints apply.
 */
export function resolveEntitySchema(
  baseSchema: Record<string, unknown>,
  appSchema: Record<string, unknown>,
): Record<string, unknown> {
  return {
    $schema: "https://json-schema.org/draft/2020-12/schema",
    allOf: [baseSchema, appSchema],
  };
}

/**
 * Fill missing fields from schema defaults.
 *
 * Walks `properties` and `allOf` sub-schemas. Assumes `schema` has been
 * loaded via {@link loadSchema} so any base-entity `$ref` has been inlined —
 * does not resolve live `$ref` values.
 */
export function hydrateDefaults(
  data: Record<string, unknown>,
  schema: Record<string, unknown>,
): Record<string, unknown> {
  const result = { ...data };
  applyPropertyDefaults(result, schema);
  return result;
}

function applyPropertyDefaults(
  data: Record<string, unknown>,
  schema: Record<string, unknown>,
): void {
  const allOf = schema.allOf as Array<Record<string, unknown>> | undefined;
  if (allOf) {
    for (const sub of allOf) {
      if (sub && typeof sub === "object") {
        applyPropertyDefaults(data, sub);
      }
    }
  }

  const props = schema.properties as Record<string, Record<string, unknown>> | undefined;
  if (!props) return;

  for (const [fieldName, fieldSchema] of Object.entries(props)) {
    if (!(fieldName in data) && "default" in fieldSchema) {
      data[fieldName] = structuredClone(fieldSchema.default);
    }
  }
}

/**
 * Compare two app-level schema dicts and return diagnostics.
 *
 * Compares top-level `properties` and `required` only.
 */
export function validateSchemaChange(
  oldSchema: Record<string, unknown>,
  newSchema: Record<string, unknown>,
): Array<{ severity: string; field: string; message: string }> {
  const diagnostics: Array<{ severity: string; field: string; message: string }> = [];

  const oldProps = (oldSchema.properties ?? {}) as Record<string, Record<string, unknown>>;
  const newProps = (newSchema.properties ?? {}) as Record<string, Record<string, unknown>>;
  const oldRequired = new Set((oldSchema.required ?? []) as string[]);
  const newRequired = new Set((newSchema.required ?? []) as string[]);

  for (const field of [...newRequired].sort()) {
    if (oldRequired.has(field)) continue;
    const prop = newProps[field];
    if (prop && !("default" in prop)) {
      diagnostics.push({
        severity: "error",
        field,
        message: `Field '${field}' is newly required but has no default`,
      });
    }
  }

  const sharedFields = Object.keys(oldProps)
    .filter((k) => k in newProps)
    .sort();
  for (const field of sharedFields) {
    const oldType = oldProps[field].type as string | undefined;
    const newType = newProps[field].type as string | undefined;
    if (oldType && newType && oldType !== newType) {
      diagnostics.push({
        severity: "error",
        field,
        message: `Type changed from '${oldType}' to '${newType}'`,
      });
    }

    const oldEnum = oldProps[field].enum as unknown[] | undefined;
    const newEnum = newProps[field].enum as unknown[] | undefined;
    if (oldEnum !== undefined && newEnum !== undefined) {
      const oldSet = new Set(oldEnum.map(String));
      const newSet = new Set(newEnum.map(String));
      const isSubset = [...newSet].every((v) => oldSet.has(v));
      if (isSubset && newSet.size < oldSet.size) {
        diagnostics.push({
          severity: "error",
          field,
          message: `Enum narrowed from ${JSON.stringify(oldEnum)} to ${JSON.stringify(newEnum)}`,
        });
      }
    }
  }

  for (const field of Object.keys(oldProps).sort()) {
    if (!(field in newProps)) {
      diagnostics.push({
        severity: "warning",
        field,
        message: `Field '${field}' was removed`,
      });
    }
  }

  return diagnostics;
}

/**
 * Build an output schema for a single-entity tool response.
 *
 * Expects `schema` to be already self-contained (loaded via {@link loadSchema}).
 * Strips JSON Schema meta keywords that don't belong in a tool output schema.
 * MCP requires `type: "object"` on every outputSchema.
 */
export function buildEntityOutputSchema(schema: Record<string, unknown>): Record<string, unknown> {
  const { $schema: _, $id: __, ...result } = structuredClone(schema);
  if (!("type" in result)) {
    result.type = "object";
  }
  return result;
}

/**
 * Build an output schema for a list/search tool response.
 *
 * Returns an envelope schema with `entities` array and `count`.
 */
export function buildListOutputSchema(
  entitySchema: Record<string, unknown>,
): Record<string, unknown> {
  return {
    type: "object",
    properties: {
      entities: {
        type: "array",
        items: buildEntityOutputSchema(entitySchema),
      },
      count: {
        type: "integer",
        description: "Number of entities returned",
      },
    },
    required: ["entities", "count"],
  };
}
