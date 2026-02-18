import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { UpjackApp } from "../src/app.js";
import { init, main, makePrefix, slugify } from "../src/cli.js";

// ---------------------------------------------------------------------------
// Unit tests: slugify
// ---------------------------------------------------------------------------

describe("slugify", () => {
  it("converts spaces to hyphens", () => {
    expect(slugify("My App")).toBe("my-app");
  });

  it("returns already-slugged names unchanged", () => {
    expect(slugify("my-app")).toBe("my-app");
  });

  it("strips leading and trailing hyphens from spaces", () => {
    expect(slugify(" hello world ")).toBe("hello-world");
  });
});

// ---------------------------------------------------------------------------
// Unit tests: makePrefix
// ---------------------------------------------------------------------------

describe("makePrefix", () => {
  it("short name (<=4 chars) stays as-is", () => {
    expect(makePrefix("note")).toBe("note");
  });

  it("two char name", () => {
    expect(makePrefix("ab")).toBe("ab");
  });

  it("long name produces 2-4 char alpha prefix", () => {
    const prefix = makePrefix("contact");
    expect(prefix.length).toBeGreaterThanOrEqual(2);
    expect(prefix.length).toBeLessThanOrEqual(4);
    expect(prefix).toMatch(/^[a-z]+$/);
  });
});

// ---------------------------------------------------------------------------
// Integration tests: init
// ---------------------------------------------------------------------------

describe("init", () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = mkdtempSync(join(tmpdir(), "upjack-cli-"));
  });

  it("creates directory structure", async () => {
    const target = join(tmpDir, "my-app");
    await init([target, "--name", "my-app", "--entity", "note"]);

    expect(existsSync(join(target, "manifest.json"))).toBe(true);
    expect(existsSync(join(target, "server.ts"))).toBe(true);
    expect(existsSync(join(target, "context.md"))).toBe(true);
    expect(existsSync(join(target, "schemas", "note.schema.json"))).toBe(true);
    expect(existsSync(join(target, "seed", "sample-notes.json"))).toBe(true);
    expect(existsSync(join(target, "skills"))).toBe(true);
  });

  it("manifest has correct content", async () => {
    const target = join(tmpDir, "test-app");
    await init([target, "--name", "test-app", "--entity", "task"]);

    const manifest = JSON.parse(readFileSync(join(target, "manifest.json"), "utf-8"));
    expect(manifest.name).toBe("test-app");
    expect(manifest.title).toBe("Test App");

    const upjack = manifest._meta["ai.nimblebrain/upjack"];
    expect(upjack.namespace).toBe("apps/test-app");
    expect(upjack.entities).toHaveLength(1);
    expect(upjack.entities[0].name).toBe("task");
    expect(upjack.entities[0].prefix).toBe("task");
  });

  it("schema is valid JSON Schema", async () => {
    const target = join(tmpDir, "app");
    await init([target, "--name", "app", "--entity", "item"]);

    const schema = JSON.parse(readFileSync(join(target, "schemas", "item.schema.json"), "utf-8"));
    expect(schema.$schema).toBe("https://json-schema.org/draft/2020-12/schema");
    expect(schema.allOf).toBeDefined();
    expect(schema.required).toContain("name");
  });

  it("server.ts references upjack/server", async () => {
    const target = join(tmpDir, "app");
    await init([target, "--name", "app", "--entity", "item"]);

    const content = readFileSync(join(target, "server.ts"), "utf-8");
    expect(content).toContain("startServer");
    expect(content).toContain("manifest.json");
  });

  it("refuses nonempty directory", async () => {
    const target = join(tmpDir, "existing");
    mkdirSync(target);
    writeFileSync(join(target, "file.txt"), "exists");

    const exitSpy = vi.spyOn(process, "exit").mockImplementation(() => {
      throw new Error("process.exit");
    });

    await expect(init([target, "--name", "existing", "--entity", "item"])).rejects.toThrow(
      "process.exit",
    );
    expect(exitSpy).toHaveBeenCalledWith(1);

    exitSpy.mockRestore();
  });

  it("generated app loads with UpjackApp", async () => {
    const target = join(tmpDir, "app");
    await init([target, "--name", "app", "--entity", "note"]);

    const workspace = join(tmpDir, "workspace");
    const app = UpjackApp.fromManifest(join(target, "manifest.json"), workspace);
    const note = app.createEntity("note", { name: "Test" });
    expect(note.type).toBe("note");
    expect(note.name).toBe("Test");
    expect((note.id as string).startsWith("note_")).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// main entrypoint
// ---------------------------------------------------------------------------

describe("main", () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = mkdtempSync(join(tmpdir(), "upjack-main-"));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("no command exits with 1", async () => {
    vi.spyOn(process, "argv", "get").mockReturnValue(["node", "cli.js"]);
    const exitSpy = vi.spyOn(process, "exit").mockImplementation(() => {
      throw new Error("process.exit");
    });

    await expect(main()).rejects.toThrow("process.exit");
    expect(exitSpy).toHaveBeenCalledWith(1);
  });

  it("init command creates app", async () => {
    const target = join(tmpDir, "cli-test");
    vi.spyOn(process, "argv", "get").mockReturnValue([
      "node",
      "cli.js",
      "init",
      target,
      "--name",
      "cli-test",
      "--entity",
      "item",
    ]);

    await main();
    expect(existsSync(join(target, "manifest.json"))).toBe(true);
  });
});
