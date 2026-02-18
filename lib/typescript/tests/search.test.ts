import { mkdirSync, writeFileSync } from "node:fs";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { createEntity, deleteEntity } from "../src/entity.js";
import { entityDir } from "../src/paths.js";
import { searchEntities } from "../src/search.js";

const NAMESPACE = "apps/crm";
const PLURAL = "contacts";
const PREFIX = "ct";

let workspace: string;

beforeEach(() => {
  workspace = mkdtempSync(join(tmpdir(), "upjack-search-"));
});

function populateWorkspace() {
  const contacts = [
    { first_name: "Sarah", last_name: "Chen", email: "sarah@acme.com", lead_score: 85 },
    { first_name: "James", last_name: "Park", email: "james@acme.com", lead_score: 45 },
    { first_name: "Alice", last_name: "Wong", email: "alice@bigcorp.com", lead_score: 72 },
    {
      first_name: "Bob",
      last_name: "Smith",
      email: "bob@startup.io",
      lead_score: 30,
      tags: ["cold-lead"],
    },
  ];
  for (const data of contacts) {
    createEntity(workspace, NAMESPACE, "contact", PLURAL, PREFIX, data);
  }
}

describe("text search", () => {
  it("searches by first name", () => {
    populateWorkspace();
    const results = searchEntities(workspace, NAMESPACE, PLURAL, "Sarah");
    expect(results).toHaveLength(1);
    expect(results[0].first_name).toBe("Sarah");
  });

  it("case insensitive", () => {
    populateWorkspace();
    const results = searchEntities(workspace, NAMESPACE, PLURAL, "sarah");
    expect(results).toHaveLength(1);
  });

  it("searches by email domain", () => {
    populateWorkspace();
    const results = searchEntities(workspace, NAMESPACE, PLURAL, "acme");
    expect(results).toHaveLength(2);
  });

  it("no match returns empty", () => {
    populateWorkspace();
    const results = searchEntities(workspace, NAMESPACE, PLURAL, "zzzznotfound");
    expect(results).toHaveLength(0);
  });

  it("partial match", () => {
    populateWorkspace();
    const results = searchEntities(workspace, NAMESPACE, PLURAL, "ark");
    expect(results).toHaveLength(1);
    expect(results[0].last_name).toBe("Park");
  });
});

describe("structured filters", () => {
  it("equality filter", () => {
    populateWorkspace();
    const results = searchEntities(workspace, NAMESPACE, PLURAL, undefined, {
      first_name: "Alice",
    });
    expect(results).toHaveLength(1);
    expect(results[0].first_name).toBe("Alice");
  });

  it("$gte filter", () => {
    populateWorkspace();
    const results = searchEntities(workspace, NAMESPACE, PLURAL, undefined, {
      lead_score: { $gte: 70 },
    });
    expect(results).toHaveLength(2);
    const scores = new Set(results.map((r) => r.lead_score));
    expect(scores).toEqual(new Set([85, 72]));
  });

  it("$lt filter", () => {
    populateWorkspace();
    const results = searchEntities(workspace, NAMESPACE, PLURAL, undefined, {
      lead_score: { $lt: 50 },
    });
    expect(results).toHaveLength(2);
    const scores = new Set(results.map((r) => r.lead_score));
    expect(scores).toEqual(new Set([45, 30]));
  });

  it("$ne filter", () => {
    populateWorkspace();
    const results = searchEntities(workspace, NAMESPACE, PLURAL, undefined, {
      first_name: { $ne: "Sarah" },
    });
    expect(results).toHaveLength(3);
    const names = new Set(results.map((r) => r.first_name));
    expect(names.has("Sarah")).toBe(false);
  });

  it("$in filter", () => {
    populateWorkspace();
    const results = searchEntities(workspace, NAMESPACE, PLURAL, undefined, {
      first_name: { $in: ["Sarah", "Bob"] },
    });
    expect(results).toHaveLength(2);
  });

  it("$contains filter", () => {
    populateWorkspace();
    const results = searchEntities(workspace, NAMESPACE, PLURAL, undefined, {
      tags: { $contains: "cold-lead" },
    });
    expect(results).toHaveLength(1);
    expect(results[0].first_name).toBe("Bob");
  });

  it("$exists true filter", () => {
    populateWorkspace();
    const results = searchEntities(workspace, NAMESPACE, PLURAL, undefined, {
      lead_score: { $exists: true },
    });
    expect(results).toHaveLength(4);
  });

  it("$gt filter strictly greater", () => {
    populateWorkspace();
    const results = searchEntities(workspace, NAMESPACE, PLURAL, undefined, {
      lead_score: { $gt: 72 },
    });
    expect(results).toHaveLength(1);
    expect(results[0].lead_score).toBe(85);
  });

  it("$lte includes equal", () => {
    populateWorkspace();
    const results = searchEntities(workspace, NAMESPACE, PLURAL, undefined, {
      lead_score: { $lte: 45 },
    });
    expect(results).toHaveLength(2);
    const scores = new Set(results.map((r) => r.lead_score));
    expect(scores).toEqual(new Set([45, 30]));
  });

  it("$exists false for missing field", () => {
    createEntity(workspace, NAMESPACE, "contact", PLURAL, PREFIX, {
      first_name: "Alice",
      last_name: "W",
      nickname: "Ali",
    });
    createEntity(workspace, NAMESPACE, "contact", PLURAL, PREFIX, {
      first_name: "Bob",
      last_name: "S",
    });

    const results = searchEntities(workspace, NAMESPACE, PLURAL, undefined, {
      nickname: { $exists: false },
    });
    expect(results).toHaveLength(1);
    expect(results[0].first_name).toBe("Bob");
  });

  it("combined text and filter", () => {
    populateWorkspace();
    const results = searchEntities(workspace, NAMESPACE, PLURAL, "acme", {
      lead_score: { $gte: 70 },
    });
    expect(results).toHaveLength(1);
    expect(results[0].first_name).toBe("Sarah");
  });
});

