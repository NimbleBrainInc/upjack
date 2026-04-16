/**
 * Activity entity definition and helpers for upjack apps.
 *
 * Activities are entities that record events against other entities. They
 * use the existing CRUD, search, and relationship infrastructure so they
 * get indexing, querying, and MCP tools for free.
 *
 * Opt-in via "activities": true in the manifest's upjack extension.
 */

import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { EntityDefinition } from "./entity.js";
import { loadSchema } from "./schema.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCHEMA_PATH = join(__dirname, "schemas", "activity.schema.json");

export const ACTIVITY_ENTITY_DEF: EntityDefinition = {
  name: "activity",
  plural: "activities",
  prefix: "act",
  schema: SCHEMA_PATH,
};

/** Load the built-in activity schema (with base-entity $ref inlined). */
export function getActivitySchema(): Record<string, unknown> {
  return loadSchema(SCHEMA_PATH);
}
