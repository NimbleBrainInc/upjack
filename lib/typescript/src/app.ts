import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { ACTIVITY_ENTITY_DEF, getActivitySchema } from "./activity.js";
import {
  type EntityDefinition,
  type EntityRecord,
  createEntity,
  deleteEntity,
  getEntity,
  listEntities,
  updateEntity,
} from "./entity.js";
import { resolveRoot } from "./paths.js";
import { queryReverse, removeFromIndex, updateIndex } from "./relations.js";
import { loadSchema } from "./schema.js";
import { searchEntities as _searchEntities } from "./search.js";

/** The upjack extension block from a MCPB manifest's _meta. */
export interface UpjackManifestExtension {
  upjack_version: string;
  namespace: string;
  entities: EntityDefinition[];
  display?: { name?: string; icon?: string; category?: string };
  skills?: Array<{ source: string; path: string; name?: string; version?: string }>;
  context?: string;
  seed?: { data?: string; run_on_install?: boolean };
  activities?: boolean;
  utility_tools?: string[];
  [key: string]: unknown;
}

export class UpjackApp {
  readonly namespace: string;
  readonly root: string;
  /** @internal */
  readonly _schemas: Record<string, Record<string, unknown>>;
  private readonly _entities: Record<string, EntityDefinition>;
  private readonly _prefixMap: Record<string, string>;
  private readonly _manifestDir?: string;

  constructor(
    namespace: string,
    entities: EntityDefinition[],
    root?: string,
    schemas?: Record<string, Record<string, unknown>>,
    manifestDir?: string,
  ) {
    this.namespace = namespace;
    this.root = resolveRoot(root);
    this._entities = Object.fromEntries(entities.map((e) => [e.name, e]));
    this._schemas = schemas ?? {};
    this._prefixMap = Object.fromEntries(entities.map((e) => [e.prefix, e.name]));
    this._manifestDir = manifestDir;
  }

  /**
   * Load an UpjackApp from a MCPB manifest.json.
   */
  static fromManifest(manifestPath: string, root?: string): UpjackApp {
    const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
    const upjack = manifest?._meta?.["ai.nimblebrain/upjack"] as
      | UpjackManifestExtension
      | undefined;

    if (!upjack) {
      throw new Error(
        'Manifest missing upjack extension. Expected _meta["ai.nimblebrain/upjack"]. ' +
          "See https://github.com/NimbleBrainInc/upjack#2-create-a-manifest",
      );
    }
    if (!upjack.namespace) {
      throw new Error(
        "Upjack extension missing required field 'namespace' in " +
          '_meta["ai.nimblebrain/upjack"]',
      );
    }
    if (!upjack.entities) {
      throw new Error(
        "Upjack extension missing required field 'entities' in " + '_meta["ai.nimblebrain/upjack"]',
      );
    }

    let entities = upjack.entities;
    const manifestDir = dirname(manifestPath);

    // Opt-in activity tracking
    const activitiesEnabled = Boolean(upjack.activities);
    if (activitiesEnabled) {
      const userNames = new Set(entities.map((e) => e.name));
      if (userNames.has("activity")) {
        throw new Error(
          "Cannot enable built-in activities: an entity named 'activity' " +
            "is already defined in the manifest",
        );
      }
      entities = [...entities, ACTIVITY_ENTITY_DEF];
    }

    const schemas: Record<string, Record<string, unknown>> = {};
    for (const entityDef of entities) {
      const schemaPath = join(manifestDir, entityDef.schema);
      try {
        schemas[entityDef.name] = loadSchema(schemaPath);
      } catch {
        // Schema file doesn't exist — skip
      }
    }

    // Load the built-in activity schema from the package
    if (activitiesEnabled) {
      schemas.activity = getActivitySchema();
    }

    return new UpjackApp(upjack.namespace, entities, root, schemas, manifestDir);
  }

  private _getEntityDef(entityType: string): EntityDefinition {
    const def = this._entities[entityType];
    if (!def) {
      throw new Error(
        `Unknown entity type '${entityType}'. Known types: ${Object.keys(this._entities).join(", ")}`,
      );
    }
    return def;
  }

  private _getPlural(entityDef: EntityDefinition): string {
    return entityDef.plural ?? `${entityDef.name}s`;
  }

  // ------------------------------------------------------------------
  // Relationship index callbacks
  // ------------------------------------------------------------------

  /** @internal */
  _onRelationshipsChanged(
    entityId: string,
    oldRels: Array<Record<string, string>>,
    newRels: Array<Record<string, string>>,
  ): void {
    updateIndex(this.root, this.namespace, entityId, oldRels, newRels);
  }

