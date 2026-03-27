"""Tests for upjack.search module."""

from pathlib import Path

import pytest

from upjack.entity import create_entity
from upjack.search import search_entities

NAMESPACE = "apps/crm"
PLURAL = "contacts"
PREFIX = "ct"


@pytest.fixture
def populated_workspace(tmp_workspace: Path) -> Path:
    """Create a workspace with several contacts for search testing."""
    contacts = [
        {"first_name": "Sarah", "last_name": "Chen", "email": "sarah@acme.com", "lead_score": 85},
        {"first_name": "James", "last_name": "Park", "email": "james@acme.com", "lead_score": 45},
        {
            "first_name": "Alice",
            "last_name": "Wong",
            "email": "alice@bigcorp.com",
            "lead_score": 72,
        },
        {
            "first_name": "Bob",
            "last_name": "Smith",
            "email": "bob@startup.io",
            "lead_score": 30,
            "tags": ["cold-lead"],
        },
    ]

    for data in contacts:
        create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural=PLURAL,
            prefix=PREFIX,
            data=data,
        )

    return tmp_workspace


class TestTextSearch:
    def test_search_by_first_name(self, populated_workspace: Path):
        results = search_entities(populated_workspace, NAMESPACE, PLURAL, query="Sarah")
        assert len(results) == 1
        assert results[0]["first_name"] == "Sarah"

    def test_search_case_insensitive(self, populated_workspace: Path):
        results = search_entities(populated_workspace, NAMESPACE, PLURAL, query="sarah")
        assert len(results) == 1
        assert results[0]["first_name"] == "Sarah"

    def test_search_by_email_domain(self, populated_workspace: Path):
        results = search_entities(populated_workspace, NAMESPACE, PLURAL, query="acme")
        assert len(results) == 2

    def test_search_no_match(self, populated_workspace: Path):
        results = search_entities(populated_workspace, NAMESPACE, PLURAL, query="zzzznotfound")
        assert len(results) == 0

    def test_search_partial_match(self, populated_workspace: Path):
        results = search_entities(populated_workspace, NAMESPACE, PLURAL, query="ark")
        assert len(results) == 1
        assert results[0]["last_name"] == "Park"


class TestStructuredFilters:
    def test_equality_filter(self, populated_workspace: Path):
        results = search_entities(
            populated_workspace, NAMESPACE, PLURAL, filter={"first_name": "Alice"}
        )
        assert len(results) == 1
        assert results[0]["first_name"] == "Alice"

    def test_gte_filter(self, populated_workspace: Path):
        results = search_entities(
            populated_workspace, NAMESPACE, PLURAL, filter={"lead_score": {"$gte": 70}}
        )
        assert len(results) == 2
        scores = {r["lead_score"] for r in results}
        assert scores == {85, 72}

    def test_lt_filter(self, populated_workspace: Path):
        results = search_entities(
            populated_workspace, NAMESPACE, PLURAL, filter={"lead_score": {"$lt": 50}}
        )
        assert len(results) == 2
        scores = {r["lead_score"] for r in results}
        assert scores == {45, 30}

    def test_ne_filter(self, populated_workspace: Path):
        results = search_entities(
            populated_workspace, NAMESPACE, PLURAL, filter={"first_name": {"$ne": "Sarah"}}
        )
        assert len(results) == 3
        names = {r["first_name"] for r in results}
        assert "Sarah" not in names

    def test_in_filter(self, populated_workspace: Path):
        results = search_entities(
            populated_workspace,
            NAMESPACE,
            PLURAL,
            filter={"first_name": {"$in": ["Sarah", "Bob"]}},
        )
        assert len(results) == 2

    def test_contains_filter(self, populated_workspace: Path):
        results = search_entities(
            populated_workspace, NAMESPACE, PLURAL, filter={"tags": {"$contains": "cold-lead"}}
        )
        assert len(results) == 1
        assert results[0]["first_name"] == "Bob"

    def test_exists_filter(self, populated_workspace: Path):
        results = search_entities(
            populated_workspace, NAMESPACE, PLURAL, filter={"lead_score": {"$exists": True}}
        )
        assert len(results) == 4

    def test_gt_filter(self, populated_workspace: Path):
        """$gt is strictly greater than (not >=)."""
        results = search_entities(
            populated_workspace, NAMESPACE, PLURAL, filter={"lead_score": {"$gt": 72}}
        )
        assert len(results) == 1
        assert results[0]["lead_score"] == 85

    def test_gt_excludes_equal(self, populated_workspace: Path):
        results = search_entities(
            populated_workspace, NAMESPACE, PLURAL, filter={"lead_score": {"$gt": 85}}
        )
        assert len(results) == 0

    def test_lte_filter(self, populated_workspace: Path):
        """$lte includes the boundary value."""
        results = search_entities(
            populated_workspace, NAMESPACE, PLURAL, filter={"lead_score": {"$lte": 45}}
        )
        assert len(results) == 2
        scores = {r["lead_score"] for r in results}
        assert scores == {45, 30}

    def test_lte_includes_equal(self, populated_workspace: Path):
        results = search_entities(
            populated_workspace, NAMESPACE, PLURAL, filter={"lead_score": {"$lte": 30}}
        )
        assert len(results) == 1
        assert results[0]["lead_score"] == 30

    def test_exists_false_filters_for_missing_field(self, tmp_workspace: Path):
        """$exists: False should match entities that lack the field."""
        create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural=PLURAL,
            prefix=PREFIX,
            data={"first_name": "Alice", "last_name": "W", "nickname": "Ali"},
        )
        create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural=PLURAL,
            prefix=PREFIX,
            data={"first_name": "Bob", "last_name": "S"},
        )

        # Bob has no nickname
        results = search_entities(
            tmp_workspace, NAMESPACE, PLURAL, filter={"nickname": {"$exists": False}}
        )
        assert len(results) == 1
        assert results[0]["first_name"] == "Bob"

    def test_exists_true_filters_for_present_field(self, tmp_workspace: Path):
        create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural=PLURAL,
            prefix=PREFIX,
            data={"first_name": "Alice", "last_name": "W", "nickname": "Ali"},
        )
        create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural=PLURAL,
            prefix=PREFIX,
            data={"first_name": "Bob", "last_name": "S"},
        )

        results = search_entities(
            tmp_workspace, NAMESPACE, PLURAL, filter={"nickname": {"$exists": True}}
        )
        assert len(results) == 1
        assert results[0]["first_name"] == "Alice"

    def test_combined_filters(self, populated_workspace: Path):
        results = search_entities(
            populated_workspace,
            NAMESPACE,
            PLURAL,
            query="acme",
            filter={"lead_score": {"$gte": 70}},
        )
        assert len(results) == 1
        assert results[0]["first_name"] == "Sarah"


