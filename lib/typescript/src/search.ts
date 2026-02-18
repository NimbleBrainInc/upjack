import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import type { EntityRecord } from "./entity.js";
import { entityDir } from "./paths.js";

function matchText(entity: EntityRecord, query: string): boolean {
  const q = query.toLowerCase();
  for (const value of Object.values(entity)) {
    if (typeof value === "string" && value.toLowerCase().includes(q)) {
      return true;
    }
  }
  return false;
}

function matchFilter(entity: EntityRecord, filters: Record<string, unknown>): boolean {
  for (const [key, condition] of Object.entries(filters)) {
    const value = entity[key];

    if (condition !== null && typeof condition === "object" && !Array.isArray(condition)) {
      const ops = condition as Record<string, unknown>;
      for (const [op, operand] of Object.entries(ops)) {
        if (op === "$gt") {
          if (value == null || (value as number) <= (operand as number)) return false;
        } else if (op === "$gte") {
          if (value == null || (value as number) < (operand as number)) return false;
        } else if (op === "$lt") {
          if (value == null || (value as number) >= (operand as number)) return false;
        } else if (op === "$lte") {
          if (value == null || (value as number) > (operand as number)) return false;
        } else if (op === "$ne") {
          if (value === operand) return false;
        } else if (op === "$in") {
          if (!(operand as unknown[]).includes(value)) return false;
        } else if (op === "$contains") {
          if (!Array.isArray(value) || !value.includes(operand)) return false;
        } else if (op === "$exists") {
          const exists = key in entity && entity[key] != null;
          if (exists !== operand) return false;
        }
      }
    } else {
      if (value !== condition) return false;
    }
  }
  return true;
}

function sortKey(entity: EntityRecord, field: string): string {
  const value = entity[field];
  if (value == null) return "";
  return String(value);
}

/**
 * Search entities with text query and structured filters.
 */
export function searchEntities(
  root: string,
  namespace: string,
  plural: string,
  query?: string,
  filter?: Record<string, unknown>,
  sort = "-updated_at",
  limit = 20,
): EntityRecord[] {
  const directory = entityDir(root, namespace, plural);
  if (!existsSync(directory)) {
    return [];
  }

  let entities: EntityRecord[] = [];
  for (const file of readdirSync(directory)) {
    if (!file.endsWith(".json")) continue;
    try {
      entities.push(JSON.parse(readFileSync(join(directory, file), "utf-8")));
    } catch {
      // Skip corrupt JSON files
    }
  }

  // Exclude deleted unless filter explicitly targets status
  const filterTargetsStatus = filter != null && "status" in filter;
  if (!filterTargetsStatus) {
    entities = entities.filter((e) => (e.status ?? "active") !== "deleted");
  }

  if (query) {
    entities = entities.filter((e) => matchText(e, query));
  }

  if (filter) {
    entities = entities.filter((e) => matchFilter(e, filter));
  }

  const descending = sort.startsWith("-");
  const sortField = sort.replace(/^-/, "");
  entities.sort((a, b) => {
    const ka = sortKey(a, sortField);
    const kb = sortKey(b, sortField);
    const cmp = ka < kb ? -1 : ka > kb ? 1 : 0;
    return descending ? -cmp : cmp;
  });

  return entities.slice(0, limit);
}
