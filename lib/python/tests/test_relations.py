"""Tests for upjack.relations module."""

import json

import pytest

from upjack.relations import (
    load_index,
    query_reverse,
    rebuild_index,
    remove_from_index,
    save_index,
    update_index,
)


@pytest.fixture
def workspace(tmp_path):
    """Create a workspace with namespace directory structure."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


NAMESPACE = "apps/crm"


class TestLoadSaveIndex:
    def test_load_returns_empty_for_nonexistent(self, workspace):
        index = load_index(workspace, NAMESPACE)
        assert index == {"reverse": {}}

    def test_save_and_load_roundtrip(self, workspace):
        index = {
            "reverse": {
                "cp_01ABC": [{"source": "pr_01DEF", "rel": "belongs_to"}],
            }
        }
        save_index(workspace, NAMESPACE, index)
        loaded = load_index(workspace, NAMESPACE)
        assert loaded == index

    def test_save_creates_directory(self, workspace):
        save_index(workspace, NAMESPACE, {"reverse": {}})
        index_file = workspace / NAMESPACE / "data" / "_index" / "relations.json"
        assert index_file.exists()

    def test_corrupt_json_returns_empty(self, workspace):
        index_dir = workspace / NAMESPACE / "data" / "_index"
        index_dir.mkdir(parents=True)
        (index_dir / "relations.json").write_text("{corrupt")
        index = load_index(workspace, NAMESPACE)
        assert index == {"reverse": {}}


class TestUpdateIndex:
    def test_add_new_relationships(self, workspace):
        new_rels = [
            {"rel": "belongs_to", "target": "cp_01ABC"},
            {"rel": "assigned_to", "target": "usr_01XYZ"},
        ]
        update_index(workspace, NAMESPACE, "pr_01DEF", [], new_rels)

        index = load_index(workspace, NAMESPACE)
        assert {"source": "pr_01DEF", "rel": "belongs_to"} in index["reverse"]["cp_01ABC"]
        assert {"source": "pr_01DEF", "rel": "assigned_to"} in index["reverse"]["usr_01XYZ"]

    def test_change_relationship_target(self, workspace):
        old_rels = [{"rel": "belongs_to", "target": "cp_01OLD"}]
        new_rels = [{"rel": "belongs_to", "target": "cp_01NEW"}]

        update_index(workspace, NAMESPACE, "pr_01DEF", [], old_rels)
        update_index(workspace, NAMESPACE, "pr_01DEF", old_rels, new_rels)

        index = load_index(workspace, NAMESPACE)
        assert "cp_01OLD" not in index["reverse"]
        assert {"source": "pr_01DEF", "rel": "belongs_to"} in index["reverse"]["cp_01NEW"]

    def test_remove_all_relationships(self, workspace):
        old_rels = [{"rel": "belongs_to", "target": "cp_01ABC"}]
        update_index(workspace, NAMESPACE, "pr_01DEF", [], old_rels)
        update_index(workspace, NAMESPACE, "pr_01DEF", old_rels, [])

        index = load_index(workspace, NAMESPACE)
        assert "cp_01ABC" not in index["reverse"]

    def test_no_duplicates_on_repeated_update(self, workspace):
        rels = [{"rel": "belongs_to", "target": "cp_01ABC"}]
        update_index(workspace, NAMESPACE, "pr_01DEF", [], rels)
        update_index(workspace, NAMESPACE, "pr_01DEF", rels, rels)

        index = load_index(workspace, NAMESPACE)
        entries = index["reverse"]["cp_01ABC"]
        matching = [e for e in entries if e["source"] == "pr_01DEF"]
        assert len(matching) == 1

    def test_multiple_sources_same_target(self, workspace):
        update_index(
            workspace, NAMESPACE, "pr_01AAA", [], [{"rel": "belongs_to", "target": "cp_01ABC"}]
        )
        update_index(
            workspace, NAMESPACE, "pr_01BBB", [], [{"rel": "belongs_to", "target": "cp_01ABC"}]
        )

        index = load_index(workspace, NAMESPACE)
        entries = index["reverse"]["cp_01ABC"]
        assert len(entries) == 2
        sources = {e["source"] for e in entries}
        assert sources == {"pr_01AAA", "pr_01BBB"}


class TestRemoveFromIndex:
    def test_removes_all_entries_for_entity(self, workspace):
        update_index(
            workspace,
            NAMESPACE,
            "pr_01DEF",
            [],
            [
                {"rel": "belongs_to", "target": "cp_01ABC"},
                {"rel": "assigned_to", "target": "usr_01XYZ"},
            ],
        )
        remove_from_index(
            workspace,
            NAMESPACE,
            "pr_01DEF",
            [
                {"rel": "belongs_to", "target": "cp_01ABC"},
                {"rel": "assigned_to", "target": "usr_01XYZ"},
            ],
        )

        index = load_index(workspace, NAMESPACE)
        assert "cp_01ABC" not in index["reverse"]
        assert "usr_01XYZ" not in index["reverse"]

    def test_preserves_other_entities(self, workspace):
        update_index(
            workspace, NAMESPACE, "pr_01AAA", [], [{"rel": "belongs_to", "target": "cp_01ABC"}]
        )
        update_index(
            workspace, NAMESPACE, "pr_01BBB", [], [{"rel": "belongs_to", "target": "cp_01ABC"}]
        )
        remove_from_index(
            workspace, NAMESPACE, "pr_01AAA", [{"rel": "belongs_to", "target": "cp_01ABC"}]
        )

        index = load_index(workspace, NAMESPACE)
        entries = index["reverse"]["cp_01ABC"]
        assert len(entries) == 1
        assert entries[0]["source"] == "pr_01BBB"

    def test_noop_for_empty_rels(self, workspace):
        remove_from_index(workspace, NAMESPACE, "pr_01DEF", [])
        # Should not create index file
        assert not (workspace / NAMESPACE / "data" / "_index" / "relations.json").exists()


class TestRebuildIndex:
    def test_rebuilds_from_entity_files(self, workspace):
        # Create entity files with relationships
        contacts_dir = workspace / NAMESPACE / "data" / "contacts"
        contacts_dir.mkdir(parents=True)
        (contacts_dir / "ct_01AAA.json").write_text(
            json.dumps(
                {
                    "id": "ct_01AAA",
                    "type": "contact",
                    "relationships": [{"rel": "works_at", "target": "co_01BBB"}],
                }
            )
        )
        deals_dir = workspace / NAMESPACE / "data" / "deals"
        deals_dir.mkdir(parents=True)
        (deals_dir / "dl_01CCC.json").write_text(
            json.dumps(
                {
                    "id": "dl_01CCC",
                    "type": "deal",
                    "relationships": [
                        {"rel": "contact", "target": "ct_01AAA"},
                        {"rel": "company", "target": "co_01BBB"},
                    ],
                }
            )
        )

        entity_defs = [
            {"plural": "contacts"},
            {"plural": "deals"},
            {"plural": "companies"},
        ]
        index = rebuild_index(workspace, NAMESPACE, entity_defs)

        assert {"source": "ct_01AAA", "rel": "works_at"} in index["reverse"]["co_01BBB"]
        assert {"source": "dl_01CCC", "rel": "contact"} in index["reverse"]["ct_01AAA"]
        assert {"source": "dl_01CCC", "rel": "company"} in index["reverse"]["co_01BBB"]

    def test_skips_corrupt_files(self, workspace):
        contacts_dir = workspace / NAMESPACE / "data" / "contacts"
        contacts_dir.mkdir(parents=True)
        (contacts_dir / "ct_01AAA.json").write_text("{corrupt json")
        (contacts_dir / "ct_01BBB.json").write_text(
            json.dumps(
                {
                    "id": "ct_01BBB",
                    "type": "contact",
                    "relationships": [{"rel": "works_at", "target": "co_01CCC"}],
                }
            )
        )

        index = rebuild_index(workspace, NAMESPACE, [{"plural": "contacts"}])
        assert "co_01CCC" in index["reverse"]

    def test_skips_missing_directories(self, workspace):
        index = rebuild_index(workspace, NAMESPACE, [{"plural": "nonexistent"}])
        assert index == {"reverse": {}}


class TestQueryReverse:
    def test_returns_matching_entries(self, workspace):
        update_index(
            workspace, NAMESPACE, "pr_01DEF", [], [{"rel": "belongs_to", "target": "cp_01ABC"}]
        )

        results = query_reverse(workspace, NAMESPACE, "cp_01ABC")
        assert len(results) == 1
        assert results[0] == {"source": "pr_01DEF", "rel": "belongs_to"}

    def test_filters_by_rel(self, workspace):
        update_index(
            workspace,
            NAMESPACE,
            "pr_01DEF",
            [],
            [
                {"rel": "belongs_to", "target": "cp_01ABC"},
                {"rel": "assigned_to", "target": "cp_01ABC"},
            ],
        )

        results = query_reverse(workspace, NAMESPACE, "cp_01ABC", rel="belongs_to")
        assert len(results) == 1
        assert results[0]["rel"] == "belongs_to"

    def test_returns_empty_for_unknown_target(self, workspace):
        results = query_reverse(workspace, NAMESPACE, "unknown_01ABC")
        assert results == []

    def test_auto_rebuilds_when_missing(self, workspace):
        # Create entity with relationship but no index
        contacts_dir = workspace / NAMESPACE / "data" / "contacts"
        contacts_dir.mkdir(parents=True)
        (contacts_dir / "ct_01AAA.json").write_text(
            json.dumps(
                {
                    "id": "ct_01AAA",
                    "type": "contact",
                    "relationships": [{"rel": "works_at", "target": "co_01BBB"}],
                }
            )
        )

        entity_defs = [{"plural": "contacts"}]
        results = query_reverse(workspace, NAMESPACE, "co_01BBB", entity_defs=entity_defs)
        assert len(results) == 1
        assert results[0]["source"] == "ct_01AAA"

    def test_does_not_rebuild_without_entity_defs(self, workspace):
        results = query_reverse(workspace, NAMESPACE, "co_01BBB")
        assert results == []
