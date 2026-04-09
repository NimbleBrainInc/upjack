import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { dirname, join } from "node:path";
import { generateId } from "./ids.js";
import { entityDir, entityPath } from "./paths.js";
import { hydrateDefaults, validateEntity } from "./schema.js";

export interface Relationship {
  rel: string;
  target: string;
  label?: string;
  [key: string]: string | undefined;
}

export type RelationshipsChangedCallback = (
  entityId: string,
  oldRels: Relationship[],
  newRels: Relationship[],
) => void;

/** Base fields present on every entity record. */
export interface EntityRecord {
  id: string;
  type: string;
  version: number;
  created_at: string;
  updated_at: string;
  created_by: string;
  status: string;
  tags: string[];
  source?: Record<string, string>;
  relationships: Relationship[];
  [key: string]: unknown;
}

/** Entity definition from the manifest. */
export interface EntityDefinition {
  name: string;
  plural?: string;
  schema: string;
  prefix: string;
  index?: boolean;
}

function nowIso(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

/**
 * Create a new entity, validate it, and write to disk.
 */
export function createEntity(
  root: string,
  namespace: string,
  entityType: string,
  plural: string,
  prefix: string,
  data: Record<string, unknown>,
  schema?: Record<string, unknown>,
  schemaVersion = 1,
  createdBy = "agent",
  onRelationshipsChanged?: RelationshipsChangedCallback,
): EntityRecord {
  const now = nowIso();
  const entityId = generateId(prefix);
  const { tags: rawTags, relationships: rawRelationships, source: rawSource, ...appData } = data;
  const tags = (rawTags as string[]) ?? [];
  const relationships = (rawRelationships as EntityRecord["relationships"]) ?? [];
  const source = rawSource as Record<string, string> | undefined;

  const record: EntityRecord = {
    id: entityId,
    type: entityType,
    version: schemaVersion,
    created_at: now,
    updated_at: now,
    created_by: createdBy,
    status: "active",
    tags,
    relationships,
    ...appData,
  };

  if (source !== undefined) {
    record.source = source;
  }

  if (schema) {
    validateEntity(record, schema);
  }

  const path = entityPath(root, namespace, plural, entityId);
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, `${JSON.stringify(record, null, 2)}\n`);

  if (onRelationshipsChanged && record.relationships.length > 0) {
    onRelationshipsChanged(entityId, [], record.relationships);
  }

  return record;
}

/**
 * Update an existing entity.
 */
export function updateEntity(
  root: string,
  namespace: string,
  plural: string,
  entityId: string,
  data: Record<string, unknown>,
  schema?: Record<string, unknown>,
  merge = true,
  onRelationshipsChanged?: RelationshipsChangedCallback,
): EntityRecord {
  const path = entityPath(root, namespace, plural, entityId);
  if (!existsSync(path)) {
    throw new Error(`Entity not found: ${entityId}`);
  }

  let existing = JSON.parse(readFileSync(path, "utf-8")) as EntityRecord;
  const oldRelationships = JSON.stringify(existing.relationships ?? []);

  // Hydrate defaults before merge so old entities missing new fields
  // get filled in — prevents validation failures on schema evolution.
  if (schema) {
    existing = hydrateDefaults(existing, schema) as EntityRecord;
  }

  // Strip immutable fields
  const immutable = new Set(["id", "type", "version", "created_at", "created_by"]);
  const safeData: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(data)) {
    if (!immutable.has(k)) {
      safeData[k] = v;
    }
  }

  if (merge) {
    existing = { ...existing, ...safeData };
  } else {
    const preserved: Record<string, unknown> = {};
    for (const key of immutable) {
      if (key in existing) {
        preserved[key] = existing[key as keyof EntityRecord];
      }
    }
    existing = { ...preserved, ...safeData } as EntityRecord;
  }

  existing.updated_at = nowIso();

  if (schema) {
    validateEntity(existing, schema);
  }

  writeFileSync(path, `${JSON.stringify(existing, null, 2)}\n`);

  if (onRelationshipsChanged) {
    const newRelationships = JSON.stringify(existing.relationships ?? []);
    if (oldRelationships !== newRelationships) {
      onRelationshipsChanged(entityId, JSON.parse(oldRelationships), existing.relationships ?? []);
    }
  }

  return existing;
}

/**
 * Read a single entity from disk.
 */
export function getEntity(
  root: string,
  namespace: string,
  plural: string,
  entityId: string,
  schema?: Record<string, unknown>,
): EntityRecord {
  const path = entityPath(root, namespace, plural, entityId);
  if (!existsSync(path)) {
    throw new Error(`Entity not found: ${entityId}`);
  }
  const entity = JSON.parse(readFileSync(path, "utf-8")) as EntityRecord;
  if (schema) {
    return hydrateDefaults(entity, schema) as EntityRecord;
  }
  return entity;
}

/**
 * List entities of a given type.
 */
export function listEntities(
  root: string,
  namespace: string,
  plural: string,
  status = "active",
  limit = 50,
  schema?: Record<string, unknown>,
): EntityRecord[] {
  const directory = entityDir(root, namespace, plural);
  if (!existsSync(directory)) {
    return [];
  }

  const results: EntityRecord[] = [];
  for (const file of readdirSync(directory)) {
    if (!file.endsWith(".json")) continue;
    try {
      let entity = JSON.parse(readFileSync(join(directory, file), "utf-8")) as EntityRecord;
      if ((entity.status ?? "active") === status) {
        if (schema) {
          entity = hydrateDefaults(entity, schema) as EntityRecord;
        }
        results.push(entity);
      }
    } catch {
      // Skip corrupt JSON files
    }
  }

  results.sort((a, b) => (b.updated_at ?? "").localeCompare(a.updated_at ?? ""));
  return results.slice(0, limit);
}

/**
 * Delete an entity (soft delete by default).
 */
export function deleteEntity(
  root: string,
  namespace: string,
  plural: string,
  entityId: string,
  hard = false,
  onRelationshipsChanged?: RelationshipsChangedCallback,
): EntityRecord {
  const path = entityPath(root, namespace, plural, entityId);
  if (!existsSync(path)) {
    throw new Error(`Entity not found: ${entityId}`);
  }

  const entity = JSON.parse(readFileSync(path, "utf-8")) as EntityRecord;

  if (hard) {
    unlinkSync(path);
    if (onRelationshipsChanged && entity.relationships?.length > 0) {
      onRelationshipsChanged(entityId, entity.relationships, []);
    }
  } else {
    entity.status = "deleted";
    entity.updated_at = nowIso();
    writeFileSync(path, `${JSON.stringify(entity, null, 2)}\n`);
  }

  return entity;
}
