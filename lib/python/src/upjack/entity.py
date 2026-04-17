"""Entity CRUD operations for upjack apps."""

import json
import logging
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from upjack.ids import generate_id, validate_id
from upjack.paths import entity_dir, entity_path
from upjack.schema import hydrate_defaults, validate_entity

logger = logging.getLogger(__name__)

try:
    import fcntl

    _HAS_FCNTL = True
except ImportError:  # pragma: no cover — Windows fallback
    _HAS_FCNTL = False
    logger.warning(
        "fcntl is unavailable on this platform; upjack entity updates will "
        "not be serialized across concurrent writers. On Unix this is "
        "handled by an fcntl.flock on a sidecar .lock file."
    )

# Hard ceiling on how long an entity update may wait for another
# holder to release. Typical lock hold is single-digit milliseconds
# (read → compute → write on a small JSON file). Anything approaching
# this bound indicates a stuck-but-alive writer, and failing loudly
# is better than wedging the whole tool server forever.
_LOCK_TIMEOUT_SECONDS = 30.0
_LOCK_POLL_INTERVAL = 0.02

# Thread-local tracking of which entity paths this thread already
# holds. Guards against deadlock if a caller ever re-enters update_entity
# on the same entity from within another lock — the nested call skips
# the acquire since we already own it.
_held_paths = threading.local()


class EntityLockTimeout(RuntimeError):
    """Raised when an entity lock cannot be acquired within the timeout."""


def _already_held(path: Path) -> bool:
    held: set[str] = getattr(_held_paths, "paths", set())
    return str(path) in held


def _mark_held(path: Path) -> None:
    held: set[str] = getattr(_held_paths, "paths", None) or set()
    held.add(str(path))
    _held_paths.paths = held


def _unmark_held(path: Path) -> None:
    held: set[str] = getattr(_held_paths, "paths", set())
    held.discard(str(path))


@contextmanager
def _entity_lock(path: Path, timeout: float = _LOCK_TIMEOUT_SECONDS) -> Iterator[None]:
    """Serialize read-modify-write operations on a single entity.

    Concurrent tool calls (e.g. an agent invoking ``update_deal`` and
    ``move_deal_stage`` on the same deal in parallel) would otherwise
    read the same pre-state, each compute a partial update, and write
    sequentially — silently clobbering one another's changes. The
    on-disk state usually ends up consistent (last writer wins) but the
    **intermediate tool responses lie**: each call returns the state it
    wrote, unaware of the other's overlap.

    Acquires an exclusive advisory flock on a sidecar ``.lock`` file
    next to the entity's JSON file. The lock file persists — cleaning
    it up would race the lock itself.

    Semantics:

    - Blocks up to ``timeout`` seconds; raises :class:`EntityLockTimeout`
      after that. A stuck-but-alive holder must not wedge the server
      indefinitely.
    - If the holder process dies (crash, SIGKILL, OOM), the OS releases
      the flock automatically — waiters unblock.
    - Re-entrant on the same thread: nested calls on the same entity
      pass through without re-acquiring, avoiding self-deadlock.
    - On Windows (no fcntl) this is a no-op; concurrent updates remain
      unsafe, but no worse than before this fix.
    """
    if not _HAS_FCNTL or _already_held(path):
        yield
        return

    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    deadline = time.monotonic() + timeout
    with open(lock_path, "w") as lock_f:
        while True:
            try:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise EntityLockTimeout(
                        f"Could not acquire entity lock for {path} within "
                        f"{timeout:.1f}s — another writer appears stuck."
                    ) from None
                time.sleep(_LOCK_POLL_INTERVAL)

        _mark_held(path)
        try:
            yield
        finally:
            _unmark_held(path)
            # flock is also released on FD close (the `with open` exit),
            # so this is belt-and-suspenders — harmless if the OS has
            # already dropped it.