  /** @internal */
  _onRelationshipsRemoved(
    entityId: string,
    oldRels: Array<Record<string, string>>,
    _newRels: Array<Record<string, string>>,
  ): void {
    removeFromIndex(this.root, this.namespace, entityId, oldRels);
  }

  // ------------------------------------------------------------------
  // Prefix resolution
  // ------------------------------------------------------------------

  /** @internal */
  _resolveType(entityId: string): string {
    const prefix = entityId.split("_", 1)[0];
    if (!(prefix in this._prefixMap)) {
      throw new Error(
        `Unknown prefix '${prefix}' in entity ID '${entityId}'. Known: ${Object.keys(this._prefixMap).join(", ")}`,
      );
    }
    return this._prefixMap[prefix];
  }

  /** @internal */
  _entityDefsList(): EntityDefinition[] {
    return Object.values(this._entities);
  }

  // ------------------------------------------------------------------
  // Schema reloading
  // ------------------------------------------------------------------

  reloadSchema(entityType: string): void {
    if (!this._manifestDir) {
      throw new Error("Cannot reload schema: manifestDir is not set");
    }
    const entityDef = this._getEntityDef(entityType);
    const schemaPath = join(this._manifestDir, entityDef.schema);
    this._schemas[entityType] = loadSchema(schemaPath);
  }

  // ------------------------------------------------------------------
  // CRUD operations
  // ------------------------------------------------------------------

  createEntity(
    entityType: string,
    data: Record<string, unknown>,
    createdBy = "agent",
  ): EntityRecord {
    const entityDef = this._getEntityDef(entityType);
    return createEntity(
      this.root,
      this.namespace,
      entityType,
      this._getPlural(entityDef),
      entityDef.prefix,
      data,
      this._schemas[entityType],
      1,
      createdBy,
      this._onRelationshipsChanged.bind(this),
    );
  }

  updateEntity(
    entityType: string,
    entityId: string,
    data: Record<string, unknown>,
    merge = true,
  ): EntityRecord {
    const entityDef = this._getEntityDef(entityType);
    return updateEntity(
      this.root,
      this.namespace,
      this._getPlural(entityDef),
      entityId,
      data,
      this._schemas[entityType],
      merge,
      this._onRelationshipsChanged.bind(this),
    );
  }

  getEntity(entityType: string, entityId: string): EntityRecord {
    const entityDef = this._getEntityDef(entityType);
    return getEntity(
      this.root,
      this.namespace,
      this._getPlural(entityDef),
      entityId,
      this._schemas[entityType],
    );
  }

  listEntities(entityType: string, status = "active", limit = 50): EntityRecord[] {
    const entityDef = this._getEntityDef(entityType);
    return listEntities(
      this.root,
      this.namespace,
      this._getPlural(entityDef),
      status,
      limit,
      this._schemas[entityType],
    );
  }

  deleteEntity(entityType: string, entityId: string, hard = false): EntityRecord {
    const entityDef = this._getEntityDef(entityType);
    return deleteEntity(
      this.root,
      this.namespace,
      this._getPlural(entityDef),
      entityId,
      hard,
      this._onRelationshipsRemoved.bind(this),
    );
  }

  searchEntities(
    entityType: string,
    options: {
      query?: string;
      filter?: Record<string, unknown>;
      sort?: string;
      limit?: number;
    } = {},
  ): EntityRecord[] {
    const entityDef = this._getEntityDef(entityType);
    return _searchEntities(
      this.root,
      this.namespace,
      this._getPlural(entityDef),
      options.query,
      options.filter,
      options.sort ?? "-updated_at",
      options.limit ?? 20,
    );
  }

  // ------------------------------------------------------------------
  // Graph traversal
  // ------------------------------------------------------------------

  queryByRelationship(
    entityType: string,
    rel: string,
    targetId: string,
    filter?: Record<string, unknown>,
    limit = 50,
  ): EntityRecord[] {
    const entityDef = this._getEntityDef(entityType);
    const prefix = entityDef.prefix;

    const entries = queryReverse(this.root, this.namespace, targetId, rel, this._entityDefsList());

    const matchingIds = entries
      .filter((e) => e.source.startsWith(`${prefix}_`))
      .map((e) => e.source);

    const results: EntityRecord[] = [];
    for (const eid of matchingIds) {
      let entity: EntityRecord;
      try {
        entity = this.getEntity(entityType, eid);
      } catch {
        continue;
      }
      if ((entity.status ?? "active") !== "active") continue;
      if (filter && !UpjackApp._matchesFilter(entity, filter)) continue;
      results.push(entity);
      if (results.length >= limit) break;
    }

    return results;
  }

