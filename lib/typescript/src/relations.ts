/**
 * Reverse relationship index for upjack entities.
 *
 * Maintains a write-time index that maps target entity IDs to the source
 * entities that reference them. The index file lives at
 * {root}/{namespace}/data/_index/relations.json and is updated
 * atomically (temp file + rename) on every CRUD operation that
 * touches relationships.
 */

import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  renameSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { join } from "node:path";
import { indexDir, indexPath } from "./paths.js";

export interface RelationEntry {
  source: string;
  rel: string;
}

export interface RelationIndex {
  reverse: Record<string, RelationEntry[]>;
}

export function loadIndex(root: string, namespace: string): RelationIndex {
  const path = indexPath(root, namespace);
  if (!existsSync(path)) {
    return { reverse: {} };
  }
  try {
    return JSON.parse(readFileSync(path, "utf-8"));
  } catch {
    return { reverse: {} };
  }
}

export function saveIndex(root: string, namespace: string, index: RelationIndex): void {
  const path = indexPath(root, namespace);
  const dir = indexDir(root, namespace);
  mkdirSync(dir, { recursive: true });

  const tmpPath = `${path}.tmp`;
  try {
    writeFileSync(tmpPath, `${JSON.stringify(index, null, 2)}\n`);
    renameSync(tmpPath, path);
  } catch (err) {
    try {
      if (existsSync(tmpPath)) unlinkSync(tmpPath);
    } catch {
      // ignore cleanup errors
    }
    throw err;
  }
}

export function updateIndex(
  root: string,
  namespace: string,
  entityId: string,
  oldRels: Array<{ rel?: string; target?: string }>,
  newRels: Array<{ rel?: string; target?: string }>,
): void {
  const index = loadIndex(root, namespace);
  const reverse = index.reverse;

  // Build sets of "target|rel" strings for diffing
  const toKey = (r: { target?: string; rel?: string }) =>
    r.target && r.rel ? `${r.target}|${r.rel}` : null;

  const oldSet = new Set<string>();
  const oldMap = new Map<string, { target: string; rel: string }>();
  for (const r of oldRels) {
    const key = toKey(r);
    if (key && r.target && r.rel) {
      oldSet.add(key);
      oldMap.set(key, { target: r.target, rel: r.rel });
    }
  }

  const newSet = new Set<string>();
  const newMap = new Map<string, { target: string; rel: string }>();
  for (const r of newRels) {
    const key = toKey(r);
    if (key && r.target && r.rel) {
      newSet.add(key);
      newMap.set(key, { target: r.target, rel: r.rel });
    }
  }

  // Remove stale entries
  for (const key of oldSet) {
    if (newSet.has(key)) continue;
    const pair = oldMap.get(key);
    if (!pair) continue;
    const { target, rel } = pair;
    const entries = reverse[target];
    if (entries) {
      reverse[target] = entries.filter((e) => !(e.source === entityId && e.rel === rel));
      if (reverse[target].length === 0) {
        delete reverse[target];
      }
    }
  }

  // Add new entries
  for (const key of newSet) {
    if (oldSet.has(key)) continue;
    const pair = newMap.get(key);
    if (!pair) continue;
    const { target, rel } = pair;
    if (!reverse[target]) {
      reverse[target] = [];
    }
    const entry: RelationEntry = { source: entityId, rel };
    const exists = reverse[target].some((e) => e.source === entry.source && e.rel === entry.rel);
    if (!exists) {
      reverse[target].push(entry);
    }
  }

  saveIndex(root, namespace, index);
}

export function removeFromIndex(
  root: string,
  namespace: string,
  entityId: string,
  rels: Array<{ rel?: string; target?: string }>,
): void {
  if (!rels || rels.length === 0) return;

  const index = loadIndex(root, namespace);
  const reverse = index.reverse;

  for (const r of rels) {
    const target = r.target;
    if (!target) continue;
    const entries = reverse[target];
    if (entries) {
      reverse[target] = entries.filter((e) => e.source !== entityId);
      if (reverse[target].length === 0) {
        delete reverse[target];
      }
    }
  }

  saveIndex(root, namespace, index);
}

export function rebuildIndex(
  root: string,
  namespace: string,
  entityDefs: Array<{ plural?: string; name?: string }>,
): RelationIndex {
  const reverse: Record<string, RelationEntry[]> = {};

  for (const edef of entityDefs) {
    const plural = edef.plural ?? `${edef.name ?? ""}s`;
    const edir = join(root, namespace, "data", plural);
    if (!existsSync(edir)) continue;

    for (const file of readdirSync(edir)) {
      if (!file.endsWith(".json")) continue;
      try {
        const entity = JSON.parse(readFileSync(join(edir, file), "utf-8"));
        const entityId = entity.id ?? "";
        for (const rel of entity.relationships ?? []) {
          const target = rel.target;
          const relName = rel.rel;
          if (!target || !relName) continue;
          if (!reverse[target]) {
            reverse[target] = [];
          }
          const entry: RelationEntry = { source: entityId, rel: relName };
          const exists = reverse[target].some(
            (e) => e.source === entry.source && e.rel === entry.rel,
          );
          if (!exists) {
            reverse[target].push(entry);
          }
        }
      } catch {
        // Skip corrupt files
      }
    }
  }

  const index: RelationIndex = { reverse };
  saveIndex(root, namespace, index);
  return index;
}

export function queryReverse(
  root: string,
  namespace: string,
  targetId: string,
  rel?: string,
  entityDefs?: Array<{ plural?: string; name?: string }>,
): RelationEntry[] {
  const path = indexPath(root, namespace);
  if (!existsSync(path) && entityDefs) {
    rebuildIndex(root, namespace, entityDefs);
  }

  const index = loadIndex(root, namespace);
  let entries = index.reverse[targetId] ?? [];

  if (rel !== undefined) {
    entries = entries.filter((e) => e.rel === rel);
  }

  return entries;
}