@dataclass
class Entity:
    """Represents an upjack entity with base fields."""

    id: str
    type: str
    version: int
    created_at: str
    updated_at: str
    created_by: str = "agent"
    status: str = "active"
    tags: list[str] = field(default_factory=list)
    source: dict[str, str] | None = None
    relationships: list[dict[str, str]] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize entity to a flat dict (base fields + app data merged)."""
        result: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
            "status": self.status,
            "tags": self.tags,
            "relationships": self.relationships,
        }
        if self.source is not None:
            result["source"] = self.source
        result.update(self.data)
        return result

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Entity":
        """Deserialize entity from a flat dict."""
        base_keys = {
            "id",
            "type",
            "version",
            "created_at",
            "updated_at",
            "created_by",
            "status",
            "tags",
            "source",
            "relationships",
        }
        data = {k: v for k, v in raw.items() if k not in base_keys}
        return cls(
            id=raw["id"],
            type=raw["type"],
            version=raw["version"],
            created_at=raw["created_at"],
            updated_at=raw["updated_at"],
            created_by=raw.get("created_by", "agent"),
            status=raw.get("status", "active"),
            tags=raw.get("tags", []),
            source=raw.get("source"),
            relationships=raw.get("relationships", []),
            data=data,
        )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def create_entity(
    root: str | Path,
    namespace: str,
    entity_type: str,
    plural: str,
    prefix: str,
    data: dict[str, Any],
    schema: dict[str, Any] | None = None,
    schema_version: int = 1,
    created_by: str = "agent",
    on_relationships_changed: Callable[[str, list, list], None] | None = None,
) -> dict[str, Any]:
    """Create a new entity, validate it, and write to disk.

    Args:
        root: Workspace root directory.
        namespace: App namespace (e.g., 'apps/crm').
        entity_type: Entity type name (e.g., 'contact').
        plural: Plural form (e.g., 'contacts').
        prefix: ID prefix (e.g., 'ct').
        data: App-specific entity data.
        schema: Optional JSON Schema to validate against.
        schema_version: Schema version number.
        created_by: Who created this entity.

    Returns:
        The complete entity dict (base fields + app data).
    """
    now = _now_iso()
    data = dict(data)  # avoid mutating caller's dict

    # Resolve entity ID: use provided ID if valid for this prefix, otherwise generate
    provided_id = data.pop("id", None)
    if provided_id and validate_id(provided_id) and provided_id.startswith(f"{prefix}_"):
        entity_id = provided_id
    else:
        entity_id = generate_id(prefix)

    # Strip type — always set from entity_type parameter
    data.pop("type", None)

    # Reject duplicates
    path = entity_path(root, namespace, plural, entity_id)
    if path.exists():
        raise ValueError(f"Entity already exists: {entity_id}")

    record: dict[str, Any] = {
        "id": entity_id,
        "type": entity_type,
        "version": schema_version,
        "created_at": now,
        "updated_at": now,
        "created_by": created_by,
        "status": "active",
        "tags": data.pop("tags", []),
        "relationships": data.pop("relationships", []),
    }
    if "source" in data:
        record["source"] = data.pop("source")
    record.update(data)

    if schema is not None:
        validate_entity(record, schema)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n")

    if on_relationships_changed is not None and record.get("relationships"):
        on_relationships_changed(entity_id, [], record["relationships"])

    return record


def update_entity(
    root: str | Path,
    namespace: str,
    plural: str,
    entity_id: str,
    data: dict[str, Any],
    schema: dict[str, Any] | None = None,
    merge: bool = True,
    on_relationships_changed: Callable[[str, list, list], None] | None = None,
) -> dict[str, Any]:
    """Update an existing entity.

    Args:
        root: Workspace root directory.
        namespace: App namespace.
        plural: Plural form.
        entity_id: Entity ID to update.
        data: Fields to update.
        schema: Optional JSON Schema to validate against.
        merge: If True, merge with existing data. If False, replace.

    Returns:
        The updated entity dict.

    Raises:
        FileNotFoundError: If the entity doesn't exist.
    """
    path = entity_path(root, namespace, plural, entity_id)
    if not path.exists():
        raise FileNotFoundError(f"Entity not found: {entity_id}")

    # Hold the lock across read+compute+write so concurrent updates on
    # the same entity don't race. See _entity_lock() for full context.
    with _entity_lock(path):
        existing = json.loads(path.read_text())
        old_relationships = existing.get("relationships", [])

        # Hydrate defaults before merge so old entities missing new fields
        # get filled in — prevents validation failures on schema evolution.
        if schema is not None:
            existing = hydrate_defaults(existing, schema)

        # Strip immutable fields — these cannot be changed after creation
        immutable = {"id", "type", "version", "created_at", "created_by"}
        safe_data = {k: v for k, v in data.items() if k not in immutable}

        if merge:
            existing.update(safe_data)
        else:
            preserved_keys = {"id", "type", "version", "created_at", "created_by"}
            preserved = {k: existing[k] for k in preserved_keys if k in existing}
            existing = {**preserved, **safe_data}

        existing["updated_at"] = _now_iso()

        if schema is not None:
            validate_entity(existing, schema)

        path.write_text(json.dumps(existing, indent=2) + "\n")

    if on_relationships_changed is not None:
        new_relationships = existing.get("relationships", [])
        if old_relationships != new_relationships:
            on_relationships_changed(entity_id, old_relationships, new_relationships)

    return existing


def get_entity(
    root: str | Path,
    namespace: str,
    plural: str,
    entity_id: str,
    schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Read a single entity from disk.

    If a schema is provided, missing fields are filled with schema
    defaults before returning (hydrate-on-read).

    Args:
        root: Workspace root directory.
        namespace: App namespace.
        plural: Plural form.
        entity_id: Entity ID to read.
        schema: Optional JSON Schema — used to hydrate defaults on read.

    Returns:
        The entity dict (hydrated if schema provided).

    Raises:
        FileNotFoundError: If the entity doesn't exist.
    """
    path = entity_path(root, namespace, plural, entity_id)
    if not path.exists():
        raise FileNotFoundError(f"Entity not found: {entity_id}")
    entity = json.loads(path.read_text())
    if schema is not None:
        entity = hydrate_defaults(entity, schema)
    return entity


