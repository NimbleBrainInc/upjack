"""Tests for the activity module and activity tracking on UpjackApp."""

import json
import time

import pytest

from upjack.activity import ACTIVITY_ENTITY_DEF, get_activity_schema
from upjack.app import UpjackApp
from upjack.schema import BASE_ENTITY_MARKER

NAMESPACE = "apps/test"
ENTITIES = [
    {
        "name": "contact",
        "plural": "contacts",
        "schema": "schemas/contact.schema.json",
        "prefix": "ct",
    },
]


# ------------------------------------------------------------------
# Activity schema
# ------------------------------------------------------------------


class TestActivitySchema:
    def test_schema_loads(self):
        schema = get_activity_schema()
        assert schema["title"] == "Upjack Activity"
        assert "action" in schema["properties"]
        assert "detail" in schema["properties"]

    def test_schema_requires_action(self):
        schema = get_activity_schema()
        assert "action" in schema["required"]

    def test_schema_detail_is_optional_with_default(self):
        schema = get_activity_schema()
        detail = schema["properties"]["detail"]
        assert detail["type"] == "object"
        assert detail["default"] == {}

    def test_schema_inlines_base_entity(self):
        """get_activity_schema() returns a fully self-contained schema — the
        base entity $ref is inlined at load time, so no downstream consumer
        needs to dereference it over the network."""
        schema = get_activity_schema()
        assert "allOf" in schema
        # No unresolved $refs and no leftover $id (both trip up validators
        # that auto-register schemas by identifier).
        for entry in schema["allOf"]:
            assert "$ref" not in entry, f"Unresolved $ref in allOf: {entry.get('$ref')}"
            assert "$id" not in entry, f"Stray $id in inlined allOf: {entry.get('$id')}"
        # The inlined base member carries our non-standard marker
        base = next((e for e in schema["allOf"] if e.get(BASE_ENTITY_MARKER) is True), None)
        assert base is not None, "base entity schema not inlined into allOf"
        assert "id" in base["properties"]
        assert "created_at" in base["properties"]


class TestActivityEntityDef:
    def test_def_fields(self):
        assert ACTIVITY_ENTITY_DEF["name"] == "activity"
        assert ACTIVITY_ENTITY_DEF["plural"] == "activities"
        assert ACTIVITY_ENTITY_DEF["prefix"] == "act"
        assert "schema" in ACTIVITY_ENTITY_DEF


# ------------------------------------------------------------------
# Manifest parsing
# ------------------------------------------------------------------


def _make_manifest(tmp_workspace, *, activities=None, extra_entities=None):
    """Helper to write a manifest and return its path."""
    entities = [
        {
            "name": "contact",
            "plural": "contacts",
            "schema": "schemas/contact.schema.json",
            "prefix": "ct",
        },
    ]
    if extra_entities:
        entities.extend(extra_entities)

    upjack_ext = {
        "upjack_version": "0.1",
        "namespace": NAMESPACE,
        "entities": entities,
    }
    if activities is not None:
        upjack_ext["activities"] = activities

    manifest = {
        "manifest_version": "0.4",
        "name": "test",
        "version": "1.0.0",
        "_meta": {"ai.nimblebrain/upjack": upjack_ext},
    }
    path = tmp_workspace / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


class TestManifestActivities:
    def test_activities_true_registers_activity_type(self, tmp_workspace):
        path = _make_manifest(tmp_workspace, activities=True)
        app = UpjackApp.from_manifest(path, root=tmp_workspace)
        assert "activity" in app._entities
        assert "activity" in app._schemas

    def test_activities_false_does_not_register(self, tmp_workspace):
        path = _make_manifest(tmp_workspace, activities=False)
        app = UpjackApp.from_manifest(path, root=tmp_workspace)
        assert "activity" not in app._entities

    def test_activities_absent_does_not_register(self, tmp_workspace):
        path = _make_manifest(tmp_workspace)
        app = UpjackApp.from_manifest(path, root=tmp_workspace)
        assert "activity" not in app._entities

    def test_collision_with_user_defined_activity_raises(self, tmp_workspace):
        extra = [
            {
                "name": "activity",
                "plural": "activities",
                "schema": "schemas/activity.schema.json",
                "prefix": "av",
            }
        ]
        path = _make_manifest(tmp_workspace, activities=True, extra_entities=extra)
        with pytest.raises(ValueError, match="already defined"):
            UpjackApp.from_manifest(path, root=tmp_workspace)


# ------------------------------------------------------------------
# log_activity / get_activities
# ------------------------------------------------------------------


@pytest.fixture
def app_with_activities(tmp_workspace):
    """An UpjackApp with activities enabled (constructed directly)."""
    all_entities = [*ENTITIES, ACTIVITY_ENTITY_DEF]
    schema = get_activity_schema()
    return UpjackApp(
        namespace=NAMESPACE,
        entities=all_entities,
        root=tmp_workspace,
        schemas={"activity": schema},
    )


