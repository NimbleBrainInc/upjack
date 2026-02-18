import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import {
  type EntityDefinition,
  type EntityRecord,
  createEntity,
  deleteEntity,
  getEntity,
  listEntities,
  updateEntity,
} from "./entity.js";
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
  [key: string]: unknown;
}

export class UpjackApp {
  readonly namespace: string;
  readonly root: string;
  /** @internal */
  readonly _schemas: Record<string, Record<string, unknown>>;
  private readonly _entities: Record<string, EntityDefinition>;

  constructor(
    namespace: string,
    entities: EntityDefinition[],
    root = ".",
    schemas?: Record<string, Record<string, unknown>>,
  ) {
    this.namespace = namespace;
    this.root = root;
    this._entities = Object.fromEntries(entities.map((e) => [e.name, e]));
    this._schemas = schemas ?? {};
  }

  /**
   * Load an UpjackApp from a MCPB manifest.json.
   */
  static fromManifest(manifestPath: string, root = "."): UpjackApp {
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

    const manifestDir = dirname(manifestPath);
    const schemas: Record<string, Record<string, unknown>> = {};
    for (const entityDef of upjack.entities) {
      const schemaPath = join(manifestDir, entityDef.schema);
      try {
        schemas[entityDef.name] = loadSchema(schemaPath);
      } catch {
        // Schema file doesn't exist — skip
      }
    }

    return new UpjackApp(upjack.namespace, upjack.entities, root, schemas);
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
    );
  }

  getEntity(entityType: string, entityId: string): EntityRecord {
    const entityDef = this._getEntityDef(entityType);
    return getEntity(this.root, this.namespace, this._getPlural(entityDef), entityId);
  }

  listEntities(entityType: string, status = "active", limit = 50): EntityRecord[] {
    const entityDef = this._getEntityDef(entityType);
    return listEntities(this.root, this.namespace, this._getPlural(entityDef), status, limit);
  }

  deleteEntity(entityType: string, entityId: string, hard = false): EntityRecord {
    const entityDef = this._getEntityDef(entityType);
    return deleteEntity(this.root, this.namespace, this._getPlural(entityDef), entityId, hard);
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
}
