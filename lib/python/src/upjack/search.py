"""In-memory search over entity JSON files."""

import json
from pathlib import Path
from typing import Any

from upjack.paths import entity_dir
from upjack.schema import hydrate_defaults


def _match_text(entity: dict[str, Any], query: str) -> bool:
    """Case-insensitive substring match across all string-valued fields."""
    q = query.lower()
    for value in entity.values():
        if isinstance(value, str) and q in value.lower():
            return True
    return False


def _match_filter(entity: dict[str, Any], filters: dict[str, Any]) -> bool:
    """Match entity against structured filters."""
    for key, condition in filters.items():
        value = entity.get(key)

        if isinstance(condition, dict):
            for op, operand in condition.items():
                if op == "$gt":
                    if value is None or value <= operand:
                        return False
                elif op == "$gte":
                    if value is None or value < operand:
                        return False
                elif op == "$lt":
                    if value is None or value >= operand:
                        return False
                elif op == "$lte":
                    if value is None or value > operand:
                        return False
                elif op == "$ne":
                    if value == operand:
                        return False
                elif op == "$in":
                    if value not in operand:
                        return False
                elif op == "$contains":
                    if not isinstance(value, list) or operand not in value:
                        return False
                elif op == "$exists":
                    exists = key in entity and entity[key] is not None
                    if exists != operand:
                        return False
        else:
            # Direct equality
            if value != condition:
                return False

    return True


def _sort_key(entity: dict[str, Any], field: str) -> Any:
    """Extract a sort key, handling missing values."""
    value = entity.get(field)
    if value is None:
        return ""
    return value


def search_entities(
    root: str | Path,
    namespace: str,
    plural: str,
    query: str | None = None,
    filter: dict[str, Any] | None = None,
    sort: str = "-updated_at",
    limit: int = 20,
    schema: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Search entities with text query and structured filters.

    If a schema is provided, missing fields are filled with schema
    defaults before filtering and returning (hydrate-on-read).

    Args:
        root: Workspace root directory.
        namespace: App namespace (e.g., 'apps/crm').
        plural: Entity plural name (e.g., 'contacts').
        query: Optional substring to match across all string fields.
        filter: Optional structured filters (equality, comparisons, etc.).
        sort: Field name to sort by. Prefix with '-' for descending.
        limit: Maximum number of results.
        schema: Optional JSON Schema — used to hydrate defaults on read.

    Returns:
        List of matching entity dicts.
    """
    directory = entity_dir(root, namespace, plural)
    if not directory.exists():
        return []

    # Load all entities, skipping corrupt files
    entities: list[dict[str, Any]] = []
    for file in directory.glob("*.json"):
        try:
            entity = json.loads(file.read_text())
        except json.JSONDecodeError:
            continue
        if schema is not None:
            entity = hydrate_defaults(entity, schema)
        entities.append(entity)

    # Exclude deleted unless filter explicitly targets status
    filter_targets_status = filter is not None and "status" in filter
    if not filter_targets_status:
        entities = [e for e in entities if e.get("status", "active") != "deleted"]

    # Apply text query
    if query:
        entities = [e for e in entities if _match_text(e, query)]

    # Apply structured filters
    if filter:
        entities = [e for e in entities if _match_filter(e, filter)]

    # Sort
    descending = sort.startswith("-")
    sort_field = sort.lstrip("-")
    entities.sort(key=lambda e: _sort_key(e, sort_field), reverse=descending)

    # Limit
    return entities[:limit]
