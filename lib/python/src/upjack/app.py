"""UpjackApp — high-level interface for upjack apps."""

import json
from pathlib import Path
from typing import Any

from upjack.activity import ACTIVITY_ENTITY_DEF, get_activity_schema
from upjack.entity import create_entity, delete_entity, get_entity, list_entities, update_entity
from upjack.relations import query_reverse, remove_from_index, update_index
from upjack.schema import load_schema
from upjack.search import search_entities as _search_entities


class UpjackApp:
    """High-level interface for a NimbleBrain Upjack app.

    Provides entity CRUD operations with automatic schema resolution,
    ID generation, and path management. Works standalone or as the
    foundation for an MCP server.
    """

    def __init__(
        self,
        namespace: str,
        entities: list[dict[str, Any]],
        root: str | Path | None = None,
        schemas: dict[str, dict[str, Any]] | None = None,
        manifest_dir: Path | None = None,
    ) -> None:
        from upjack.paths import resolve_root

        self.namespace = namespace
        self.root = resolve_root(root)
        self._entities = {e["name"]: e for e in entities}
        self._schemas = schemas or {}
        self._manifest_dir = manifest_dir
        self._prefix_map = {e["prefix"]: e["name"] for e in entities}

    @classmethod
    def from_manifest(
        cls, manifest_path: str | Path, root: str | Path | None = None
    ) -> "UpjackApp":
        """Load a UpjackApp from a MCPB manifest.json.

        Reads the manifest, extracts the upjack extension from
        _meta["ai.nimblebrain/upjack"], and loads entity schemas.

        Args:
            manifest_path: Path to manifest.json.
            root: Workspace root directory.

        Returns:
            Configured UpjackApp instance.
        """
        manifest_path = Path(manifest_path)
        manifest = json.loads(manifest_path.read_text())

        upjack = manifest.get("_meta", {}).get("ai.nimblebrain/upjack")
        if upjack is None:
            raise ValueError(
                'Manifest missing upjack extension. Expected _meta["ai.nimblebrain/upjack"]. '
                "See https://github.com/NimbleBrainInc/upjack#4-create-a-manifest"
            )
        for key in ("namespace", "entities"):
            if key not in upjack:
                raise ValueError(
                    f"Upjack extension missing required field '{key}' in "
                    '_meta["ai.nimblebrain/upjack"]'
                )

        namespace = upjack["namespace"]
        entities = upjack["entities"]

        # Opt-in activity tracking: auto-register the built-in activity entity
        activities_enabled = bool(upjack.get("activities", False))
        if activities_enabled:
            user_names = {e["name"] for e in entities}
            if "activity" in user_names:
                raise ValueError(
                    "Cannot enable built-in activities: an entity named 'activity' "
                    "is already defined in the manifest"
                )
            entities = [*entities, ACTIVITY_ENTITY_DEF]

        schemas: dict[str, dict[str, Any]] = {}
        manifest_dir = manifest_path.parent
        for entity_def in entities:
            schema_path = manifest_dir / entity_def["schema"]
            if schema_path.exists():
                schemas[entity_def["name"]] = load_schema(schema_path)

        # Load the built-in activity schema from the package
        if activities_enabled:
            schemas["activity"] = get_activity_schema()

        return cls(
            namespace=namespace,
            entities=entities,
            root=root,
            schemas=schemas,
            manifest_dir=manifest_dir,
        )

    def reload_schema(self, entity_type: str) -> None:
        """Reload the schema for an entity type from disk.

        Raises:
            ValueError: If entity type is unknown or manifest_dir is not set.
        """
        if self._manifest_dir is None:
            raise ValueError("Cannot reload schema: manifest_dir is not set")
        entity_def = self._get_entity_def(entity_type)
        schema_path = self._manifest_dir / entity_def["schema"]
        self._schemas[entity_type] = load_schema(schema_path)

    def _on_relationships_changed(self, entity_id: str, old_rels: list, new_rels: list) -> None:
        """Callback that updates the reverse relationship index."""
        update_index(self.root, self.namespace, entity_id, old_rels, new_rels)

    def _on_relationships_removed(self, entity_id: str, old_rels: list, _new_rels: list) -> None:
        """Callback for hard delete — removes entries from index."""
        remove_from_index(self.root, self.namespace, entity_id, old_rels)

    def _get_entity_def(self, entity_type: str) -> dict[str, Any]:
        if entity_type not in self._entities:
            raise ValueError(
                f"Unknown entity type '{entity_type}'. Known types: {list(self._entities.keys())}"
            )
        return self._entities[entity_type]

    def _get_plural(self, entity_def: dict[str, Any]) -> str:
        return entity_def.get("plural", entity_def["name"] + "s")

    def create_entity(
        self,
        entity_type: str,
        data: dict[str, Any],
        created_by: str = "agent",
    ) -> dict[str, Any]:
        """Create a new entity of the given type."""
        entity_def = self._get_entity_def(entity_type)
        return create_entity(
            root=self.root,
            namespace=self.namespace,
            entity_type=entity_type,
            plural=self._get_plural(entity_def),
            prefix=entity_def["prefix"],
            data=data,
            schema=self._schemas.get(entity_type),
            created_by=created_by,
            on_relationships_changed=self._on_relationships_changed,
        )

    def update_entity(
        self,
        entity_type: str,
        entity_id: str,
        data: dict[str, Any],
        merge: bool = True,
    ) -> dict[str, Any]:
        """Update an existing entity."""
        entity_def = self._get_entity_def(entity_type)
        return update_entity(
            root=self.root,
            namespace=self.namespace,
            plural=self._get_plural(entity_def),
            entity_id=entity_id,
            data=data,
            schema=self._schemas.get(entity_type),
            merge=merge,
            on_relationships_changed=self._on_relationships_changed,
        )

    def get_entity(self, entity_type: str, entity_id: str) -> dict[str, Any]:
        """Get a single entity by ID."""
        entity_def = self._get_entity_def(entity_type)
        return get_entity(
            root=self.root,
            namespace=self.namespace,
            plural=self._get_plural(entity_def),
            entity_id=entity_id,
            schema=self._schemas.get(entity_type),
        )

    def list_entities(
        self,
        entity_type: str,
        status: str = "active",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List entities of the given type."""
        entity_def = self._get_entity_def(entity_type)
        return list_entities(
            root=self.root,
            namespace=self.namespace,
            plural=self._get_plural(entity_def),
            status=status,
            limit=limit,
            schema=self._schemas.get(entity_type),
        )

    def delete_entity(
        self,
        entity_type: str,
        entity_id: str,
        hard: bool = False,
    ) -> dict[str, Any]:
        """Delete an entity (soft delete by default)."""
        entity_def = self._get_entity_def(entity_type)
        return delete_entity(
            root=self.root,
            namespace=self.namespace,
            plural=self._get_plural(entity_def),
            entity_id=entity_id,
            hard=hard,
            on_relationships_changed=self._on_relationships_removed,
        )

    def search_entities(
        self,
        entity_type: str,
        query: str | None = None,
        filter: dict[str, Any] | None = None,
        sort: str = "-updated_at",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search entities with text query and structured filters."""
        entity_def = self._get_entity_def(entity_type)
        return _search_entities(
            root=self.root,
            namespace=self.namespace,
            plural=self._get_plural(entity_def),
            query=query,
            filter=filter,
            sort=sort,
            limit=limit,
            schema=self._schemas.get(entity_type),
        )

    # ------------------------------------------------------------------
    # Activity tracking
    # ------------------------------------------------------------------

    def log_activity(
        self,
        subject_id: str,
        action: str,
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Log an activity against an entity.

        Creates an activity entity with a ``subject`` relationship pointing
        at *subject_id*.  The activity is created with ``created_by="system"``
        to distinguish it from agent-created entities.

        Args:
            subject_id: The entity this activity is about.
            action: What happened (e.g., ``"email_sent"``).
            detail: Optional structured data about the activity.

        Returns:
            The created activity entity dict.

        Raises:
            ValueError: If the ``activity`` entity type is not registered
                (i.e., activities were not enabled in the manifest).
        """
        self._get_entity_def("activity")  # ensure activity type is registered
        data: dict[str, Any] = {
            "action": action,
            "detail": detail if detail is not None else {},
            "relationships": [{"rel": "subject", "target": subject_id}],
        }
        return self.create_entity("activity", data, created_by="system")

    def get_activities(
        self,
        subject_id: str,
        action: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return activities recorded against *subject_id*.

        Uses the reverse relationship index for efficient lookup rather
        than scanning all activity files.

        Args:
            subject_id: The entity to get activities for.
            action: Optional filter — only return activities with this action.
            limit: Maximum number of results (default 50).

        Returns:
            List of activity entity dicts, sorted most-recent first.
        """
        self._get_entity_def("activity")  # ensure activity type is registered
        entity_def = self._entities["activity"]
        plural = self._get_plural(entity_def)
        prefix = entity_def["prefix"]
        schema = self._schemas.get("activity")

        entries = query_reverse(
            self.root,
            self.namespace,
            subject_id,
            rel="subject",
            entity_defs=self._entity_defs_list(),
        )

        # Filter to activity entities only (by prefix)
        activity_ids = [e["source"] for e in entries if e["source"].startswith(prefix + "_")]

        results: list[dict[str, Any]] = []
        for eid in activity_ids:
            try:
                entity = get_entity(
                    root=self.root,
                    namespace=self.namespace,
                    plural=plural,
                    entity_id=eid,
                    schema=schema,
                )
            except FileNotFoundError:
                continue
            if entity.get("status", "active") != "active":
                continue
            if action is not None and entity.get("action") != action:
                continue
            results.append(entity)

        # Sort by most recent first
        results.sort(key=lambda e: e.get("updated_at", ""), reverse=True)
        return results[:limit]

    # ------------------------------------------------------------------
    # Prefix resolution
    # ------------------------------------------------------------------

    def _resolve_type(self, entity_id: str) -> str:
        """Resolve an entity ID to its type name via the prefix map.

        Raises:
            ValueError: If the prefix is not recognized.
        """
        prefix = entity_id.split("_", 1)[0]
        if prefix not in self._prefix_map:
            raise ValueError(
                f"Unknown prefix '{prefix}' in entity ID '{entity_id}'. "
                f"Known prefixes: {list(self._prefix_map.keys())}"
            )
        return self._prefix_map[prefix]

    def _entity_defs_list(self) -> list[dict[str, Any]]:
        """Return entity defs as a list (for rebuild_index)."""
        return list(self._entities.values())

    # ------------------------------------------------------------------
    # Graph traversal
    # ------------------------------------------------------------------

    def query_by_relationship(
        self,
        entity_type: str,
        rel: str,
        target_id: str,
        filter: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return entities of *entity_type* with relationship *rel* pointing to *target_id*.

        Uses the reverse index for O(1) lookup of candidate IDs, then loads
        and optionally filters.
        """
        entity_def = self._get_entity_def(entity_type)
        prefix = entity_def["prefix"]
        plural = self._get_plural(entity_def)
        schema = self._schemas.get(entity_type)

        entries = query_reverse(
            self.root,
            self.namespace,
            target_id,
            rel=rel,
            entity_defs=self._entity_defs_list(),
        )

        # Filter to entries whose source matches the requested entity type prefix
        matching_ids = [e["source"] for e in entries if e["source"].startswith(prefix + "_")]

        results: list[dict[str, Any]] = []
        for eid in matching_ids:
            try:
                entity = get_entity(
                    root=self.root,
                    namespace=self.namespace,
                    plural=plural,
                    entity_id=eid,
                    schema=schema,
                )
            except FileNotFoundError:
                continue
            if entity.get("status", "active") != "active":
                continue
            if filter:
                if not self._matches_filter(entity, filter):
                    continue
            results.append(entity)
            if len(results) >= limit:
                break

        return results

    def get_related(
        self,
        entity_id: str,
        rel: str | None = None,
        direction: str = "forward",
    ) -> list[dict[str, Any]]:
        """Follow relationship edges from an entity.

        Args:
            entity_id: The entity to start from.
            rel: Optional relationship type filter.
            direction: ``"forward"`` reads the entity's relationships array.
                ``"reverse"`` queries the index for entities pointing at this one.

        Returns:
            List of resolved entity dicts.
        """
        if direction == "forward":
            return self._get_related_forward(entity_id, rel)
        elif direction == "reverse":
            return self._get_related_reverse(entity_id, rel)
        else:
            raise ValueError(f"direction must be 'forward' or 'reverse', got '{direction}'")

    def _get_related_forward(self, entity_id: str, rel: str | None = None) -> list[dict[str, Any]]:
        """Resolve forward relationships (edges this entity has)."""
        source_type = self._resolve_type(entity_id)
        entity = self.get_entity(source_type, entity_id)
        relationships = entity.get("relationships", [])
        if rel is not None:
            relationships = [r for r in relationships if r.get("rel") == rel]

        results: list[dict[str, Any]] = []
        for r in relationships:
            target_id = r.get("target")
            if not target_id:
                continue
            try:
                target_type = self._resolve_type(target_id)
                target = self.get_entity(target_type, target_id)
                results.append(target)
            except (ValueError, FileNotFoundError):
                continue
        return results

    def _get_related_reverse(self, entity_id: str, rel: str | None = None) -> list[dict[str, Any]]:
        """Resolve reverse relationships (edges pointing at this entity)."""
        entries = query_reverse(
            self.root,
            self.namespace,
            entity_id,
            rel=rel,
            entity_defs=self._entity_defs_list(),
        )

        results: list[dict[str, Any]] = []
        for entry in entries:
            source_id = entry["source"]
            try:
                source_type = self._resolve_type(source_id)
                source = self.get_entity(source_type, source_id)
                results.append(source)
            except (ValueError, FileNotFoundError):
                continue
        return results

    def get_composite(
        self,
        entity_type: str,
        entity_id: str,
        depth: int = 1,
    ) -> dict[str, Any]:
        """Load an entity with all related entities in one call.

        Returns the entity dict with an added ``_related`` key containing:
        - Forward relationships keyed by rel name
        - Reverse relationships keyed by ``~rel`` name

        Args:
            entity_type: Entity type name.
            entity_id: Entity ID.
            depth: How many hops to follow (1 = direct only).

        Returns:
            Entity dict with ``_related`` key.
        """
        entity = self.get_entity(entity_type, entity_id)
        related: dict[str, list[dict[str, Any]]] = {}

        if depth >= 1:
            # Forward relationships
            for r in entity.get("relationships", []):
                target_id = r.get("target")
                rel_name = r.get("rel")
                if not target_id or not rel_name:
                    continue
                try:
                    target_type = self._resolve_type(target_id)
                    target = self.get_entity(target_type, target_id)
                    related.setdefault(rel_name, []).append(target)
                except (ValueError, FileNotFoundError):
                    continue

            # Reverse relationships
            entries = query_reverse(
                self.root,
                self.namespace,
                entity_id,
                entity_defs=self._entity_defs_list(),
            )
            for entry in entries:
                source_id = entry["source"]
                rel_name = f"~{entry['rel']}"
                try:
                    source_type = self._resolve_type(source_id)
                    source = self.get_entity(source_type, source_id)
                    related.setdefault(rel_name, []).append(source)
                except (ValueError, FileNotFoundError):
                    continue

        return {**entity, "_related": related}

    @staticmethod
    def _matches_filter(entity: dict[str, Any], filter: dict[str, Any]) -> bool:
        """Check if an entity matches a structured filter (simple equality only)."""
        for key, value in filter.items():
            if isinstance(value, dict):
                raise ValueError(
                    f"Operator filters (e.g., {value}) are not supported in "
                    f"query_by_relationship. Use simple equality filters."
                )
            if entity.get(key) != value:
                return False
        return True
