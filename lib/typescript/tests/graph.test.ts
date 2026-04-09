import { existsSync } from "node:fs";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { UpjackApp } from "../src/app.js";
import type { EntityDefinition } from "../src/entity.js";
import { indexPath } from "../src/paths.js";

let workspace: string;
let app: UpjackApp;

const ENTITIES: EntityDefinition[] = [
  { name: "contact", plural: "contacts", prefix: "ct", schema: "schemas/contact.schema.json" },
  { name: "company", plural: "companies", prefix: "co", schema: "schemas/company.schema.json" },
  { name: "deal", plural: "deals", prefix: "dl", schema: "schemas/deal.schema.json" },
];

beforeEach(() => {
  workspace = mkdtempSync(join(tmpdir(), "upjack-graph-"));
  app = new UpjackApp("apps/crm", ENTITIES, workspace);
});

describe("prefix resolution", () => {
  it("resolves known prefix to entity name", () => {
    expect(app._resolveType("ct_01FAKE00000000000000000000")).toBe("contact");
    expect(app._resolveType("co_01FAKE00000000000000000000")).toBe("company");
    expect(app._resolveType("dl_01FAKE00000000000000000000")).toBe("deal");
  });

  it("throws for unknown prefix", () => {
    expect(() => app._resolveType("xx_01FAKE00000000000000000000")).toThrow("Unknown prefix");
  });
});

describe("queryByRelationship", () => {
  it("returns entities with matching relationship", () => {
    const company = app.createEntity("company", { name: "Acme" });
    app.createEntity("contact", {
      first_name: "Sarah",
      relationships: [{ rel: "works_at", target: company.id }],
    });
    app.createEntity("contact", {
      first_name: "Bob",
      relationships: [{ rel: "works_at", target: company.id }],
    });

    const results = app.queryByRelationship("contact", "works_at", company.id);
    expect(results).toHaveLength(2);
  });

  it("filters to correct entity type", () => {
    const company = app.createEntity("company", { name: "Acme" });
    app.createEntity("contact", {
      first_name: "Sarah",
      relationships: [{ rel: "belongs_to", target: company.id }],
    });
    app.createEntity("deal", {
      title: "Big Deal",
      relationships: [{ rel: "belongs_to", target: company.id }],
    });

    const contacts = app.queryByRelationship("contact", "belongs_to", company.id);
    expect(contacts).toHaveLength(1);
    expect(contacts[0].type).toBe("contact");
  });

  it("applies equality filter", () => {
    const company = app.createEntity("company", { name: "Acme" });
    app.createEntity("contact", {
      first_name: "Sarah",
      role: "engineer",
      relationships: [{ rel: "works_at", target: company.id }],
    });
    app.createEntity("contact", {
      first_name: "Bob",
      role: "manager",
      relationships: [{ rel: "works_at", target: company.id }],
    });

    const results = app.queryByRelationship("contact", "works_at", company.id, {
      role: "engineer",
    });
    expect(results).toHaveLength(1);
    expect(results[0].first_name).toBe("Sarah");
  });

  it("throws on operator filter when there are matching entities", () => {
    const company = app.createEntity("company", { name: "Acme" });
    app.createEntity("contact", {
      first_name: "Sarah",
      age: 35,
      relationships: [{ rel: "works_at", target: company.id }],
    });

    expect(() =>
      app.queryByRelationship("contact", "works_at", company.id, { age: { $gt: 30 } }),
    ).toThrow("Operator filters");
  });

  it("respects limit", () => {
    const company = app.createEntity("company", { name: "Acme" });
    for (let i = 0; i < 5; i++) {
      app.createEntity("contact", {
        first_name: `Person${i}`,
        relationships: [{ rel: "works_at", target: company.id }],
      });
    }

    const results = app.queryByRelationship("contact", "works_at", company.id, undefined, 2);
    expect(results).toHaveLength(2);
  });

  it("excludes deleted entities", () => {
    const company = app.createEntity("company", { name: "Acme" });
    const contact = app.createEntity("contact", {
      first_name: "Sarah",
      relationships: [{ rel: "works_at", target: company.id }],
    });
    app.deleteEntity("contact", contact.id);

    const results = app.queryByRelationship("contact", "works_at", company.id);
    expect(results).toHaveLength(0);
  });

  it("returns empty for no matches", () => {
    const company = app.createEntity("company", { name: "Acme" });
    const results = app.queryByRelationship("contact", "works_at", company.id);
    expect(results).toHaveLength(0);
  });
});

