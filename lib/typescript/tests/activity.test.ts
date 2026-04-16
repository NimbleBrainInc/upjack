import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { ACTIVITY_ENTITY_DEF, getActivitySchema } from "../src/activity.js";
import { UpjackApp } from "../src/app.js";
import type { EntityDefinition } from "../src/entity.js";

describe("ACTIVITY_ENTITY_DEF", () => {
  it("has correct fields", () => {
    expect(ACTIVITY_ENTITY_DEF.name).toBe("activity");
    expect(ACTIVITY_ENTITY_DEF.plural).toBe("activities");
    expect(ACTIVITY_ENTITY_DEF.prefix).toBe("act");
    expect(ACTIVITY_ENTITY_DEF.schema).toBeDefined();
  });
});

describe("getActivitySchema", () => {
  it("returns schema with allOf", () => {
    const schema = getActivitySchema();
    expect(schema.allOf).toBeDefined();
  });

  it("schema has action property", () => {
    const schema = getActivitySchema();
    const props = schema.properties as Record<string, Record<string, unknown>>;
    expect(props.action).toBeDefined();
    expect(props.action.type).toBe("string");
  });
});

describe("manifest activities", () => {
  let workspace: string;
  let manifestDir: string;

  beforeEach(() => {
    workspace = mkdtempSync(join(tmpdir(), "upjack-activity-"));
    manifestDir = join(workspace, "app");
    mkdirSync(join(manifestDir, "schemas"), { recursive: true });
    writeFileSync(
      join(manifestDir, "schemas", "contact.schema.json"),
      JSON.stringify({
        allOf: [
          { $ref: "https://upjack.dev/schemas/v1/upjack-entity.schema.json" },
          { type: "object", properties: { first_name: { type: "string" } } },
        ],
      }),
    );
  });

  function writeManifest(activities: boolean | undefined) {
    const manifest: Record<string, unknown> = {
      _meta: {
        "ai.nimblebrain/upjack": {
          upjack_version: "0.1",
          namespace: "apps/crm",
          entities: [
            {
              name: "contact",
              plural: "contacts",
              prefix: "ct",
              schema: "schemas/contact.schema.json",
            },
          ],
          ...(activities !== undefined ? { activities } : {}),
        },
      },
    };
    const path = join(manifestDir, "manifest.json");
    writeFileSync(path, JSON.stringify(manifest));
    return path;
  }

  it("activities: true registers activity entity type", () => {
    const app = UpjackApp.fromManifest(writeManifest(true), workspace);
    expect(() => app.logActivity("ct_01FAKE00000000000000000000", "test")).not.toThrow();
  });

  it("activities: false does not register", () => {
    const app = UpjackApp.fromManifest(writeManifest(false), workspace);
    expect(() => app.logActivity("ct_01FAKE00000000000000000000", "test")).toThrow(
      "Unknown entity type",
    );
  });

  it("activities absent does not register", () => {
    const app = UpjackApp.fromManifest(writeManifest(undefined), workspace);
    expect(() => app.logActivity("ct_01FAKE00000000000000000000", "test")).toThrow(
      "Unknown entity type",
    );
  });

  it("activities: true with user activity entity throws", () => {
    const manifest = {
      _meta: {
        "ai.nimblebrain/upjack": {
          upjack_version: "0.1",
          namespace: "apps/crm",
          entities: [
            {
              name: "activity",
              plural: "activities",
              prefix: "act",
              schema: "schemas/contact.schema.json",
            },
          ],
          activities: true,
        },
      },
    };
    const path = join(manifestDir, "manifest.json");
    writeFileSync(path, JSON.stringify(manifest));
    expect(() => UpjackApp.fromManifest(path, workspace)).toThrow(
      "Cannot enable built-in activities",
    );
  });
});

