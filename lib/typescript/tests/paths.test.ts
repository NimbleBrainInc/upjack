import { mkdirSync } from "node:fs";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { entityDir, entityPath, resolveRoot, schemaDir } from "../src/paths.js";

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

describe("resolveRoot", () => {
  const originalEnv = process.env.UPJACK_ROOT;

  afterEach(() => {
    if (originalEnv !== undefined) {
      process.env.UPJACK_ROOT = originalEnv;
    } else {
      // biome-ignore lint/performance/noDelete: env var cleanup requires delete
      delete process.env.UPJACK_ROOT;
    }
  });

  it("uses env var when set", () => {
    process.env.UPJACK_ROOT = "/custom/root";
    expect(resolveRoot()).toBe(resolve("/custom/root"));
  });

  it("uses cliRoot when no env var", () => {
    // biome-ignore lint/performance/noDelete: env var cleanup requires delete
    delete process.env.UPJACK_ROOT;
    expect(resolveRoot("/explicit")).toBe(resolve("/explicit"));
  });

  it("falls back to .upjack", () => {
    // biome-ignore lint/performance/noDelete: env var cleanup requires delete
    delete process.env.UPJACK_ROOT;
    expect(resolveRoot()).toBe(resolve(".upjack"));
  });

  it("env var beats cliRoot", () => {
    process.env.UPJACK_ROOT = "/from-env";
    expect(resolveRoot("/from-cli")).toBe(resolve("/from-env"));
  });
});
