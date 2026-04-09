import { writeFileSync } from "node:fs";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  buildEntityOutputSchema,
  buildListOutputSchema,
  hydrateDefaults,
  loadSchema,
  resolveEntitySchema,
  validateEntity,
  validateSchemaChange,
} from "../src/schema.js";

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

describe("hydrateDefaults", () => {
  it("fills missing field with schema default", () => {
    const schema = {
      type: "object",
      properties: {
        name: { type: "string" },
        status: { type: "string", default: "active" },
      },
    };
    const data = { name: "test" };
    const result = hydrateDefaults(data, schema);
    expect(result.status).toBe("active");
    expect(result.name).toBe("test");
  });

  it("preserves existing field value", () => {
    const schema = {
      type: "object",
      properties: {
        status: { type: "string", default: "active" },
      },
    };
    const data = { status: "archived" };
    const result = hydrateDefaults(data, schema);
    expect(result.status).toBe("archived");
  });

  it("does not mutate input object", () => {
    const schema = {
      type: "object",
      properties: {
        status: { type: "string", default: "active" },
      },
    };
    const data = { name: "test" };
    hydrateDefaults(data, schema);
    expect(data).toEqual({ name: "test" });
  });

  it("handles allOf with $ref to base entity schema", () => {
    const schema = {
      allOf: [
        { $ref: "https://upjack.dev/schemas/v1/upjack-entity.schema.json" },
        {
          type: "object",
          properties: {
            priority: { type: "string", default: "medium" },
          },
        },
      ],
    };
    const data = { name: "test" };
    const result = hydrateDefaults(data, schema);
    // Base schema has defaults for created_by, status, tags, relationships
    expect(result.status).toBe("active");
    expect(result.tags).toEqual([]);
    expect(result.relationships).toEqual([]);
    expect(result.created_by).toBe("agent");
    // App schema default
    expect(result.priority).toBe("medium");
  });

  it("returns shallow copy when no defaults", () => {
    const schema = {
      type: "object",
      properties: { name: { type: "string" } },
    };
    const data = { name: "test" };
    const result = hydrateDefaults(data, schema);
    expect(result).toEqual(data);
    expect(result).not.toBe(data);
  });

  it("deep-clones mutable defaults so they are isolated", () => {
    const schema = {
      type: "object",
      properties: {
        items: { type: "array", default: ["a", "b"] },
      },
    };
    const result1 = hydrateDefaults({}, schema);
    const result2 = hydrateDefaults({}, schema);
    (result1.items as string[]).push("c");
    expect(result2.items).toEqual(["a", "b"]);
  });
});

