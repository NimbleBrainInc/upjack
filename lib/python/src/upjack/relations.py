"""Reverse relationship index for upjack entities.

Maintains a write-time index that maps target entity IDs to the source
entities that reference them.  The index file lives at
``{root}/{namespace}/data/_index/relations.json`` and is updated
atomically (temp file + ``os.replace``) on every CRUD operation that
touches relationships.

The index is an **optimization**, not the source of truth — the
``relationships`` arrays stored on individual entity files are canonical.
If the index file is missing or corrupt, it is rebuilt automatically from
a full directory scan on the next read.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from upjack.paths import index_dir, index_path

logger = logging.getLogger(__name__)

_EMPTY_INDEX: dict[str, Any] = {"reverse": {}}


def load_index(root: str | Path, namespace: str) -> dict[str, Any]:
    """Read the relationship index from disk.

    Returns the parsed index dict, or an empty index structure if the
    file does not exist.
    """
    path = index_path(root, namespace)
    if not path.exists():
        return {"reverse": {}}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupt or unreadable index at %s — will rebuild on next query", path)
        return {"reverse": {}}


def save_index(root: str | Path, namespace: str, index: dict[str, Any]) -> None:
    """Write the relationship index atomically.

    Writes to a temporary file in the same directory, then replaces the
    target via ``os.replace`` to guarantee atomicity.
    """
    path = index_path(root, namespace)
    idir = index_dir(root, namespace)
    idir.mkdir(parents=True, exist_ok=True)

    fd, tmp = tempfile.mkstemp(dir=idir, suffix=".tmp")
    closed = False
    try:
        os.write(fd, json.dumps(index, indent=2).encode())
        os.close(fd)
        closed = True
        os.replace(tmp, path)
    except BaseException:
        if not closed:
            os.close(fd)
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def update_index(
    root: str | Path,
    namespace: str,
    entity_id: str,
    old_rels: list[dict[str, Any]],
    new_rels: list[dict[str, Any]],
) -> None:
    """Update the index after an entity's relationships changed.

    Diffs *old_rels* against *new_rels*, removes stale entries, and adds
    new ones.
    """
    index = load_index(root, namespace)
    reverse = index.setdefault("reverse", {})

    # Build sets of (target, rel) tuples for diffing
    old_set = {(r["target"], r["rel"]) for r in old_rels if "target" in r and "rel" in r}
    new_set = {(r["target"], r["rel"]) for r in new_rels if "target" in r and "rel" in r}

    # Remove stale entries
    for target, rel in old_set - new_set:
        entries = reverse.get(target, [])
        reverse[target] = [e for e in entries if not (e["source"] == entity_id and e["rel"] == rel)]
        if not reverse[target]:
            del reverse[target]

    # Add new entries
    for target, rel in new_set - old_set:
        entries = reverse.setdefault(target, [])
        entry = {"source": entity_id, "rel": rel}
        if entry not in entries:
            entries.append(entry)

    save_index(root, namespace, index)


def remove_from_index(
    root: str | Path,
    namespace: str,
    entity_id: str,
    rels: list[dict[str, Any]],
) -> None:
    """Remove all index entries for a given source entity."""
    if not rels:
        return
    index = load_index(root, namespace)
    reverse = index.get("reverse", {})

    for r in rels:
        target = r.get("target")
        if not target:
            continue
        entries = reverse.get(target, [])
        reverse[target] = [e for e in entries if e["source"] != entity_id]
        if not reverse[target]:
            del reverse[target]

    save_index(root, namespace, index)


def rebuild_index(
    root: str | Path,
    namespace: str,
    entity_defs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Rebuild the index from a full scan of all entity files.

    Args:
        root: Workspace root directory.
        namespace: App namespace.
        entity_defs: List of entity definition dicts, each with at least
            a ``plural`` key.

    Returns:
        The newly built index.
    """
    root = Path(root)
    reverse: dict[str, list[dict[str, str]]] = {}

    for edef in entity_defs:
        plural = edef.get("plural", edef.get("name", "") + "s")
        edir = root / namespace / "data" / plural
        if not edir.is_dir():
            continue
        for file in edir.glob("*.json"):
            try:
                entity = json.loads(file.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            entity_id = entity.get("id", "")
            for rel in entity.get("relationships", []):
                target = rel.get("target")
                rel_name = rel.get("rel")
                if not target or not rel_name:
                    continue
                entries = reverse.setdefault(target, [])
                entry = {"source": entity_id, "rel": rel_name}
                if entry not in entries:
                    entries.append(entry)

    index = {"reverse": reverse}
    save_index(root, namespace, index)
    return index


def query_reverse(
    root: str | Path,
    namespace: str,
    target_id: str,
    rel: str | None = None,
    entity_defs: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Query the reverse index for entities pointing at *target_id*.

    If the index file does not exist and *entity_defs* is provided,
    triggers a full rebuild first.

    Args:
        root: Workspace root directory.
        namespace: App namespace.
        target_id: The entity ID to look up in the reverse index.
        rel: Optional relationship type filter.
        entity_defs: Entity definitions for auto-rebuild (optional).

    Returns:
        List of ``{"source": ..., "rel": ...}`` dicts.
    """
    path = index_path(root, namespace)
    if not path.exists() and entity_defs is not None:
        logger.info("Index missing — rebuilding from entity files")
        rebuild_index(root, namespace, entity_defs)

    index = load_index(root, namespace)
    entries = index.get("reverse", {}).get(target_id, [])

    if rel is not None:
        entries = [e for e in entries if e["rel"] == rel]

    return entries