def list_entities(
    root: str | Path,
    namespace: str,
    plural: str,
    status: str = "active",
    limit: int = 50,
    schema: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """List entities of a given type.

    If a schema is provided, missing fields are filled with schema
    defaults before returning (hydrate-on-read).

    Args:
        root: Workspace root directory.
        namespace: App namespace.
        plural: Plural form.
        status: Filter by status (default 'active').
        limit: Maximum number of results.
        schema: Optional JSON Schema — used to hydrate defaults on read.

    Returns:
        List of entity dicts matching the filter.
    """
    directory = entity_dir(root, namespace, plural)
    if not directory.exists():
        return []

    results: list[dict[str, Any]] = []
    for file in directory.glob("*.json"):
        try:
            entity = json.loads(file.read_text())
        except json.JSONDecodeError:
            continue
        if entity.get("status", "active") == status:
            if schema is not None:
                entity = hydrate_defaults(entity, schema)
            results.append(entity)

    results.sort(key=lambda e: e.get("updated_at", ""), reverse=True)
    return results[:limit]


def delete_entity(
    root: str | Path,
    namespace: str,
    plural: str,
    entity_id: str,
    hard: bool = False,
    on_relationships_changed: Callable[[str, list, list], None] | None = None,
) -> dict[str, Any]:
    """Delete an entity (soft delete by default).

    Args:
        root: Workspace root directory.
        namespace: App namespace.
        plural: Plural form.
        entity_id: Entity ID to delete.
        hard: If True, remove the file. If False, set status to 'deleted'.

    Returns:
        The deleted entity dict.

    Raises:
        FileNotFoundError: If the entity doesn't exist.
    """
    path = entity_path(root, namespace, plural, entity_id)
    if not path.exists():
        raise FileNotFoundError(f"Entity not found: {entity_id}")

    # Same lock as update_entity — a concurrent update + delete on the
    # same entity would otherwise race.
    with _entity_lock(path):
        entity = json.loads(path.read_text())

        if hard:
            path.unlink()
        else:
            entity["status"] = "deleted"
            entity["updated_at"] = _now_iso()
            path.write_text(json.dumps(entity, indent=2) + "\n")

    if hard and on_relationships_changed is not None and entity.get("relationships"):
        on_relationships_changed(entity_id, entity["relationships"], [])

    return entity
