import { writeFileSync } from "node:fs";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { loadSchema, resolveEntitySchema, validateEntity } from "../src/schema.js";

describe("loadSchema", () => {
  it("loads a valid schema file", () => {
    const tmp = mkdtempSync(join(tmpdir(), "schema-"));
    const schema = { type: "object", properties: { name: { type: "string" } } };
    const schemaPath = join(tmp, "test.schema.json");
    writeFileSync(schemaPath, JSON.stringify(schema));

    const result = loadSchema(schemaPath);
    expect(result).toEqual(schema);
  });

  it("throws on missing file", () => {
    expect(() => loadSchema("/nonexistent/missing.schema.json")).toThrow();
  });
});

const SAMPLE_SCHEMA: Record<string, unknown> = {
  $schema: "https://json-schema.org/draft/2020-12/schema",
  type: "object",
  properties: {
    id: { type: "string" },
    type: { type: "string" },
    version: { type: "integer" },
    created_at: { type: "string" },
    updated_at: { type: "string" },
    first_name: { type: "string" },
    last_name: { type: "string" },
    email: { type: "string", format: "email" },
  },
  required: ["id", "type", "version", "created_at", "updated_at", "first_name", "last_name"],
  additionalProperties: true,
};

describe("validateEntity", () => {
  it("accepts valid entity", () => {
    const data = {
      id: "ct_01JKXM9V3QWERTY123456ABCDF",
      type: "contact",
      version: 1,
      created_at: "2026-02-17T12:00:00Z",
      updated_at: "2026-02-17T12:00:00Z",
      first_name: "Sarah",
      last_name: "Chen",
    };
    expect(() => validateEntity(data, SAMPLE_SCHEMA)).not.toThrow();
  });

  it("rejects missing required fields", () => {
    const data = {
      id: "ct_01JKXM9V3QWERTY123456ABCDF",
      type: "contact",
    };
    expect(() => validateEntity(data, SAMPLE_SCHEMA)).toThrow("Validation failed");
  });

  it("allows additional properties", () => {
    const data = {
      id: "ct_01JKXM9V3QWERTY123456ABCDF",
      type: "contact",
      version: 1,
      created_at: "2026-02-17T12:00:00Z",
      updated_at: "2026-02-17T12:00:00Z",
      first_name: "Sarah",
      last_name: "Chen",
      custom_field: "extra data",
    };
    expect(() => validateEntity(data, SAMPLE_SCHEMA)).not.toThrow();
  });
});

describe("resolveEntitySchema", () => {
  it("creates allOf composition", () => {
    const base = { type: "object", properties: { id: { type: "string" } } };
    const app = { properties: { name: { type: "string" } } };

    const result = resolveEntitySchema(base, app);

    expect(result.$schema).toBeDefined();
    expect(result.allOf).toHaveLength(2);
    expect((result.allOf as unknown[])[0]).toEqual(base);
    expect((result.allOf as unknown[])[1]).toEqual(app);
  });
});