describe("sorting", () => {
  it("ascending sort", () => {
    populateWorkspace();
    const results = searchEntities(
      workspace,
      NAMESPACE,
      PLURAL,
      undefined,
      undefined,
      "lead_score",
    );
    const scores = results.map((r) => r.lead_score as number);
    expect(scores).toEqual([...scores].sort((a, b) => a - b));
  });

  it("descending sort", () => {
    populateWorkspace();
    const results = searchEntities(
      workspace,
      NAMESPACE,
      PLURAL,
      undefined,
      undefined,
      "-lead_score",
    );
    const scores = results.map((r) => r.lead_score as number);
    expect(scores).toEqual([...scores].sort((a, b) => b - a));
  });

  it("sort by name ascending", () => {
    populateWorkspace();
    const results = searchEntities(
      workspace,
      NAMESPACE,
      PLURAL,
      undefined,
      undefined,
      "first_name",
    );
    const names = results.map((r) => r.first_name);
    expect(names).toEqual([...names].sort());
  });
});

describe("limit and edge cases", () => {
  it("respects limit", () => {
    populateWorkspace();
    const results = searchEntities(
      workspace,
      NAMESPACE,
      PLURAL,
      undefined,
      undefined,
      "-updated_at",
      2,
    );
    expect(results).toHaveLength(2);
  });

  it("empty directory returns empty", () => {
    const results = searchEntities(workspace, NAMESPACE, PLURAL);
    expect(results).toEqual([]);
  });

  it("excludes deleted by default", () => {
    populateWorkspace();
    const all = searchEntities(workspace, NAMESPACE, PLURAL);
    const entityId = all[0].id;
    deleteEntity(workspace, NAMESPACE, PLURAL, entityId);

    const results = searchEntities(workspace, NAMESPACE, PLURAL);
    expect(results).toHaveLength(3);
    expect(results.every((r) => r.id !== entityId)).toBe(true);
  });

  it("includes deleted when filtered", () => {
    populateWorkspace();
    const all = searchEntities(workspace, NAMESPACE, PLURAL);
    const entityId = all[0].id;
    deleteEntity(workspace, NAMESPACE, PLURAL, entityId);

    const results = searchEntities(workspace, NAMESPACE, PLURAL, undefined, {
      status: "deleted",
    });
    expect(results).toHaveLength(1);
    expect(results[0].id).toBe(entityId);
  });

  it("skips corrupt JSON", () => {
    createEntity(workspace, NAMESPACE, "contact", PLURAL, PREFIX, { first_name: "Valid" });
    const dir = entityDir(workspace, NAMESPACE, PLURAL);
    writeFileSync(join(dir, "corrupt.json"), "{not valid json");

    const results = searchEntities(workspace, NAMESPACE, PLURAL, "Valid");
    expect(results).toHaveLength(1);
    expect(results[0].first_name).toBe("Valid");
  });
});
