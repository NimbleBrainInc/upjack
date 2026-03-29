import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { UpjackApp } from "../src/app.js";
import { validateId } from "../src/ids.js";

const NAMESPACE = "apps/crm";
const ENTITIES = [
  { name: "contact", plural: "contacts", schema: "schemas/contact.schema.json", prefix: "ct" },
  { name: "company", plural: "companies", schema: "schemas/company.schema.json", prefix: "co" },
];

let workspace: string;

beforeEach(() => {
  workspace = mkdtempSync(join(tmpdir(), "upjack-app-"));
});

describe("UpjackApp", () => {
  it("creates entity", () => {
    const app = new UpjackApp(NAMESPACE, ENTITIES, workspace);
    const result = app.createEntity("contact", { first_name: "Sarah", last_name: "Chen" });
    expect(validateId(result.id)).toBe(true);
    expect(result.id.startsWith("ct_")).toBe(true);
    expect(result.type).toBe("contact");
    expect(result.first_name).toBe("Sarah");
  });

  it("gets entity", () => {
    const app = new UpjackApp(NAMESPACE, ENTITIES, workspace);
    const created = app.createEntity("contact", { first_name: "Sarah" });
    const result = app.getEntity("contact", created.id);
    expect(result.id).toBe(created.id);
    expect(result.first_name).toBe("Sarah");
  });

  it("updates entity", () => {
    const app = new UpjackApp(NAMESPACE, ENTITIES, workspace);
    const created = app.createEntity("contact", { first_name: "Sarah" });
    const updated = app.updateEntity("contact", created.id, { last_name: "Chen" });
    expect(updated.first_name).toBe("Sarah");
    expect(updated.last_name).toBe("Chen");
  });

  it("lists entities", () => {
    const app = new UpjackApp(NAMESPACE, ENTITIES, workspace);
    app.createEntity("contact", { first_name: "Alice" });
    app.createEntity("contact", { first_name: "Bob" });
    const results = app.listEntities("contact");
    expect(results).toHaveLength(2);
  });

  it("deletes entity", () => {
    const app = new UpjackApp(NAMESPACE, ENTITIES, workspace);
    const created = app.createEntity("contact", { first_name: "Sarah" });
    const result = app.deleteEntity("contact", created.id);
    expect(result.status).toBe("deleted");
  });

  it("multiple entity types", () => {
    const app = new UpjackApp(NAMESPACE, ENTITIES, workspace);
    const contact = app.createEntity("contact", { first_name: "Sarah" });
    const company = app.createEntity("company", { name: "Acme Corp" });
    expect(contact.id.startsWith("ct_")).toBe(true);
    expect(company.id.startsWith("co_")).toBe(true);
  });

  it("unknown entity type throws", () => {
    const app = new UpjackApp(NAMESPACE, ENTITIES, workspace);
    expect(() => app.createEntity("nonexistent", { name: "test" })).toThrow("Unknown entity type");
  });

  it("default plural", () => {
    const app = new UpjackApp(
      NAMESPACE,
      [{ name: "deal", schema: "schemas/deal.schema.json", prefix: "dl" }],
      workspace,
    );
    const result = app.createEntity("deal", { title: "Big Deal" });
    expect(result.type).toBe("deal");
    const path = join(workspace, NAMESPACE, "data", "deals", `${result.id}.json`);
    expect(existsSync(path)).toBe(true);
  });

  it("searches entities", () => {
    const app = new UpjackApp(NAMESPACE, ENTITIES, workspace);
    app.createEntity("contact", { first_name: "Sarah", last_name: "Chen" });
    app.createEntity("contact", { first_name: "James", last_name: "Park" });

    const results = app.searchEntities("contact", { query: "Sarah" });
    expect(results).toHaveLength(1);
    expect(results[0].first_name).toBe("Sarah");
  });

  it("searches with filter", () => {
    const app = new UpjackApp(NAMESPACE, ENTITIES, workspace);
    app.createEntity("contact", { first_name: "Sarah", lead_score: 90 });
    app.createEntity("contact", { first_name: "James", lead_score: 40 });

    const results = app.searchEntities("contact", {
      filter: { lead_score: { $gte: 70 } },
    });
    expect(results).toHaveLength(1);
    expect(results[0].first_name).toBe("Sarah");
  });
});

