import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { indexPath } from "../src/paths.js";
import {
  loadIndex,
  queryReverse,
  rebuildIndex,
  removeFromIndex,
  saveIndex,
  updateIndex,
} from "../src/relations.js";

const NAMESPACE = "apps/crm";
let workspace: string;

beforeEach(() => {
  workspace = mkdtempSync(join(tmpdir(), "upjack-relations-"));
});

describe("loadIndex / saveIndex", () => {
  it("returns empty index for nonexistent file", () => {
    const index = loadIndex(workspace, NAMESPACE);
    expect(index).toEqual({ reverse: {} });
  });

  it("round-trips save then load", () => {
    const index = {
      reverse: {
        co_01FAKE: [{ source: "ct_01FAKE", rel: "works_at" }],
      },
    };
    saveIndex(workspace, NAMESPACE, index);
    const loaded = loadIndex(workspace, NAMESPACE);
    expect(loaded).toEqual(index);
  });

  it("creates directory if missing", () => {
    const path = indexPath(workspace, NAMESPACE);
    expect(existsSync(path)).toBe(false);
    saveIndex(workspace, NAMESPACE, { reverse: {} });
    expect(existsSync(path)).toBe(true);
  });

  it("returns empty index for corrupt JSON", () => {
    const dir = join(workspace, NAMESPACE, "data", "_index");
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, "relations.json"), "NOT JSON{{{");
    const index = loadIndex(workspace, NAMESPACE);
    expect(index).toEqual({ reverse: {} });
  });
});

describe("updateIndex", () => {
  it("adds new relationships to index", () => {
    updateIndex(workspace, NAMESPACE, "ct_01A", [], [{ rel: "works_at", target: "co_01B" }]);
    const index = loadIndex(workspace, NAMESPACE);
    expect(index.reverse.co_01B).toEqual([{ source: "ct_01A", rel: "works_at" }]);
  });

  it("changes target: removes old, adds new", () => {
    updateIndex(workspace, NAMESPACE, "ct_01A", [], [{ rel: "works_at", target: "co_01B" }]);
    updateIndex(
      workspace,
      NAMESPACE,
      "ct_01A",
      [{ rel: "works_at", target: "co_01B" }],
      [{ rel: "works_at", target: "co_01C" }],
    );
    const index = loadIndex(workspace, NAMESPACE);
    expect(index.reverse.co_01B).toBeUndefined();
    expect(index.reverse.co_01C).toEqual([{ source: "ct_01A", rel: "works_at" }]);
  });

  it("removes all relationships: cleans up index", () => {
    updateIndex(workspace, NAMESPACE, "ct_01A", [], [{ rel: "works_at", target: "co_01B" }]);
    updateIndex(workspace, NAMESPACE, "ct_01A", [{ rel: "works_at", target: "co_01B" }], []);
    const index = loadIndex(workspace, NAMESPACE);
    expect(index.reverse.co_01B).toBeUndefined();
  });

  it("no duplicates on repeated update", () => {
    updateIndex(workspace, NAMESPACE, "ct_01A", [], [{ rel: "works_at", target: "co_01B" }]);
    updateIndex(workspace, NAMESPACE, "ct_01A", [], [{ rel: "works_at", target: "co_01B" }]);
    const index = loadIndex(workspace, NAMESPACE);
    expect(index.reverse.co_01B).toHaveLength(1);
  });

  it("multiple sources can point to same target", () => {
    updateIndex(workspace, NAMESPACE, "ct_01A", [], [{ rel: "works_at", target: "co_01X" }]);
    updateIndex(workspace, NAMESPACE, "ct_01B", [], [{ rel: "works_at", target: "co_01X" }]);
    const index = loadIndex(workspace, NAMESPACE);
    expect(index.reverse.co_01X).toHaveLength(2);
  });
});

describe("removeFromIndex", () => {
  it("removes all entries for a source entity", () => {
    updateIndex(
      workspace,
      NAMESPACE,
      "ct_01A",
      [],
      [
        { rel: "works_at", target: "co_01B" },
        { rel: "knows", target: "ct_01C" },
      ],
    );
    removeFromIndex(workspace, NAMESPACE, "ct_01A", [
      { rel: "works_at", target: "co_01B" },
      { rel: "knows", target: "ct_01C" },
    ]);
    const index = loadIndex(workspace, NAMESPACE);
    expect(Object.keys(index.reverse)).toHaveLength(0);
  });

  it("preserves entries from other entities", () => {
    updateIndex(workspace, NAMESPACE, "ct_01A", [], [{ rel: "works_at", target: "co_01X" }]);
    updateIndex(workspace, NAMESPACE, "ct_01B", [], [{ rel: "works_at", target: "co_01X" }]);
    removeFromIndex(workspace, NAMESPACE, "ct_01A", [{ rel: "works_at", target: "co_01X" }]);
    const index = loadIndex(workspace, NAMESPACE);
    expect(index.reverse.co_01X).toHaveLength(1);
    expect(index.reverse.co_01X[0].source).toBe("ct_01B");
  });

  it("no-op for empty rels (does not create index file)", () => {
    removeFromIndex(workspace, NAMESPACE, "ct_01A", []);
    const path = indexPath(workspace, NAMESPACE);
    expect(existsSync(path)).toBe(false);
  });
});

