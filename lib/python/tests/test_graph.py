"""Tests for graph traversal methods on UpjackApp."""

import pytest

from upjack.app import UpjackApp

NAMESPACE = "apps/crm"
ENTITIES = [
    {"name": "contact", "plural": "contacts", "prefix": "ct", "schema": "s.json"},
    {"name": "company", "plural": "companies", "prefix": "co", "schema": "s.json"},
    {"name": "deal", "plural": "deals", "prefix": "dl", "schema": "s.json"},
]


@pytest.fixture
def app(tmp_workspace):
    return UpjackApp(namespace=NAMESPACE, entities=ENTITIES, root=tmp_workspace)


# ===========================================================================
# Prefix resolution
# ===========================================================================


class TestPrefixResolution:
    def test_resolves_known_prefix(self, app):
        assert app._resolve_type("ct_01ABCDEFGHIJKLMNOPQRSTUVWX") == "contact"
        assert app._resolve_type("co_01ABCDEFGHIJKLMNOPQRSTUVWX") == "company"
        assert app._resolve_type("dl_01ABCDEFGHIJKLMNOPQRSTUVWX") == "deal"

    def test_unknown_prefix_raises(self, app):
        with pytest.raises(ValueError, match="Unknown prefix"):
            app._resolve_type("xx_01ABCDEFGHIJKLMNOPQRSTUVWX")

    def test_all_entity_types_covered(self, app):
        assert set(app._prefix_map.values()) == {"contact", "company", "deal"}


# ===========================================================================
# query_by_relationship
# ===========================================================================


class TestQueryByRelationship:
    def test_returns_matching_entities(self, app):
        company = app.create_entity("company", {"name": "Acme"})
        ct1 = app.create_entity(
            "contact",
            {
                "first_name": "Alice",
                "relationships": [{"rel": "works_at", "target": company["id"]}],
            },
        )
        ct2 = app.create_entity(
            "contact",
            {
                "first_name": "Bob",
                "relationships": [{"rel": "works_at", "target": company["id"]}],
            },
        )
        # Unrelated contact
        app.create_entity("contact", {"first_name": "Charlie"})

        results = app.query_by_relationship("contact", "works_at", company["id"])
        ids = {r["id"] for r in results}
        assert ids == {ct1["id"], ct2["id"]}

    def test_filters_by_rel_name(self, app):
        company = app.create_entity("company", {"name": "Acme"})
        app.create_entity(
            "contact",
            {
                "first_name": "Alice",
                "relationships": [{"rel": "works_at", "target": company["id"]}],
            },
        )
        app.create_entity(
            "deal",
            {
                "title": "Big Deal",
                "relationships": [{"rel": "company", "target": company["id"]}],
            },
        )

        contacts = app.query_by_relationship("contact", "works_at", company["id"])
        assert len(contacts) == 1
        assert contacts[0]["first_name"] == "Alice"

    def test_additional_filter(self, app):
        company = app.create_entity("company", {"name": "Acme"})
        app.create_entity(
            "contact",
            {
                "first_name": "Alice",
                "relationships": [{"rel": "works_at", "target": company["id"]}],
            },
        )
        app.create_entity(
            "contact",
            {
                "first_name": "Bob",
                "relationships": [{"rel": "works_at", "target": company["id"]}],
            },
        )

        results = app.query_by_relationship(
            "contact", "works_at", company["id"], filter={"first_name": "Alice"}
        )
        assert len(results) == 1
        assert results[0]["first_name"] == "Alice"

    def test_returns_empty_for_no_matches(self, app):
        results = app.query_by_relationship("contact", "works_at", "co_NONEXISTENT")
        assert results == []

    def test_respects_limit(self, app):
        company = app.create_entity("company", {"name": "Acme"})
        for i in range(5):
            app.create_entity(
                "contact",
                {
                    "first_name": f"Person{i}",
                    "relationships": [{"rel": "works_at", "target": company["id"]}],
                },
            )

        results = app.query_by_relationship("contact", "works_at", company["id"], limit=2)
        assert len(results) == 2

    def test_excludes_deleted_entities(self, app):
        company = app.create_entity("company", {"name": "Acme"})
        contact = app.create_entity(
            "contact",
            {
                "first_name": "Alice",
                "relationships": [{"rel": "works_at", "target": company["id"]}],
            },
        )
        app.delete_entity("contact", contact["id"])  # soft delete

        results = app.query_by_relationship("contact", "works_at", company["id"])
        assert len(results) == 0


# ===========================================================================
# get_related
# ===========================================================================


