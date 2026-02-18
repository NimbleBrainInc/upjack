import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
// eslint-disable-next-line @typescript-eslint/no-require-imports -- AJV CJS interop
import Ajv2020Module from "ajv/dist/2020.js";
// eslint-disable-next-line @typescript-eslint/no-require-imports -- ajv-formats CJS interop
import addFormatsModule from "ajv-formats";

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