describe("fromManifest", () => {
  it("loads from manifest", () => {
    const manifest = {
      manifest_version: "0.4",
      name: "@nimblebraininc/crm",
      version: "1.0.0",
      _meta: {
        "ai.nimblebrain/upjack": {
          upjack_version: "0.1",
          namespace: "apps/crm",
          entities: [
            {
              name: "contact",
              plural: "contacts",
              schema: "schemas/contact.schema.json",
              prefix: "ct",
            },
          ],
        },
      },
    };

    const manifestPath = join(workspace, "manifest.json");
    writeFileSync(manifestPath, JSON.stringify(manifest));

    const app = UpjackApp.fromManifest(manifestPath, workspace);
    expect(app.namespace).toBe("apps/crm");

    const result = app.createEntity("contact", { first_name: "Sarah" });
    expect(result.id.startsWith("ct_")).toBe(true);
  });

  it("loads schemas and validates", () => {
    const schemasDir = join(workspace, "schemas");
    mkdirSync(schemasDir, { recursive: true });
    const schema = {
      $schema: "https://json-schema.org/draft/2020-12/schema",
      type: "object",
      properties: { name: { type: "string" }, value: { type: "integer", minimum: 0 } },
      required: ["name"],
    };
    writeFileSync(join(schemasDir, "widget.schema.json"), JSON.stringify(schema));

    const manifest = {
      manifest_version: "0.4",
      name: "test",
      version: "1.0.0",
      _meta: {
        "ai.nimblebrain/upjack": {
          upjack_version: "0.1",
          namespace: "test",
          entities: [
            {
              name: "widget",
              plural: "widgets",
              prefix: "wg",
              schema: "schemas/widget.schema.json",
            },
          ],
        },
      },
    };
    writeFileSync(join(workspace, "manifest.json"), JSON.stringify(manifest));

    const app = UpjackApp.fromManifest(join(workspace, "manifest.json"), workspace);
    expect(app._schemas.widget).toBeDefined();

    const widget = app.createEntity("widget", { name: "Gizmo", value: 42 });
    expect(widget.name).toBe("Gizmo");

    // Missing required "name"
    expect(() => app.createEntity("widget", { value: 100 })).toThrow("Validation failed");

    // Negative value
    expect(() => app.createEntity("widget", { name: "Bad", value: -5 })).toThrow(
      "Validation failed",
    );
  });

  it("missing _meta raises", () => {
    const manifest = { manifest_version: "0.4", name: "test", version: "1.0.0" };
    writeFileSync(join(workspace, "manifest.json"), JSON.stringify(manifest));
    expect(() => UpjackApp.fromManifest(join(workspace, "manifest.json"))).toThrow(
      "missing upjack extension",
    );
  });

  it("missing namespace raises", () => {
    const manifest = {
      manifest_version: "0.4",
      name: "test",
      version: "1.0.0",
      _meta: {
        "ai.nimblebrain/upjack": { upjack_version: "0.1", entities: [] },
      },
    };
    writeFileSync(join(workspace, "manifest.json"), JSON.stringify(manifest));
    expect(() => UpjackApp.fromManifest(join(workspace, "manifest.json"))).toThrow(
      "missing required field 'namespace'",
    );
  });

  it("missing entities raises", () => {
    const manifest = {
      manifest_version: "0.4",
      name: "test",
      version: "1.0.0",
      _meta: {
        "ai.nimblebrain/upjack": { upjack_version: "0.1", namespace: "apps/crm" },
      },
    };
    writeFileSync(join(workspace, "manifest.json"), JSON.stringify(manifest));
    expect(() => UpjackApp.fromManifest(join(workspace, "manifest.json"))).toThrow(
      "missing required field 'entities'",
    );
  });

  it("wrong vendor key raises", () => {
    const manifest = {
      manifest_version: "0.4",
      name: "test",
      version: "1.0.0",
      _meta: { "some.other/extension": { data: true } },
    };
    writeFileSync(join(workspace, "manifest.json"), JSON.stringify(manifest));
    expect(() => UpjackApp.fromManifest(join(workspace, "manifest.json"))).toThrow(
      "missing upjack extension",
    );
  });
});