describe("getRelated", () => {
  it("forward returns resolved target entities", () => {
    const company = app.createEntity("company", { name: "Acme" });
    const contact = app.createEntity("contact", {
      first_name: "Sarah",
      relationships: [{ rel: "works_at", target: company.id }],
    });

    const related = app.getRelated(contact.id, undefined, "forward");
    expect(related).toHaveLength(1);
    expect(related[0].id).toBe(company.id);
  });

  it("forward with rel filter", () => {
    const company = app.createEntity("company", { name: "Acme" });
    const other = app.createEntity("company", { name: "Other" });
    const contact = app.createEntity("contact", {
      first_name: "Sarah",
      relationships: [
        { rel: "works_at", target: company.id },
        { rel: "founded", target: other.id },
      ],
    });

    const related = app.getRelated(contact.id, "works_at", "forward");
    expect(related).toHaveLength(1);
    expect(related[0].id).toBe(company.id);
  });

  it("reverse returns entities pointing at this one", () => {
    const company = app.createEntity("company", { name: "Acme" });
    app.createEntity("contact", {
      first_name: "Sarah",
      relationships: [{ rel: "works_at", target: company.id }],
    });

    const related = app.getRelated(company.id, undefined, "reverse");
    expect(related).toHaveLength(1);
    expect(related[0].first_name).toBe("Sarah");
  });

  it("skips missing target entities", () => {
    const contact = app.createEntity("contact", {
      first_name: "Sarah",
      relationships: [{ rel: "works_at", target: "co_01NONEXISTENT0000000000000" }],
    });

    const related = app.getRelated(contact.id, undefined, "forward");
    expect(related).toHaveLength(0);
  });

  it("throws for invalid direction", () => {
    const contact = app.createEntity("contact", { first_name: "Sarah" });
    expect(() => app.getRelated(contact.id, undefined, "sideways" as "forward")).toThrow(
      "direction must be",
    );
  });

  it("empty relationships returns empty array", () => {
    const contact = app.createEntity("contact", { first_name: "Sarah" });
    const related = app.getRelated(contact.id, undefined, "forward");
    expect(related).toEqual([]);
  });
});

describe("getComposite", () => {
  it("includes forward and reverse relationships", () => {
    const company = app.createEntity("company", { name: "Acme" });
    const contact = app.createEntity("contact", {
      first_name: "Sarah",
      relationships: [{ rel: "works_at", target: company.id }],
    });

    const composite = app.getComposite("company", company.id);
    const related = composite._related as Record<string, unknown[]>;

    // Reverse: contact works_at company
    expect(related["~works_at"]).toHaveLength(1);
    expect((related["~works_at"][0] as { id: string }).id).toBe(contact.id);
  });

  it("forward rels keyed by rel name", () => {
    const company = app.createEntity("company", { name: "Acme" });
    const contact = app.createEntity("contact", {
      first_name: "Sarah",
      relationships: [{ rel: "works_at", target: company.id }],
    });

    const composite = app.getComposite("contact", contact.id);
    const related = composite._related as Record<string, unknown[]>;
    expect(related.works_at).toHaveLength(1);
    expect((related.works_at[0] as { id: string }).id).toBe(company.id);
  });

  it("depth 0 returns entity with empty _related", () => {
    const contact = app.createEntity("contact", { first_name: "Sarah" });
    const composite = app.getComposite("contact", contact.id, 0);
    expect(composite._related).toEqual({});
  });
});

describe("relationship index wiring", () => {
  it("creating entity with relationships updates reverse index", () => {
    const company = app.createEntity("company", { name: "Acme" });
    app.createEntity("contact", {
      first_name: "Sarah",
      relationships: [{ rel: "works_at", target: company.id }],
    });

    const path = indexPath(workspace, "apps/crm");
    expect(existsSync(path)).toBe(true);
  });

  it("hard deleting entity removes from reverse index", () => {
    const company = app.createEntity("company", { name: "Acme" });
    const contact = app.createEntity("contact", {
      first_name: "Sarah",
      relationships: [{ rel: "works_at", target: company.id }],
    });
    app.deleteEntity("contact", contact.id, true);

    const results = app.queryByRelationship("contact", "works_at", company.id);
    expect(results).toHaveLength(0);
  });
});
