"""Workspace path resolution for upjack apps."""

import os
from pathlib import Path


def resolve_root(cli_root: str | Path | None = None) -> Path:
    """Resolve the workspace root directory.

    Priority: UPJACK_ROOT env var > cli_root argument > .upjack fallback.
    """
    env = os.environ.get("UPJACK_ROOT")
    if env:
        return Path(env).resolve()
    if cli_root is not None:
        return Path(cli_root).resolve()
    return Path(".upjack").resolve()


def _check_within_root(root: Path, target: Path) -> Path:
    """Verify that target resolves within root and return the resolved path.

    Raises:
        ValueError: If the resolved path escapes the workspace root.
    """
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    # Use os.path prefix check with trailing separator to avoid
    # false matches like /workspace-evil matching /workspace.
    root_str = str(root_resolved) + "/"
    target_str = str(target_resolved)
    if not (target_str == str(root_resolved) or target_str.startswith(root_str)):
        raise ValueError(f"Path escapes workspace root: {target} resolves to {target_resolved}")
    return target


def entity_dir(root: str | Path, namespace: str, plural: str) -> Path:
    """Get the directory path for an entity type's data.

    Args:
        root: Workspace root directory.
        namespace: App namespace (e.g., 'apps/crm').
        plural: Entity plural name (e.g., 'contacts').

    Returns:
        Path to the entity data directory.

    Raises:
        ValueError: If the resolved path escapes the workspace root.
    """
    root = Path(root)
    target = root / namespace / "data" / plural
    return _check_within_root(root, target)


def entity_path(root: str | Path, namespace: str, plural: str, entity_id: str) -> Path:
    """Get the file path for a specific entity.

    Args:
        root: Workspace root directory.
        namespace: App namespace (e.g., 'apps/crm').
        plural: Entity plural name (e.g., 'contacts').
        entity_id: Prefixed ULID (e.g., 'ct_01JKXM...').

    Returns:
        Path to the entity JSON file.

    Raises:
        ValueError: If the resolved path escapes the workspace root.
    """
    root = Path(root)
    target = root / namespace / "data" / plural / f"{entity_id}.json"
    return _check_within_root(root, target)


def index_dir(root: str | Path, namespace: str) -> Path:
    """Get the directory path for the relationship index.

    Args:
        root: Workspace root directory.
        namespace: App namespace (e.g., 'apps/crm').

    Returns:
        Path to the index directory.

    Raises:
        ValueError: If the resolved path escapes the workspace root.
    """
    root = Path(root)
    target = root / namespace / "data" / "_index"
    return _check_within_root(root, target)


def index_path(root: str | Path, namespace: str) -> Path:
    """Get the file path for the relationship index.

    Args:
        root: Workspace root directory.
        namespace: App namespace (e.g., 'apps/crm').

    Returns:
        Path to the relations.json index file.

    Raises:
        ValueError: If the resolved path escapes the workspace root.
    """
    root = Path(root)
    target = root / namespace / "data" / "_index" / "relations.json"
    return _check_within_root(root, target)


def schema_dir(root: str | Path, namespace: str) -> Path:
    """Get the directory path for an app's schemas.

    Args:
        root: Workspace root directory.
        namespace: App namespace (e.g., 'apps/crm').

    Returns:
        Path to the schemas directory.

    Raises:
        ValueError: If the resolved path escapes the workspace root.
    """
    root = Path(root)
    target = root / namespace / "schemas"
    return _check_within_root(root, target)
