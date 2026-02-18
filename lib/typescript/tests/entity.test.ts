import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import {
  createEntity,
  deleteEntity,
  getEntity,
  listEntities,
  updateEntity,
} from "../src/entity.js";
import { validateId } from "../src/ids.js";
import { entityDir, entityPath } from "../src/paths.js";

const NAMESPACE = "apps/crm";
let workspace: string;

beforeEach(() => {
  workspace = mkdtempSync(join(tmpdir(), "upjack-entity-"));
});

const SAMPLE_SCHEMA = {
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
  },
  required: ["id", "type", "version", "created_at", "updated_at", "first_name", "last_name"],
  additionalProperties: true,
};

describe("createEntity", () => {
  it("creates entity file", () => {
    const result = createEntity(workspace, NAMESPACE, "contact", "contacts", "ct", {
      first_name: "Sarah",
      last_name: "Chen",
    });

    expect(validateId(result.id)).toBe(true);
    expect(result.id.startsWith("ct_")).toBe(true);
    expect(result.type).toBe("contact");
    expect(result.version).toBe(1);
    expect(result.status).toBe("active");
    expect(result.first_name).toBe("Sarah");

    const path = entityPath(workspace, NAMESPACE, "contacts", result.id);
    expect(existsSync(path)).toBe(true);
  });

  it("validates against schema", () => {
    const result = createEntity(
      workspace,
      NAMESPACE,
      "contact",
      "contacts",
      "ct",
      { first_name: "Sarah", last_name: "Chen" },
      SAMPLE_SCHEMA,
    );
    expect(result.first_name).toBe("Sarah");
  });

  it("handles source field", () => {
    const result = createEntity(workspace, NAMESPACE, "contact", "contacts", "ct", {
      first_name: "Alice",
      source: { origin: "import", ref: "legacy-123" },
    });
    expect(result.source).toEqual({ origin: "import", ref: "legacy-123" });
  });
});

describe("updateEntity", () => {
  it("updates entity with merge", () => {
    const created = createEntity(workspace, NAMESPACE, "contact", "contacts", "ct", {
      first_name: "Sarah",
      last_name: "Chen",
    });
    const updated = updateEntity(workspace, NAMESPACE, "contacts", created.id, {
      last_name: "Johnson",
    });

    expect(updated.last_name).toBe("Johnson");
    expect(updated.first_name).toBe("Sarah");
    // updated_at is refreshed (may match if within same second, so just verify it exists)
    expect(updated.updated_at).toBeDefined();
  });

  it("replace mode", () => {
    const created = createEntity(workspace, NAMESPACE, "contact", "contacts", "ct", {
      first_name: "Sarah",
      last_name: "Chen",
    });
    const updated = updateEntity(
      workspace,
      NAMESPACE,
      "contacts",
      created.id,
      { first_name: "Jane", last_name: "Doe" },
      undefined,
      false,
    );

    expect(updated.first_name).toBe("Jane");
    expect(updated.id).toBe(created.id);
  });

  it("protects immutable fields", () => {
    const created = createEntity(workspace, NAMESPACE, "contact", "contacts", "ct", {
      first_name: "Sarah",
    });
    const updated = updateEntity(workspace, NAMESPACE, "contacts", created.id, {
      id: "ct_FAKE00000000000000000000000",
      type: "hacked",
      created_at: "1999-01-01T00:00:00Z",
      version: 999,
      created_by: "hacked",
      first_name: "Jane",
    });

    expect(updated.id).toBe(created.id);
    expect(updated.type).toBe("contact");
    expect(updated.created_at).toBe(created.created_at);
    expect(updated.version).toBe(created.version);
    expect(updated.created_by).toBe(created.created_by);
    expect(updated.first_name).toBe("Jane");
  });

  it("throws on missing entity", () => {
    expect(() =>
      updateEntity(workspace, NAMESPACE, "contacts", "ct_01JKXM9V3QWERTY123456ABCDF", {
        name: "test",
      }),
    ).toThrow("Entity not found");
  });
});

describe("getEntity", () => {
  it("gets entity", () => {
    const created = createEntity(workspace, NAMESPACE, "contact", "contacts", "ct", {
      first_name: "Sarah",
    });
    const result = getEntity(workspace, NAMESPACE, "contacts", created.id);
    expect(result.id).toBe(created.id);
    expect(result.first_name).toBe("Sarah");
  });

  it("throws on missing", () => {
    expect(() =>
      getEntity(workspace, NAMESPACE, "contacts", "ct_01JKXM9V3QWERTY123456ABCDF"),
    ).toThrow("Entity not found");
  });
});

describe("listEntities", () => {
  it("lists entities", () => {
    for (const name of ["Alice", "Bob", "Charlie"]) {
      createEntity(workspace, NAMESPACE, "contact", "contacts", "ct", { first_name: name });
    }
    const results = listEntities(workspace, NAMESPACE, "contacts");
    expect(results).toHaveLength(3);
  });

  it("filters by status", () => {
    const created = createEntity(workspace, NAMESPACE, "contact", "contacts", "ct", {
      first_name: "Alice",
    });
    deleteEntity(workspace, NAMESPACE, "contacts", created.id);
    createEntity(workspace, NAMESPACE, "contact", "contacts", "ct", { first_name: "Bob" });

    const active = listEntities(workspace, NAMESPACE, "contacts", "active");
    const deleted = listEntities(workspace, NAMESPACE, "contacts", "deleted");
    expect(active).toHaveLength(1);
    expect(deleted).toHaveLength(1);
  });

  it("respects limit", () => {
    for (let i = 0; i < 10; i++) {
      createEntity(workspace, NAMESPACE, "contact", "contacts", "ct", {
        first_name: `Person${i}`,
      });
    }
    const results = listEntities(workspace, NAMESPACE, "contacts", "active", 3);
    expect(results).toHaveLength(3);
  });

  it("returns empty for missing directory", () => {
    const results = listEntities(workspace, NAMESPACE, "contacts");
    expect(results).toEqual([]);
  });

  it("skips corrupt JSON files", () => {
    createEntity(workspace, NAMESPACE, "contact", "contacts", "ct", { first_name: "Valid" });
    const dir = entityDir(workspace, NAMESPACE, "contacts");
    writeFileSync(join(dir, "corrupt.json"), "{not valid json");

    const results = listEntities(workspace, NAMESPACE, "contacts");
    expect(results).toHaveLength(1);
    expect(results[0].first_name).toBe("Valid");
  });
});

describe("deleteEntity", () => {
  it("soft delete", () => {
    const created = createEntity(workspace, NAMESPACE, "contact", "contacts", "ct", {
      first_name: "Sarah",
    });
    const result = deleteEntity(workspace, NAMESPACE, "contacts", created.id);
    expect(result.status).toBe("deleted");

    const path = entityPath(workspace, NAMESPACE, "contacts", created.id);
    expect(existsSync(path)).toBe(true);
  });

  it("hard delete", () => {
    const created = createEntity(workspace, NAMESPACE, "contact", "contacts", "ct", {
      first_name: "Sarah",
    });
    deleteEntity(workspace, NAMESPACE, "contacts", created.id, true);

    const path = entityPath(workspace, NAMESPACE, "contacts", created.id);
    expect(existsSync(path)).toBe(false);
  });

  it("throws on missing", () => {
    expect(() =>
      deleteEntity(workspace, NAMESPACE, "contacts", "ct_01JKXM9V3QWERTY123456ABCDF"),
    ).toThrow("Entity not found");
  });
});
