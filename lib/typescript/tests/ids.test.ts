import { describe, expect, it } from "vitest";
import { generateId, parseId, validateId } from "../src/ids.js";

describe("generateId", () => {
  it("generates a valid ID", () => {
    const result = generateId("ct");
    expect(validateId(result)).toBe(true);
    expect(result.startsWith("ct_")).toBe(true);
  });

  it("works with different prefixes", () => {
    for (const prefix of ["ct", "co", "dl", "act", "rpt"]) {
      const result = generateId(prefix);
      expect(result.startsWith(`${prefix}_`)).toBe(true);
      expect(validateId(result)).toBe(true);
    }
  });

  it("generates unique IDs", () => {
    const ids = new Set<string>();
    for (let i = 0; i < 100; i++) {
      ids.add(generateId("ct"));
    }
    expect(ids.size).toBe(100);
  });

  it("rejects prefix too short", () => {
    expect(() => generateId("c")).toThrow("Invalid prefix");
  });

  it("rejects prefix too long", () => {
    expect(() => generateId("contact")).toThrow("Invalid prefix");
  });

  it("rejects uppercase prefix", () => {
    expect(() => generateId("CT")).toThrow("Invalid prefix");
  });

  it("rejects numeric prefix", () => {
    expect(() => generateId("12")).toThrow("Invalid prefix");
  });
});

describe("parseId", () => {
  it("parses a valid ID", () => {
    const entityId = generateId("ct");
    const [prefix, ulidStr] = parseId(entityId);
    expect(prefix).toBe("ct");
    expect(ulidStr).toHaveLength(26);
  });

  it("parses longer prefix", () => {
    const entityId = generateId("act");
    const [prefix] = parseId(entityId);
    expect(prefix).toBe("act");
  });

  it("rejects invalid ID", () => {
    expect(() => parseId("bad_id")).toThrow("Invalid entity ID");
  });
});

describe("validateId", () => {
  it("validates correct IDs", () => {
    const entityId = generateId("ct");
    expect(validateId(entityId)).toBe(true);
  });

  it("rejects invalid formats", () => {
    expect(validateId("not-an-id")).toBe(false);
    expect(validateId("")).toBe(false);
    expect(validateId("ct_short")).toBe(false);
    expect(validateId("CT_01JKXM9V3QWERTY123456ABCDF")).toBe(false);
  });
});
