import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { entityDir, entityPath, schemaDir } from "../src/paths.js";

describe("schemaDir", () => {
  it("returns correct path", () => {
    const result = schemaDir("/workspace", "apps/crm");
    expect(result).toBe("/workspace/apps/crm/schemas");
  });

  it("different namespaces produce different paths", () => {
    expect(schemaDir("/ws", "apps/crm")).not.toBe(schemaDir("/ws", "apps/research"));
  });
});

describe("path consistency", () => {
  it("entityPath is child of entityDir", () => {
    const dir = entityDir("/ws", "apps/crm", "contacts");
    const path = entityPath("/ws", "apps/crm", "contacts", "ct_01ABC");
    expect(path).toBe(`${dir}/ct_01ABC.json`);
  });
});

describe("path traversal", () => {
  it("rejects entity ID with traversal", () => {
    const root = mkdtempSync(join(tmpdir(), "upjack-"));
    mkdirSync(join(root, "workspace"), { recursive: true });
    const workspace = join(root, "workspace");

    expect(() =>
      entityPath(workspace, "apps/crm", "contacts", "../../../../../../etc/passwd"),
    ).toThrow("Path escapes workspace root");
  });

  it("rejects namespace with traversal", () => {
    const root = mkdtempSync(join(tmpdir(), "upjack-"));
    mkdirSync(join(root, "workspace"), { recursive: true });
    const workspace = join(root, "workspace");

    expect(() => entityDir(workspace, "../../etc", "contacts")).toThrow(
      "Path escapes workspace root",
    );
  });

  it("allows traversal within workspace", () => {
    const root = mkdtempSync(join(tmpdir(), "upjack-"));
    mkdirSync(join(root, "workspace"), { recursive: true });
    const workspace = join(root, "workspace");

    const path = entityPath(workspace, "apps/crm", "contacts", "../deals/dl_01FAKE");
    expect(resolve(path).startsWith(resolve(workspace))).toBe(true);
  });

  it("clean paths work", () => {
    const root = mkdtempSync(join(tmpdir(), "upjack-"));
    mkdirSync(join(root, "workspace"), { recursive: true });
    const workspace = join(root, "workspace");

    const path = entityPath(workspace, "apps/crm", "contacts", "ct_01ABCDEFGHIJKLMNOPQRSTUVWX");
    expect(path.endsWith("ct_01ABCDEFGHIJKLMNOPQRSTUVWX.json")).toBe(true);

    const dir = entityDir(workspace, "apps/crm", "contacts");
    expect(dir).toBe(`${workspace}/apps/crm/data/contacts`);
  });
});