describe("logActivity", () => {
  let workspace: string;
  let app: UpjackApp;

  const ENTITIES: EntityDefinition[] = [
    { name: "contact", plural: "contacts", prefix: "ct", schema: "schemas/contact.schema.json" },
    ACTIVITY_ENTITY_DEF,
  ];

  beforeEach(() => {
    workspace = mkdtempSync(join(tmpdir(), "upjack-activity-"));
    app = new UpjackApp("apps/crm", ENTITIES, workspace);
  });

  it("creates activity entity with action", () => {
    const contact = app.createEntity("contact", { first_name: "Sarah" });
    const activity = app.logActivity(contact.id, "email_sent");
    expect(activity.type).toBe("activity");
    expect(activity.action).toBe("email_sent");
    expect(activity.id.startsWith("act_")).toBe(true);
  });

  it("auto-wires subject relationship", () => {
    const contact = app.createEntity("contact", { first_name: "Sarah" });
    const activity = app.logActivity(contact.id, "called");
    expect(activity.relationships).toHaveLength(1);
    expect(activity.relationships[0].rel).toBe("subject");
    expect(activity.relationships[0].target).toBe(contact.id);
  });

  it("uses created_by system", () => {
    const contact = app.createEntity("contact", { first_name: "Sarah" });
    const activity = app.logActivity(contact.id, "called");
    expect(activity.created_by).toBe("system");
  });

  it("works with detail dict", () => {
    const contact = app.createEntity("contact", { first_name: "Sarah" });
    const activity = app.logActivity(contact.id, "email_sent", { subject: "Hello" });
    expect(activity.detail).toEqual({ subject: "Hello" });
  });

  it("detail defaults to empty object", () => {
    const contact = app.createEntity("contact", { first_name: "Sarah" });
    const activity = app.logActivity(contact.id, "called");
    expect(activity.detail).toEqual({});
  });

  it("throws when activity type not registered", () => {
    const noActivityApp = new UpjackApp("apps/crm", [ENTITIES[0]], workspace);
    expect(() => noActivityApp.logActivity("ct_01FAKE", "test")).toThrow("Unknown entity type");
  });
});

describe("getActivities", () => {
  let workspace: string;
  let app: UpjackApp;

  const ENTITIES: EntityDefinition[] = [
    { name: "contact", plural: "contacts", prefix: "ct", schema: "schemas/contact.schema.json" },
    ACTIVITY_ENTITY_DEF,
  ];

  beforeEach(() => {
    workspace = mkdtempSync(join(tmpdir(), "upjack-activity-"));
    app = new UpjackApp("apps/crm", ENTITIES, workspace);
  });

  it("returns activities for subject", () => {
    const contact = app.createEntity("contact", { first_name: "Sarah" });
    app.logActivity(contact.id, "called");
    app.logActivity(contact.id, "email_sent");

    const activities = app.getActivities(contact.id);
    expect(activities).toHaveLength(2);
  });

  it("filters by action", () => {
    const contact = app.createEntity("contact", { first_name: "Sarah" });
    app.logActivity(contact.id, "called");
    app.logActivity(contact.id, "email_sent");

    const activities = app.getActivities(contact.id, "called");
    expect(activities).toHaveLength(1);
    expect(activities[0].action).toBe("called");
  });

  it("returns empty when no activities", () => {
    const contact = app.createEntity("contact", { first_name: "Sarah" });
    const activities = app.getActivities(contact.id);
    expect(activities).toHaveLength(0);
  });

  it("multiple subjects are isolated", () => {
    const sarah = app.createEntity("contact", { first_name: "Sarah" });
    const bob = app.createEntity("contact", { first_name: "Bob" });
    app.logActivity(sarah.id, "called");
    app.logActivity(bob.id, "email_sent");

    const sarahActivities = app.getActivities(sarah.id);
    expect(sarahActivities).toHaveLength(1);
    expect(sarahActivities[0].action).toBe("called");
  });

  it("respects limit", () => {
    const contact = app.createEntity("contact", { first_name: "Sarah" });
    for (let i = 0; i < 5; i++) {
      app.logActivity(contact.id, `action_${i}`);
    }

    const activities = app.getActivities(contact.id, undefined, 2);
    expect(activities).toHaveLength(2);
  });

  it("throws when activity type not registered", () => {
    const noActivityApp = new UpjackApp("apps/crm", [ENTITIES[0]], workspace);
    expect(() => noActivityApp.getActivities("ct_01FAKE")).toThrow("Unknown entity type");
  });
});