class TestSorting:
    def test_sort_ascending(self, populated_workspace: Path):
        results = search_entities(populated_workspace, NAMESPACE, PLURAL, sort="lead_score")
        scores = [r["lead_score"] for r in results]
        assert scores == sorted(scores)

    def test_sort_descending(self, populated_workspace: Path):
        results = search_entities(populated_workspace, NAMESPACE, PLURAL, sort="-lead_score")
        scores = [r["lead_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_sort_by_name(self, populated_workspace: Path):
        results = search_entities(populated_workspace, NAMESPACE, PLURAL, sort="first_name")
        names = [r["first_name"] for r in results]
        assert names == sorted(names)

    def test_sort_with_missing_field(self, tmp_workspace: Path):
        """Sorting by a field some entities lack should use '' as fallback."""
        create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural=PLURAL,
            prefix=PREFIX,
            data={"first_name": "Alice", "last_name": "A", "nickname": "Ali"},
        )
        create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural=PLURAL,
            prefix=PREFIX,
            data={"first_name": "Bob", "last_name": "B"},
        )

        results = search_entities(tmp_workspace, NAMESPACE, PLURAL, sort="nickname")
        assert len(results) == 2
        # Bob (no nickname → "") sorts before Alice ("Ali")
        assert results[0]["first_name"] == "Bob"
        assert results[1]["first_name"] == "Alice"


class TestLimitAndEdgeCases:
    def test_limit(self, populated_workspace: Path):
        results = search_entities(populated_workspace, NAMESPACE, PLURAL, limit=2)
        assert len(results) == 2

    def test_empty_directory(self, tmp_workspace: Path):
        results = search_entities(tmp_workspace, NAMESPACE, PLURAL)
        assert results == []

    def test_excludes_deleted_by_default(self, populated_workspace: Path):
        # Soft-delete one entity
        all_results = search_entities(populated_workspace, NAMESPACE, PLURAL)
        entity_id = all_results[0]["id"]

        from upjack.entity import delete_entity

        delete_entity(populated_workspace, NAMESPACE, PLURAL, entity_id)

        # Should exclude deleted
        results = search_entities(populated_workspace, NAMESPACE, PLURAL)
        assert len(results) == 3
        assert all(r["id"] != entity_id for r in results)

    def test_includes_deleted_when_filtered(self, populated_workspace: Path):
        all_results = search_entities(populated_workspace, NAMESPACE, PLURAL)
        entity_id = all_results[0]["id"]

        from upjack.entity import delete_entity

        delete_entity(populated_workspace, NAMESPACE, PLURAL, entity_id)

        # Explicit status filter should include deleted
        results = search_entities(
            populated_workspace, NAMESPACE, PLURAL, filter={"status": "deleted"}
        )
        assert len(results) == 1
        assert results[0]["id"] == entity_id


