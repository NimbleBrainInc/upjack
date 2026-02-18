"""UpjackApp — high-level interface for upjack apps."""

import json
from pathlib import Path
from typing import Any

from upjack.entity import create_entity, delete_entity, get_entity, list_entities, update_entity
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
        root: str | Path = ".",
        schemas: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.namespace = namespace
        self.root = Path(root)
        self._entities = {e["name"]: e for e in entities}
        self._schemas = schemas or {}

    @classmethod
    def from_manifest(cls, manifest_path: str | Path, root: str | Path = ".") -> "UpjackApp":
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

        schemas: dict[str, dict[str, Any]] = {}
        manifest_dir = manifest_path.parent
        for entity_def in entities:
            schema_path = manifest_dir / entity_def["schema"]
            if schema_path.exists():
                schemas[entity_def["name"]] = load_schema(schema_path)

        return cls(
            namespace=namespace,
            entities=entities,
            root=root,
            schemas=schemas,
        )

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
        )

    def get_entity(self, entity_type: str, entity_id: str) -> dict[str, Any]:
        """Get a single entity by ID."""
        entity_def = self._get_entity_def(entity_type)
        return get_entity(
            root=self.root,
            namespace=self.namespace,
            plural=self._get_plural(entity_def),
            entity_id=entity_id,
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
        )
