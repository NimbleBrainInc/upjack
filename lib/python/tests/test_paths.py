"""Tests for upjack.paths module."""

from pathlib import Path

import pytest

from upjack.paths import entity_dir, entity_path, index_dir, index_path, resolve_root, schema_dir


class TestSchemaDir:
    """Cover the previously-untested schema_dir function."""

    def test_returns_correct_path(self):
        result = schema_dir(Path("/workspace"), "apps/crm")
        assert result == Path("/workspace/apps/crm/schemas")

    def test_accepts_string_root(self):
        result = schema_dir("/workspace", "apps/crm")
        assert result == Path("/workspace/apps/crm/schemas")

    def test_different_namespaces(self):
        assert schema_dir("/ws", "apps/crm") != schema_dir("/ws", "apps/research")


class TestIndexDir:
    def test_returns_correct_path(self):
        result = index_dir(Path("/workspace"), "apps/crm")
        assert result == Path("/workspace/apps/crm/data/_index")

    def test_accepts_string_root(self):
        result = index_dir("/workspace", "apps/crm")
        assert result == Path("/workspace/apps/crm/data/_index")

    def test_traversal_rejected(self, tmp_path):
        root = tmp_path / "workspace"
        root.mkdir()
        with pytest.raises(ValueError, match="Path escapes workspace root"):
            index_dir(root, "../../etc")


class TestIndexPath:
    def test_returns_correct_path(self):
        result = index_path(Path("/workspace"), "apps/crm")
        assert result == Path("/workspace/apps/crm/data/_index/relations.json")

    def test_accepts_string_root(self):
        result = index_path("/workspace", "apps/crm")
        assert result == Path("/workspace/apps/crm/data/_index/relations.json")

    def test_is_child_of_index_dir(self):
        d = index_dir("/ws", "apps/crm")
        p = index_path("/ws", "apps/crm")
        assert p.parent == d
        assert p.name == "relations.json"

    def test_traversal_rejected(self, tmp_path):
        root = tmp_path / "workspace"
        root.mkdir()
        with pytest.raises(ValueError, match="Path escapes workspace root"):
            index_path(root, "../../etc")


class TestPathConsistency:
    """Verify entity_path builds on entity_dir correctly."""

    def test_entity_path_is_child_of_entity_dir(self):
        d = entity_dir("/ws", "apps/crm", "contacts")
        p = entity_path("/ws", "apps/crm", "contacts", "ct_01ABC")
        assert p.parent == d
        assert p.name == "ct_01ABC.json"


class TestPathTraversal:
    """Verify that path traversal in entity_id or namespace is rejected."""

    def test_entity_id_with_traversal_rejected(self, tmp_path):
        """An entity_id with '../' that escapes the workspace raises ValueError."""
        root = tmp_path / "workspace"
        root.mkdir()
        with pytest.raises(ValueError, match="Path escapes workspace root"):
            entity_path(root, "apps/crm", "contacts", "../../../../../../etc/passwd")

    def test_namespace_with_traversal_rejected(self, tmp_path):
        """A namespace containing '../' that escapes the workspace raises ValueError."""
        root = tmp_path / "workspace"
        root.mkdir()
        with pytest.raises(ValueError, match="Path escapes workspace root"):
            entity_dir(root, "../../etc", "contacts")

    def test_traversal_within_workspace_allowed(self, tmp_path):
        """Traversal that stays within the workspace root is permitted.

        A path like contacts/../deals/ resolves within root, so the workspace
        root check correctly allows it. The security boundary is the workspace
        root, not per-entity-type isolation.
        """
        root = tmp_path / "workspace"
        root.mkdir()
        # This resolves to root/apps/crm/data/deals/dl_01FAKE.json — within root
        path = entity_path(root, "apps/crm", "contacts", "../deals/dl_01FAKE")
        assert path.resolve().is_relative_to(root.resolve())

    def test_clean_paths_still_work(self, tmp_path):
        """Normal entity_id and namespace values are not rejected."""
        root = tmp_path / "workspace"
        root.mkdir()
        path = entity_path(root, "apps/crm", "contacts", "ct_01ABCDEFGHIJKLMNOPQRSTUVWX")
        assert path.name == "ct_01ABCDEFGHIJKLMNOPQRSTUVWX.json"


class TestResolveRoot:
    """Tests for resolve_root() priority chain."""

    def test_env_var_takes_priority(self, monkeypatch):
        monkeypatch.setenv("UPJACK_ROOT", "/custom/root")
        result = resolve_root("/ignored")
        assert result == Path("/custom/root")

    def test_cli_root_when_no_env(self, monkeypatch):
        monkeypatch.delenv("UPJACK_ROOT", raising=False)
        result = resolve_root("/explicit")
        assert result == Path("/explicit")

    def test_fallback_to_dot_upjack(self, monkeypatch):
        monkeypatch.delenv("UPJACK_ROOT", raising=False)
        result = resolve_root()
        assert result.name == ".upjack"

    def test_env_beats_cli_root(self, monkeypatch):
        monkeypatch.setenv("UPJACK_ROOT", "/from-env")
        result = resolve_root("/from-cli")
        assert result == Path("/from-env")