class TestLogActivity:
    def test_creates_activity_entity(self, app_with_activities):
        app = app_with_activities
        contact = app.create_entity("contact", {"first_name": "Alice"})
        activity = app.log_activity(contact["id"], "email_sent")

        assert activity["id"].startswith("act_")
        assert activity["type"] == "activity"
        assert activity["action"] == "email_sent"
        assert activity["detail"] == {}
        assert activity["created_by"] == "system"

    def test_creates_subject_relationship(self, app_with_activities):
        app = app_with_activities
        contact = app.create_entity("contact", {"first_name": "Alice"})
        activity = app.log_activity(contact["id"], "called")

        rels = activity["relationships"]
        assert len(rels) == 1
        assert rels[0]["rel"] == "subject"
        assert rels[0]["target"] == contact["id"]

    def test_with_detail_dict(self, app_with_activities):
        app = app_with_activities
        contact = app.create_entity("contact", {"first_name": "Bob"})
        detail = {"template": "intro_v2", "channel": "email"}
        activity = app.log_activity(contact["id"], "email_sent", detail=detail)

        assert activity["detail"] == detail

    def test_raises_when_activities_not_enabled(self, tmp_workspace):
        app = UpjackApp(
            namespace=NAMESPACE,
            entities=ENTITIES,
            root=tmp_workspace,
        )
        with pytest.raises(ValueError, match="Unknown entity type 'activity'"):
            app.log_activity("ct_00000000000000000000000000", "test")


class TestGetActivities:
    def test_returns_activities_for_subject(self, app_with_activities):
        app = app_with_activities
        contact = app.create_entity("contact", {"first_name": "Alice"})
        app.log_activity(contact["id"], "email_sent")
        app.log_activity(contact["id"], "called")

        activities = app.get_activities(contact["id"])
        assert len(activities) == 2
        actions = {a["action"] for a in activities}
        assert actions == {"email_sent", "called"}

    def test_filters_by_action(self, app_with_activities):
        app = app_with_activities
        contact = app.create_entity("contact", {"first_name": "Alice"})
        app.log_activity(contact["id"], "email_sent")
        app.log_activity(contact["id"], "called")
        app.log_activity(contact["id"], "email_sent")

        activities = app.get_activities(contact["id"], action="email_sent")
        assert len(activities) == 2
        assert all(a["action"] == "email_sent" for a in activities)

    def test_returns_empty_for_no_activities(self, app_with_activities):
        app = app_with_activities
        contact = app.create_entity("contact", {"first_name": "Alice"})
        activities = app.get_activities(contact["id"])
        assert activities == []

    def test_sorted_most_recent_first(self, app_with_activities):
        app = app_with_activities
        contact = app.create_entity("contact", {"first_name": "Alice"})

        a1 = app.log_activity(contact["id"], "first")
        # Ensure a measurable time gap
        time.sleep(0.01)
        a2 = app.log_activity(contact["id"], "second")

        activities = app.get_activities(contact["id"])
        assert len(activities) == 2
        # Most recent first
        assert activities[0]["id"] == a2["id"]
        assert activities[1]["id"] == a1["id"]

    def test_multiple_subjects_isolated(self, app_with_activities):
        app = app_with_activities
        alice = app.create_entity("contact", {"first_name": "Alice"})
        bob = app.create_entity("contact", {"first_name": "Bob"})

        app.log_activity(alice["id"], "emailed")
        app.log_activity(bob["id"], "called")

        alice_acts = app.get_activities(alice["id"])
        bob_acts = app.get_activities(bob["id"])
        assert len(alice_acts) == 1
        assert alice_acts[0]["action"] == "emailed"
        assert len(bob_acts) == 1
        assert bob_acts[0]["action"] == "called"

    def test_respects_limit(self, app_with_activities):
        app = app_with_activities
        contact = app.create_entity("contact", {"first_name": "Alice"})
        for i in range(5):
            app.log_activity(contact["id"], f"action_{i}")

        activities = app.get_activities(contact["id"], limit=3)
        assert len(activities) == 3

    def test_raises_when_activities_not_enabled(self, tmp_workspace):
        app = UpjackApp(
            namespace=NAMESPACE,
            entities=ENTITIES,
            root=tmp_workspace,
        )
        with pytest.raises(ValueError, match="Unknown entity type 'activity'"):
            app.get_activities("ct_00000000000000000000000000")


class TestActivityRelationshipIndex:
    def test_activity_indexed_via_reverse_index(self, app_with_activities, tmp_workspace):
        app = app_with_activities
        contact = app.create_entity("contact", {"first_name": "Alice"})
        activity = app.log_activity(contact["id"], "note_added")

        # Verify the index file contains the relationship
        index_file = tmp_workspace / NAMESPACE / "data" / "_index" / "relations.json"
        assert index_file.exists()
        index = json.loads(index_file.read_text())
        entries = index["reverse"].get(contact["id"], [])
        activity_entries = [e for e in entries if e["source"] == activity["id"]]
        assert len(activity_entries) == 1
        assert activity_entries[0]["rel"] == "subject"

    def test_activities_are_real_entities(self, app_with_activities):
        """Activities can be listed, retrieved, and deleted like any entity."""
        app = app_with_activities
        contact = app.create_entity("contact", {"first_name": "Alice"})
        activity = app.log_activity(contact["id"], "test_action")

        # Get by ID
        fetched = app.get_entity("activity", activity["id"])
        assert fetched["action"] == "test_action"

        # List
        all_activities = app.list_entities("activity")
        assert len(all_activities) == 1

        # Soft delete
        deleted = app.delete_entity("activity", activity["id"])
        assert deleted["status"] == "deleted"