describe("validateSchemaChange", () => {
  it("returns empty for identical schemas", () => {
    const schema = {
      properties: { name: { type: "string" } },
      required: ["name"],
    };
    expect(validateSchemaChange(schema, schema)).toEqual([]);
  });

  it("detects newly required field without default as error", () => {
    const old = { properties: { name: { type: "string" } } };
    const new_ = {
      properties: { name: { type: "string" }, age: { type: "number" } },
      required: ["age"],
    };
    const diags = validateSchemaChange(old, new_);
    expect(diags).toHaveLength(1);
    expect(diags[0].severity).toBe("error");
    expect(diags[0].field).toBe("age");
  });

  it("accepts newly required field with default", () => {
    const old = { properties: { name: { type: "string" } } };
    const new_ = {
      properties: { name: { type: "string" }, age: { type: "number", default: 0 } },
      required: ["age"],
    };
    expect(validateSchemaChange(old, new_)).toEqual([]);
  });

  it("detects type change as error", () => {
    const old = { properties: { count: { type: "string" } } };
    const new_ = { properties: { count: { type: "number" } } };
    const diags = validateSchemaChange(old, new_);
    expect(diags).toHaveLength(1);
    expect(diags[0].severity).toBe("error");
    expect(diags[0].message).toContain("Type changed");
  });

  it("detects enum narrowing as error", () => {
    const old = { properties: { status: { type: "string", enum: ["a", "b", "c"] } } };
    const new_ = { properties: { status: { type: "string", enum: ["a", "b"] } } };
    const diags = validateSchemaChange(old, new_);
    expect(diags).toHaveLength(1);
    expect(diags[0].severity).toBe("error");
    expect(diags[0].message).toContain("Enum narrowed");
  });

  it("accepts enum widening", () => {
    const old = { properties: { status: { type: "string", enum: ["a", "b"] } } };
    const new_ = { properties: { status: { type: "string", enum: ["a", "b", "c"] } } };
    expect(validateSchemaChange(old, new_)).toEqual([]);
  });

  it("detects field removal as warning", () => {
    const old = { properties: { name: { type: "string" }, age: { type: "number" } } };
    const new_ = { properties: { name: { type: "string" } } };
    const diags = validateSchemaChange(old, new_);
    expect(diags).toHaveLength(1);
    expect(diags[0].severity).toBe("warning");
    expect(diags[0].field).toBe("age");
  });

  it("returns multiple issues together", () => {
    const old = {
      properties: {
        name: { type: "string" },
        count: { type: "string" },
        extra: { type: "boolean" },
      },
    };
    const new_ = {
      properties: {
        name: { type: "string" },
        count: { type: "number" },
        priority: { type: "string" },
      },
      required: ["priority"],
    };
    const diags = validateSchemaChange(old, new_);
    // type change on count, field removed (extra), newly required without default (priority)
    expect(diags.length).toBeGreaterThanOrEqual(3);
  });
});

describe("buildEntityOutputSchema", () => {
  it("adds type:object to allOf schema without type", () => {
    const base = { type: "object", properties: { id: { type: "string" } } };
    const app = { type: "object", properties: { name: { type: "string" } } };
    const composed = resolveEntitySchema(base, app);
    expect(composed.type).toBeUndefined();

    const result = buildEntityOutputSchema(composed);
    expect(result.type).toBe("object");
    expect(result.allOf).toBeDefined();
  });

  it("preserves existing type:object", () => {
    const schema = { type: "object", properties: { name: { type: "string" } } };
    const result = buildEntityOutputSchema(schema);
    expect(result.type).toBe("object");
  });

  it("strips $schema and $id", () => {
    const schema = {
      $schema: "https://json-schema.org/draft/2020-12/schema",
      $id: "https://example.com/widget",
      type: "object",
      properties: { name: { type: "string" } },
    };
    const result = buildEntityOutputSchema(schema);
    expect(result.$schema).toBeUndefined();
    expect(result.$id).toBeUndefined();
  });

  it("deep copies input (mutations isolated)", () => {
    const schema = { allOf: [{ type: "object" }] };
    const result = buildEntityOutputSchema(schema);
    (result as Record<string, unknown>).extra = true;
    expect(schema).not.toHaveProperty("extra");
  });
});

describe("buildListOutputSchema", () => {
  it("returns object with entities array and count", () => {
    const schema = { type: "object", properties: { name: { type: "string" } } };
    const result = buildListOutputSchema(schema);
    expect(result.type).toBe("object");
    const props = result.properties as Record<string, Record<string, unknown>>;
    expect(props.entities.type).toBe("array");
    expect(props.count.type).toBe("integer");
    expect(result.required).toEqual(["entities", "count"]);
  });

  it("items schema has type:object via buildEntityOutputSchema", () => {
    const composed = resolveEntitySchema(
      { type: "object", properties: { id: { type: "string" } } },
      { type: "object", properties: { name: { type: "string" } } },
    );
    const result = buildListOutputSchema(composed);
    const props = result.properties as Record<string, Record<string, unknown>>;
    const items = props.entities.items as Record<string, unknown>;
    expect(items.type).toBe("object");
  });
});