describe("rebuildIndex", () => {
  it("rebuilds from entity files on disk", () => {
    const contactsDir = join(workspace, NAMESPACE, "data", "contacts");
    mkdirSync(contactsDir, { recursive: true });
    writeFileSync(
      join(contactsDir, "ct_01A.json"),
      JSON.stringify({
        id: "ct_01A",
        relationships: [{ rel: "works_at", target: "co_01B" }],
      }),
    );
    writeFileSync(
      join(contactsDir, "ct_01C.json"),
      JSON.stringify({
        id: "ct_01C",
        relationships: [{ rel: "works_at", target: "co_01B" }],
      }),
    );

    const index = rebuildIndex(workspace, NAMESPACE, [{ name: "contact", plural: "contacts" }]);
    expect(index.reverse.co_01B).toHaveLength(2);
  });

  it("skips corrupt JSON files", () => {
    const contactsDir = join(workspace, NAMESPACE, "data", "contacts");
    mkdirSync(contactsDir, { recursive: true });
    writeFileSync(join(contactsDir, "ct_01A.json"), "NOT JSON");
    writeFileSync(
      join(contactsDir, "ct_01B.json"),
      JSON.stringify({
        id: "ct_01B",
        relationships: [{ rel: "works_at", target: "co_01X" }],
      }),
    );

    const index = rebuildIndex(workspace, NAMESPACE, [{ name: "contact", plural: "contacts" }]);
    expect(index.reverse.co_01X).toHaveLength(1);
  });

  it("skips missing entity directories", () => {
    const index = rebuildIndex(workspace, NAMESPACE, [{ name: "contact", plural: "contacts" }]);
    expect(index).toEqual({ reverse: {} });
  });
});

describe("queryReverse", () => {
  it("returns entries for target ID", () => {
    updateIndex(workspace, NAMESPACE, "ct_01A", [], [{ rel: "works_at", target: "co_01B" }]);
    const entries = queryReverse(workspace, NAMESPACE, "co_01B");
    expect(entries).toEqual([{ source: "ct_01A", rel: "works_at" }]);
  });

  it("filters by rel type", () => {
    updateIndex(
      workspace,
      NAMESPACE,
      "ct_01A",
      [],
      [
        { rel: "works_at", target: "co_01B" },
        { rel: "founded", target: "co_01B" },
      ],
    );
    const entries = queryReverse(workspace, NAMESPACE, "co_01B", "works_at");
    expect(entries).toHaveLength(1);
    expect(entries[0].rel).toBe("works_at");
  });

  it("returns empty for unknown target", () => {
    const entries = queryReverse(workspace, NAMESPACE, "unknown_01Z");
    expect(entries).toEqual([]);
  });

  it("auto-rebuilds when index missing and entityDefs provided", () => {
    const contactsDir = join(workspace, NAMESPACE, "data", "contacts");
    mkdirSync(contactsDir, { recursive: true });
    writeFileSync(
      join(contactsDir, "ct_01A.json"),
      JSON.stringify({
        id: "ct_01A",
        relationships: [{ rel: "works_at", target: "co_01B" }],
      }),
    );

    const entries = queryReverse(workspace, NAMESPACE, "co_01B", undefined, [
      { name: "contact", plural: "contacts" },
    ]);
    expect(entries).toHaveLength(1);
  });

  it("does NOT rebuild when entityDefs not provided", () => {
    const contactsDir = join(workspace, NAMESPACE, "data", "contacts");
    mkdirSync(contactsDir, { recursive: true });
    writeFileSync(
      join(contactsDir, "ct_01A.json"),
      JSON.stringify({
        id: "ct_01A",
        relationships: [{ rel: "works_at", target: "co_01B" }],
      }),
    );

    const entries = queryReverse(workspace, NAMESPACE, "co_01B");
    expect(entries).toEqual([]);
  });
});