  getRelated(
    entityId: string,
    rel?: string,
    direction: "forward" | "reverse" = "forward",
  ): EntityRecord[] {
    if (direction === "forward") {
      return this._getRelatedForward(entityId, rel);
    }
    if (direction === "reverse") {
      return this._getRelatedReverse(entityId, rel);
    }
    throw new Error(`direction must be 'forward' or 'reverse', got '${direction}'`);
  }

  private _getRelatedForward(entityId: string, rel?: string): EntityRecord[] {
    const sourceType = this._resolveType(entityId);
    const entity = this.getEntity(sourceType, entityId);
    let relationships = entity.relationships ?? [];
    if (rel !== undefined) {
      relationships = relationships.filter((r) => r.rel === rel);
    }

    const results: EntityRecord[] = [];
    for (const r of relationships) {
      if (!r.target) continue;
      try {
        const targetType = this._resolveType(r.target);
        results.push(this.getEntity(targetType, r.target));
      } catch {}
    }
    return results;
  }

  private _getRelatedReverse(entityId: string, rel?: string): EntityRecord[] {
    const entries = queryReverse(this.root, this.namespace, entityId, rel, this._entityDefsList());

    const results: EntityRecord[] = [];
    for (const entry of entries) {
      try {
        const sourceType = this._resolveType(entry.source);
        results.push(this.getEntity(sourceType, entry.source));
      } catch {}
    }
    return results;
  }

  getComposite(entityType: string, entityId: string, depth = 1): Record<string, unknown> {
    const entity = this.getEntity(entityType, entityId);
    const related: Record<string, EntityRecord[]> = {};

    if (depth >= 1) {
      // Forward relationships
      for (const r of entity.relationships ?? []) {
        if (!r.target || !r.rel) continue;
        try {
          const targetType = this._resolveType(r.target);
          const target = this.getEntity(targetType, r.target);
          if (!related[r.rel]) related[r.rel] = [];
          related[r.rel].push(target);
        } catch {}
      }

      // Reverse relationships
      const entries = queryReverse(
        this.root,
        this.namespace,
        entityId,
        undefined,
        this._entityDefsList(),
      );
      for (const entry of entries) {
        const relName = `~${entry.rel}`;
        try {
          const sourceType = this._resolveType(entry.source);
          const source = this.getEntity(sourceType, entry.source);
          if (!related[relName]) related[relName] = [];
          related[relName].push(source);
        } catch {}
      }
    }

    return { ...entity, _related: related };
  }

  private static _matchesFilter(entity: EntityRecord, filter: Record<string, unknown>): boolean {
    for (const [key, value] of Object.entries(filter)) {
      if (typeof value === "object" && value !== null && !Array.isArray(value)) {
        throw new Error(
          "Operator filters are not supported in queryByRelationship. Use simple equality filters.",
        );
      }
      if (entity[key] !== value) return false;
    }
    return true;
  }

  // ------------------------------------------------------------------
  // Activity tracking
  // ------------------------------------------------------------------

  logActivity(subjectId: string, action: string, detail?: Record<string, unknown>): EntityRecord {
    this._getEntityDef("activity");
    const data: Record<string, unknown> = {
      action,
      detail: detail ?? {},
      relationships: [{ rel: "subject", target: subjectId }],
    };
    return this.createEntity("activity", data, "system");
  }

  getActivities(subjectId: string, action?: string, limit = 50): EntityRecord[] {
    this._getEntityDef("activity");
    const entityDef = this._entities.activity;
    const prefix = entityDef.prefix;

    const entries = queryReverse(
      this.root,
      this.namespace,
      subjectId,
      "subject",
      this._entityDefsList(),
    );

    const activityIds = entries
      .filter((e) => e.source.startsWith(`${prefix}_`))
      .map((e) => e.source);

    const results: EntityRecord[] = [];
    for (const eid of activityIds) {
      try {
        const entity = this.getEntity("activity", eid);
        if ((entity.status ?? "active") !== "active") continue;
        if (action !== undefined && entity.action !== action) continue;
        results.push(entity);
      } catch {}
    }

    results.sort((a, b) => (b.updated_at ?? "").localeCompare(a.updated_at ?? ""));
    return results.slice(0, limit);
  }
}