class TestGetRelated:
    def test_forward_returns_resolved_targets(self, app):
        company = app.create_entity("company", {"name": "Acme"})
        contact = app.create_entity(
            "contact",
            {
                "first_name": "Alice",
                "relationships": [{"rel": "works_at", "target": company["id"]}],
            },
        )

        results = app.get_related(contact["id"], direction="forward")
        assert len(results) == 1
        assert results[0]["id"] == company["id"]
        assert results[0]["name"] == "Acme"

    def test_forward_with_rel_filter(self, app):
        company = app.create_entity("company", {"name": "Acme"})
        other = app.create_entity("company", {"name": "Other"})
        contact = app.create_entity(
            "contact",
            {
                "first_name": "Alice",
                "relationships": [
                    {"rel": "works_at", "target": company["id"]},
                    {"rel": "client_of", "target": other["id"]},
                ],
            },
        )

        results = app.get_related(contact["id"], rel="works_at", direction="forward")
        assert len(results) == 1
        assert results[0]["name"] == "Acme"

    def test_reverse_returns_entities_pointing_here(self, app):
        company = app.create_entity("company", {"name": "Acme"})
        ct1 = app.create_entity(
            "contact",
            {
                "first_name": "Alice",
                "relationships": [{"rel": "works_at", "target": company["id"]}],
            },
        )

        results = app.get_related(company["id"], direction="reverse")
        assert len(results) == 1
        assert results[0]["id"] == ct1["id"]

    def test_reverse_with_rel_filter(self, app):
        company = app.create_entity("company", {"name": "Acme"})
        app.create_entity(
            "contact",
            {
                "first_name": "Alice",
                "relationships": [{"rel": "works_at", "target": company["id"]}],
            },
        )
        app.create_entity(
            "deal",
            {
                "title": "Big Deal",
                "relationships": [{"rel": "company", "target": company["id"]}],
            },
        )

        results = app.get_related(company["id"], rel="works_at", direction="reverse")
        assert len(results) == 1
        assert results[0]["first_name"] == "Alice"

    def test_no_relationships_returns_empty(self, app):
        contact = app.create_entity("contact", {"first_name": "Alice"})
        results = app.get_related(contact["id"], direction="forward")
        assert results == []

    def test_invalid_direction_raises(self, app):
        contact = app.create_entity("contact", {"first_name": "Alice"})
        with pytest.raises(ValueError, match="direction must be"):
            app.get_related(contact["id"], direction="sideways")

    def test_missing_target_skipped_gracefully(self, app):
        """Forward traversal skips targets that no longer exist."""
        company = app.create_entity("company", {"name": "Acme"})
        contact = app.create_entity(
            "contact",
            {
                "first_name": "Alice",
                "relationships": [{"rel": "works_at", "target": company["id"]}],
            },
        )
        app.delete_entity("company", company["id"], hard=True)

        results = app.get_related(contact["id"], direction="forward")
        assert results == []


# ===========================================================================
# get_composite
# ===========================================================================


class TestGetComposite:
    def test_includes_forward_and_reverse(self, app):
        company = app.create_entity("company", {"name": "Acme"})
        contact = app.create_entity(
            "contact",
            {
                "first_name": "Alice",
                "relationships": [{"rel": "works_at", "target": company["id"]}],
            },
        )
        deal = app.create_entity(
            "deal",
            {
                "title": "Big Deal",
                "relationships": [
                    {"rel": "primary_contact", "target": contact["id"]},
                    {"rel": "company", "target": company["id"]},
                ],
            },
        )

        result = app.get_composite("contact", contact["id"])

        # Forward: contact works_at company
        assert "works_at" in result["_related"]
        assert result["_related"]["works_at"][0]["id"] == company["id"]

        # Reverse: deal has primary_contact → contact
        assert "~primary_contact" in result["_related"]
        assert result["_related"]["~primary_contact"][0]["id"] == deal["id"]

    def test_forward_rels_keyed_by_rel_name(self, app):
        company = app.create_entity("company", {"name": "Acme"})
        other_co = app.create_entity("company", {"name": "Other"})
        contact = app.create_entity(
            "contact",
            {
                "first_name": "Alice",
                "relationships": [
                    {"rel": "works_at", "target": company["id"]},
                    {"rel": "client_of", "target": other_co["id"]},
                ],
            },
        )

        result = app.get_composite("contact", contact["id"])
        assert set(result["_related"].keys()) >= {"works_at", "client_of"}

    def test_reverse_rels_prefixed_with_tilde(self, app):
        company = app.create_entity("company", {"name": "Acme"})
        app.create_entity(
            "contact",
            {
                "first_name": "Alice",
                "relationships": [{"rel": "works_at", "target": company["id"]}],
            },
        )

        result = app.get_composite("company", company["id"])
        assert "~works_at" in result["_related"]

    def test_no_relationships_empty_related(self, app):
        contact = app.create_entity("contact", {"first_name": "Alice"})
        result = app.get_composite("contact", contact["id"])
        assert result["_related"] == {}

    def test_depth_zero_no_traversal(self, app):
        company = app.create_entity("company", {"name": "Acme"})
        app.create_entity(
            "contact",
            {
                "first_name": "Alice",
                "relationships": [{"rel": "works_at", "target": company["id"]}],
            },
        )

        result = app.get_composite("company", company["id"], depth=0)
        assert result["_related"] == {}