class TestAppIntegration:
    """Test search_entities via UpjackApp."""

    def test_app_search(self, tmp_workspace: Path):
        from upjack.app import UpjackApp

        app = UpjackApp(
            namespace=NAMESPACE,
            entities=[{"name": "contact", "plural": "contacts", "prefix": "ct"}],
            root=tmp_workspace,
        )
        app.create_entity("contact", {"first_name": "Sarah", "last_name": "Chen"})
        app.create_entity("contact", {"first_name": "James", "last_name": "Park"})

        results = app.search_entities("contact", query="Sarah")
        assert len(results) == 1
        assert results[0]["first_name"] == "Sarah"

    def test_app_search_with_filter(self, tmp_workspace: Path):
        from upjack.app import UpjackApp

        app = UpjackApp(
            namespace=NAMESPACE,
            entities=[{"name": "contact", "plural": "contacts", "prefix": "ct"}],
            root=tmp_workspace,
        )
        app.create_entity("contact", {"first_name": "Sarah", "lead_score": 90})
        app.create_entity("contact", {"first_name": "James", "lead_score": 40})

        results = app.search_entities("contact", filter={"lead_score": {"$gte": 70}})
        assert len(results) == 1
        assert results[0]["first_name"] == "Sarah"


class TestSearchHydration:
    """Test that search_entities hydrates defaults from schema."""

    SCHEMA = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "first_name": {"type": "string"},
            "priority": {"type": "string", "default": "medium"},
        },
        "additionalProperties": True,
    }

    def test_search_hydrates_missing_field(self, tmp_workspace: Path):
        """Entities missing a field with a default get it filled on search."""
        create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural=PLURAL,
            prefix=PREFIX,
            data={"first_name": "Sarah"},
        )

        results = search_entities(tmp_workspace, NAMESPACE, PLURAL, schema=self.SCHEMA)
        assert len(results) == 1
        assert results[0]["priority"] == "medium"

    def test_search_does_not_overwrite_existing(self, tmp_workspace: Path):
        create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural=PLURAL,
            prefix=PREFIX,
            data={"first_name": "Sarah", "priority": "high"},
        )

        results = search_entities(tmp_workspace, NAMESPACE, PLURAL, schema=self.SCHEMA)
        assert results[0]["priority"] == "high"

    def test_search_filter_on_hydrated_field(self, tmp_workspace: Path):
        """Filters should work against hydrated default values."""
        # Entity without priority — will be hydrated to "medium"
        create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural=PLURAL,
            prefix=PREFIX,
            data={"first_name": "Alice"},
        )
        # Entity with explicit priority
        create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural=PLURAL,
            prefix=PREFIX,
            data={"first_name": "Bob", "priority": "high"},
        )

        results = search_entities(
            tmp_workspace,
            NAMESPACE,
            PLURAL,
            filter={"priority": "medium"},
            schema=self.SCHEMA,
        )
        assert len(results) == 1
        assert results[0]["first_name"] == "Alice"


class TestCorruptJsonResilience:
    """Verify that corrupt JSON files are skipped during search."""

    def test_search_skips_corrupt_json(self, tmp_workspace: Path):
        """search_entities skips corrupt files and returns valid matches."""
        create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural=PLURAL,
            prefix=PREFIX,
            data={"first_name": "Valid"},
        )

        from upjack.paths import entity_dir

        corrupt_path = entity_dir(tmp_workspace, NAMESPACE, PLURAL) / "corrupt.json"
        corrupt_path.write_text("{not valid json")

        results = search_entities(tmp_workspace, NAMESPACE, PLURAL, query="Valid")
        assert len(results) == 1
        assert results[0]["first_name"] == "Valid"

    def test_search_returns_empty_when_all_corrupt(self, tmp_workspace: Path):
        """search_entities returns [] when every file is corrupt."""
        from upjack.paths import entity_dir

        directory = entity_dir(tmp_workspace, NAMESPACE, PLURAL)
        directory.mkdir(parents=True)
        (directory / "bad1.json").write_text("not json")
        (directory / "bad2.json").write_text("{broken")

        results = search_entities(tmp_workspace, NAMESPACE, PLURAL)
        assert results == []
