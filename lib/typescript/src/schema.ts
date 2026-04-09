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

const BASE_SCHEMA_PATH = join(__dirname, "schemas", "upjack-entity.schema.json");
const BASE_SCHEMA = JSON.parse(readFileSync(BASE_SCHEMA_PATH, "utf-8"));

// @ts-expect-error -- AJV constructor works at runtime despite CJS type mismatch
const ajv = new Ajv2020({ allErrors: true, strict: false });
// @ts-expect-error -- ajv-formats works at runtime despite CJS type mismatch
addFormats(ajv);

// Register the base schema under its remote URI so $ref resolution works offline
ajv.addSchema(BASE_SCHEMA, "https://upjack.dev/schemas/v1/upjack-entity.schema.json");

// Map $ref URIs to resolved schemas for hydration
const REF_MAP: Record<string, Record<string, unknown>> = {
  "https://upjack.dev/schemas/v1/upjack-entity.schema.json": BASE_SCHEMA as Record<string, unknown>,
};

/**
 * Load a JSON Schema from a file path.
 *
 * @param path - Path to the .schema.json file.
 * @returns Parsed JSON Schema object.
 * @throws Error if the file doesn't exist or isn't valid JSON.
 */
export function loadSchema(path: string): Record<string, unknown> {
  return JSON.parse(readFileSync(path, "utf-8"));
}

/**
 * Validate entity data against a JSON Schema.
 *
 * Uses JSON Schema draft 2020-12 validation. Resolves $ref to the
 * base entity schema via a bundled local copy.
 *
 * @param data - Entity data to validate.
 * @param schema - JSON Schema to validate against.
 * @throws Error if validation fails, with details of all errors.
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
 *
 * @param baseSchema - The upjack-entity base schema.
 * @param appSchema - The app-specific entity schema.
 * @returns Composed schema with allOf referencing both.
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
 * Walks `properties` and `allOf` sub-schemas (resolving `$ref` to the
 * bundled base entity schema). Does NOT mutate the input data.
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
  // Handle allOf — walk each sub-schema
  const allOf = schema.allOf as Array<Record<string, unknown>> | undefined;
  if (allOf) {
    for (const sub of allOf) {
      const ref = sub.$ref as string | undefined;
      if (ref && ref in REF_MAP) {
        applyPropertyDefaults(data, REF_MAP[ref]);
      } else {
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

  // Newly required without default
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

  // Type change and enum narrowing on shared fields
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

  // Field removed
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
 * Strips JSON Schema meta keywords and ensures `type: "object"`.
 */
export function buildEntityOutputSchema(schema: Record<string, unknown>): Record<string, unknown> {
  const { $schema: _, $id: __, ...result } = structuredClone(schema);
  if (!("type" in result)) {
    result.type = "object";
  }
  // Resolve $ref in allOf to prevent downstream AJV resolution failures
  if (Array.isArray(result.allOf)) {
    result.allOf = (result.allOf as Array<Record<string, unknown>>).map((sub) => {
      const ref = sub.$ref as string | undefined;
      if (ref && ref in REF_MAP) {
        return structuredClone(REF_MAP[ref]);
      }
      return sub;
    });
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
