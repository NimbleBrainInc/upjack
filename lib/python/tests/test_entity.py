"""Tests for upjack.entity module."""

import json

import pytest
from jsonschema import ValidationError

from upjack.entity import (
    Entity,
    create_entity,
    delete_entity,
    get_entity,
    list_entities,
    update_entity,
)
from upjack.ids import validate_id

NAMESPACE = "apps/crm"


class TestEntity:
    def test_to_dict(self):
        entity = Entity(
            id="ct_01JKXM9V3QWERTY123456ABCDF",
            type="contact",
            version=1,
            created_at="2026-02-17T12:00:00Z",
            updated_at="2026-02-17T12:00:00Z",
            data={"first_name": "Sarah", "last_name": "Chen"},
        )
        d = entity.to_dict()
        assert d["id"] == "ct_01JKXM9V3QWERTY123456ABCDF"
        assert d["first_name"] == "Sarah"
        assert d["status"] == "active"

    def test_from_dict(self):
        raw = {
            "id": "ct_01JKXM9V3QWERTY123456ABCDF",
            "type": "contact",
            "version": 1,
            "created_at": "2026-02-17T12:00:00Z",
            "updated_at": "2026-02-17T12:00:00Z",
            "first_name": "Sarah",
        }
        entity = Entity.from_dict(raw)
        assert entity.id == "ct_01JKXM9V3QWERTY123456ABCDF"
        assert entity.data == {"first_name": "Sarah"}

    def test_roundtrip(self):
        raw = {
            "id": "ct_01JKXM9V3QWERTY123456ABCDF",
            "type": "contact",
            "version": 1,
            "created_at": "2026-02-17T12:00:00Z",
            "updated_at": "2026-02-17T12:00:00Z",
            "status": "active",
            "created_by": "agent",
            "tags": ["hot-lead"],
            "relationships": [],
            "first_name": "Sarah",
        }
        entity = Entity.from_dict(raw)
        result = entity.to_dict()
        assert result["id"] == raw["id"]
        assert result["first_name"] == "Sarah"
        assert result["tags"] == ["hot-lead"]


class TestCreateEntity:
    def test_creates_entity_file(self, tmp_workspace):
        result = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Sarah", "last_name": "Chen"},
        )

        assert validate_id(result["id"])
        assert result["id"].startswith("ct_")
        assert result["type"] == "contact"
        assert result["version"] == 1
        assert result["status"] == "active"
        assert result["first_name"] == "Sarah"

        # File should exist on disk
        path = tmp_workspace / NAMESPACE / "data" / "contacts" / f"{result['id']}.json"
        assert path.exists()

    def test_validates_against_schema(self, tmp_workspace, sample_schema):
        result = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Sarah", "last_name": "Chen"},
            schema=sample_schema,
        )
        assert result["first_name"] == "Sarah"


class TestCreateEntityIdHandling:
    """Test ID resolution in create_entity — provided vs generated."""

    def test_respects_valid_provided_id(self, tmp_workspace):
        """A valid ID matching the prefix should be used as-is."""
        from upjack.ids import generate_id

        provided = generate_id("ct")
        result = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"id": provided, "first_name": "Alice", "last_name": "Chen"},
        )
        assert result["id"] == provided
        # File on disk should match the provided ID
        path = tmp_workspace / NAMESPACE / "data" / "contacts" / f"{provided}.json"
        assert path.exists()

    def test_provided_id_retrievable_by_get(self, tmp_workspace):
        """Entity created with a provided ID must be retrievable by that ID."""
        from upjack.ids import generate_id

        provided = generate_id("ct")
        create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"id": provided, "first_name": "Bob", "last_name": "Smith"},
        )
        fetched = get_entity(tmp_workspace, NAMESPACE, "contacts", provided)
        assert fetched["id"] == provided
        assert fetched["first_name"] == "Bob"

    def test_ignores_id_with_wrong_prefix(self, tmp_workspace):
        """An ID with the wrong prefix should be ignored — new ULID generated."""
        result = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"id": "dl_01KMRSCQ0QTWTXDG4EN1VP1GW4", "first_name": "Eve", "last_name": "X"},
        )
        assert result["id"].startswith("ct_")
        assert result["id"] != "dl_01KMRSCQ0QTWTXDG4EN1VP1GW4"

    def test_ignores_invalid_id_format(self, tmp_workspace):
        """A malformed ID should be ignored — new ULID generated."""
        result = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"id": "not-a-valid-id", "first_name": "Mal", "last_name": "Formed"},
        )
        assert result["id"].startswith("ct_")
        assert validate_id(result["id"])

    def test_rejects_duplicate_id(self, tmp_workspace):
        """Creating two entities with the same ID should raise ValueError."""
        from upjack.ids import generate_id

        provided = generate_id("ct")
        create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"id": provided, "first_name": "First", "last_name": "One"},
        )
        with pytest.raises(ValueError, match="already exists"):
            create_entity(
                root=tmp_workspace,
                namespace=NAMESPACE,
                entity_type="contact",
                plural="contacts",
                prefix="ct",
                data={"id": provided, "first_name": "Second", "last_name": "One"},
            )

    def test_provided_type_does_not_override(self, tmp_workspace):
        """A 'type' in data should not leak into the record — entity_type param wins."""
        result = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"type": "wrong_type", "first_name": "Type", "last_name": "Test"},
        )
        assert result["type"] == "contact"


class TestUpdateEntity:
    def test_updates_entity(self, tmp_workspace):
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Sarah", "last_name": "Chen"},
        )

        updated = update_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
            data={"last_name": "Johnson"},
        )

        assert updated["last_name"] == "Johnson"
        assert updated["first_name"] == "Sarah"  # Merged
        assert updated["updated_at"] != created["updated_at"]

    def test_replace_mode(self, tmp_workspace):
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Sarah", "last_name": "Chen"},
        )

        updated = update_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
            data={"first_name": "Jane", "last_name": "Doe"},
            merge=False,
        )

        assert updated["first_name"] == "Jane"
        assert updated["id"] == created["id"]  # Preserved

    def test_raises_on_missing(self, tmp_workspace):
        with pytest.raises(FileNotFoundError):
            update_entity(
                root=tmp_workspace,
                namespace=NAMESPACE,
                plural="contacts",
                entity_id="ct_01JKXM9V3QWERTY123456ABCDF",
                data={"name": "test"},
            )


class TestGetEntity:
    def test_gets_entity(self, tmp_workspace):
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Sarah"},
        )

        result = get_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
        )

        assert result["id"] == created["id"]
        assert result["first_name"] == "Sarah"

    def test_raises_on_missing(self, tmp_workspace):
        with pytest.raises(FileNotFoundError):
            get_entity(
                root=tmp_workspace,
                namespace=NAMESPACE,
                plural="contacts",
                entity_id="ct_01JKXM9V3QWERTY123456ABCDF",
            )


class TestListEntities:
    def test_lists_entities(self, tmp_workspace):
        for name in ["Alice", "Bob", "Charlie"]:
            create_entity(
                root=tmp_workspace,
                namespace=NAMESPACE,
                entity_type="contact",
                plural="contacts",
                prefix="ct",
                data={"first_name": name},
            )

        results = list_entities(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
        )

        assert len(results) == 3

    def test_filters_by_status(self, tmp_workspace):
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Alice"},
        )
        delete_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
        )
        create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Bob"},
        )

        active = list_entities(
            root=tmp_workspace, namespace=NAMESPACE, plural="contacts", status="active"
        )
        deleted = list_entities(
            root=tmp_workspace, namespace=NAMESPACE, plural="contacts", status="deleted"
        )

        assert len(active) == 1
        assert len(deleted) == 1

    def test_respects_limit(self, tmp_workspace):
        for i in range(10):
            create_entity(
                root=tmp_workspace,
                namespace=NAMESPACE,
                entity_type="contact",
                plural="contacts",
                prefix="ct",
                data={"first_name": f"Person{i}"},
            )

        results = list_entities(root=tmp_workspace, namespace=NAMESPACE, plural="contacts", limit=3)
        assert len(results) == 3

    def test_empty_directory(self, tmp_workspace):
        results = list_entities(root=tmp_workspace, namespace=NAMESPACE, plural="contacts")
        assert results == []


class TestDeleteEntity:
    def test_soft_delete(self, tmp_workspace):
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Sarah"},
        )

        result = delete_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
        )

        assert result["status"] == "deleted"

        # File still exists
        path = tmp_workspace / NAMESPACE / "data" / "contacts" / f"{created['id']}.json"
        assert path.exists()

    def test_hard_delete(self, tmp_workspace):
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Sarah"},
        )

        delete_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
            hard=True,
        )

        path = tmp_workspace / NAMESPACE / "data" / "contacts" / f"{created['id']}.json"
        assert not path.exists()

    def test_raises_on_missing(self, tmp_workspace):
        with pytest.raises(FileNotFoundError):
            delete_entity(
                root=tmp_workspace,
                namespace=NAMESPACE,
                plural="contacts",
                entity_id="ct_01JKXM9V3QWERTY123456ABCDF",
            )


class TestEntitySource:
    """Test Entity source field handling (to_dict, from_dict, create, roundtrip)."""

    def test_to_dict_includes_source_when_set(self):
        entity = Entity(
            id="ct_01JKXM9V3QWERTY123456ABCDF",
            type="contact",
            version=1,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            source={"origin": "import", "ref": "legacy-123"},
        )
        d = entity.to_dict()
        assert d["source"] == {"origin": "import", "ref": "legacy-123"}

    def test_to_dict_excludes_source_when_none(self):
        entity = Entity(
            id="ct_01JKXM9V3QWERTY123456ABCDF",
            type="contact",
            version=1,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        d = entity.to_dict()
        assert "source" not in d

    def test_from_dict_parses_source(self):
        raw = {
            "id": "ct_01JKXM9V3QWERTY123456ABCDF",
            "type": "contact",
            "version": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "source": {"origin": "api", "url": "https://example.com"},
        }
        entity = Entity.from_dict(raw)
        assert entity.source == {"origin": "api", "url": "https://example.com"}
        # source should NOT end up in data dict
        assert "source" not in entity.data

    def test_create_entity_with_source(self, tmp_workspace):
        result = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={
                "first_name": "Alice",
                "source": {"origin": "import", "ref": "legacy-123"},
            },
        )
        assert result["source"] == {"origin": "import", "ref": "legacy-123"}

        # Verify persisted on disk
        fetched = get_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=result["id"],
        )
        assert fetched["source"] == {"origin": "import", "ref": "legacy-123"}

    def test_source_roundtrip_through_from_dict(self):
        """Source field survives to_dict → from_dict → to_dict."""
        original = Entity(
            id="ct_01JKXM9V3QWERTY123456ABCDF",
            type="contact",
            version=1,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            source={"origin": "csv", "ref": "batch-42"},
            data={"first_name": "Test"},
        )
        d = original.to_dict()
        restored = Entity.from_dict(d)
        assert restored.source == original.source
        assert restored.data == original.data


class TestUpdateEntityImmutableFields:
    """Verify that immutable fields (id, type, version, created_at, created_by) cannot be overwritten."""

    def test_id_cannot_be_changed(self, tmp_workspace):
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Sarah"},
        )
        updated = update_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
            data={"id": "ct_FAKE00000000000000000000000", "first_name": "Jane"},
        )
        assert updated["id"] == created["id"]
        assert updated["first_name"] == "Jane"

    def test_type_cannot_be_changed(self, tmp_workspace):
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Sarah"},
        )
        updated = update_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
            data={"type": "hacked"},
        )
        assert updated["type"] == "contact"

    def test_created_at_cannot_be_changed(self, tmp_workspace):
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Sarah"},
        )
        updated = update_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
            data={"created_at": "1999-01-01T00:00:00Z"},
        )
        assert updated["created_at"] == created["created_at"]

    def test_version_cannot_be_changed(self, tmp_workspace):
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Sarah"},
        )
        updated = update_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
            data={"version": 999},
        )
        assert updated["version"] == created["version"]

    def test_created_by_cannot_be_changed(self, tmp_workspace):
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Sarah"},
        )
        updated = update_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
            data={"created_by": "hacked"},
        )
        assert updated["created_by"] == created["created_by"]

    def test_immutable_fields_stripped_in_replace_mode(self, tmp_workspace):
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Sarah"},
        )
        updated = update_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
            data={
                "id": "ct_FAKE00000000000000000000000",
                "type": "hacked",
                "created_at": "1999-01-01T00:00:00Z",
                "first_name": "Jane",
            },
            merge=False,
        )
        assert updated["id"] == created["id"]
        assert updated["type"] == created["type"]
        assert updated["created_at"] == created["created_at"]
        assert updated["first_name"] == "Jane"


class TestUpdateEntityWithSchema:
    """Test schema validation during update_entity."""

    def test_valid_update_with_schema(self, tmp_workspace, sample_schema):
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Alice", "last_name": "Chen"},
            schema=sample_schema,
        )
        # Valid update — changes first_name (still a string)
        updated = update_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
            data={"first_name": "Alicia"},
            schema=sample_schema,
        )
        assert updated["first_name"] == "Alicia"

    def test_invalid_update_rejected_by_schema(self, tmp_workspace, sample_schema):
        """Setting a string field to an integer should fail validation."""
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Alice", "last_name": "Chen"},
            schema=sample_schema,
        )
        with pytest.raises(ValidationError):
            update_entity(
                root=tmp_workspace,
                namespace=NAMESPACE,
                plural="contacts",
                entity_id=created["id"],
                data={"first_name": 12345},
                schema=sample_schema,
            )


class TestCorruptJsonResilience:
    """Verify that corrupt JSON files are handled gracefully."""

    def test_list_entities_skips_corrupt_json(self, tmp_workspace):
        """list_entities skips corrupt files and returns valid entities."""
        create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Valid"},
        )

        from upjack.paths import entity_dir

        corrupt_path = entity_dir(tmp_workspace, NAMESPACE, "contacts") / "corrupt.json"
        corrupt_path.write_text("{not valid json at all")

        results = list_entities(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
        )
        assert len(results) == 1
        assert results[0]["first_name"] == "Valid"

    def test_list_entities_returns_empty_when_all_corrupt(self, tmp_workspace):
        """list_entities returns [] when every file is corrupt."""
        from upjack.paths import entity_dir

        directory = entity_dir(tmp_workspace, NAMESPACE, "contacts")
        directory.mkdir(parents=True)
        (directory / "bad1.json").write_text("not json")
        (directory / "bad2.json").write_text("{broken")

        results = list_entities(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
        )
        assert results == []

    def test_get_entity_still_raises_on_corrupt_file(self, tmp_workspace):
        """get_entity raises JSONDecodeError for a specific corrupt entity.

        Unlike list (which can skip), get targets a single file and should
        surface the error so the caller knows the data is corrupt.
        """
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Valid"},
        )

        from upjack.paths import entity_path

        path = entity_path(tmp_workspace, NAMESPACE, "contacts", created["id"])
        path.write_text("<<<not json>>>")

        with pytest.raises(json.JSONDecodeError):
            get_entity(
                root=tmp_workspace,
                namespace=NAMESPACE,
                plural="contacts",
                entity_id=created["id"],
            )


class TestSchemaEvolution:
    """Test that adding a field with a default doesn't break old entities."""

    SCHEMA_V1 = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "type": {"type": "string"},
            "version": {"type": "integer"},
            "created_at": {"type": "string"},
            "updated_at": {"type": "string"},
            "first_name": {"type": "string"},
            "last_name": {"type": "string"},
        },
        "required": [
            "id",
            "type",
            "version",
            "created_at",
            "updated_at",
            "first_name",
            "last_name",
        ],
        "additionalProperties": True,
    }

    SCHEMA_V2 = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "type": {"type": "string"},
            "version": {"type": "integer"},
            "created_at": {"type": "string"},
            "updated_at": {"type": "string"},
            "first_name": {"type": "string"},
            "last_name": {"type": "string"},
            "score": {"type": "integer", "default": 0},
        },
        "required": [
            "id",
            "type",
            "version",
            "created_at",
            "updated_at",
            "first_name",
            "last_name",
            "score",
        ],
        "additionalProperties": True,
    }

    def test_get_entity_hydrates_missing_field(self, tmp_workspace):
        """Entity created under v1 schema can be read with v2 schema."""
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Sarah", "last_name": "Chen"},
            schema=self.SCHEMA_V1,
        )
        assert "score" not in created

        result = get_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
            schema=self.SCHEMA_V2,
        )
        assert result["score"] == 0
        assert result["first_name"] == "Sarah"

    def test_list_entities_hydrates_missing_field(self, tmp_workspace):
        """list_entities fills defaults for old entities."""
        create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Sarah", "last_name": "Chen"},
            schema=self.SCHEMA_V1,
        )

        results = list_entities(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            schema=self.SCHEMA_V2,
        )
        assert len(results) == 1
        assert results[0]["score"] == 0

    def test_update_old_entity_with_new_schema(self, tmp_workspace):
        """Updating a v1 entity against v2 schema succeeds (hydration fills default)."""
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Sarah", "last_name": "Chen"},
            schema=self.SCHEMA_V1,
        )

        # This would fail without hydration because the merged entity
        # is missing the now-required "score" field.
        updated = update_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
            data={"first_name": "Sarah J."},
            schema=self.SCHEMA_V2,
        )
        assert updated["first_name"] == "Sarah J."
        assert updated["score"] == 0

    def test_allof_ref_schema_hydration(self, tmp_workspace):
        """Real-world schema using allOf $ref to base entity schema."""
        SCHEMA_V1 = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "allOf": [{"$ref": "https://upjack.dev/schemas/v1/upjack-entity.schema.json"}],
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
        }
        SCHEMA_V2 = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "allOf": [{"$ref": "https://upjack.dev/schemas/v1/upjack-entity.schema.json"}],
            "properties": {
                "name": {"type": "string"},
                "priority": {"type": "string", "default": "medium"},
            },
            "required": ["name", "priority"],
        }

        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="campaign",
            plural="campaigns",
            prefix="cp",
            data={"name": "Q1 Push"},
            schema=SCHEMA_V1,
        )
        assert "priority" not in created

        result = get_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="campaigns",
            entity_id=created["id"],
            schema=SCHEMA_V2,
        )
        assert result["priority"] == "medium"
        # Base schema defaults also applied
        assert result["tags"] == []
        assert result["relationships"] == []

        # Update succeeds against v2 with new required field
        updated = update_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="campaigns",
            entity_id=created["id"],
            data={"name": "Q1 Push (revised)"},
            schema=SCHEMA_V2,
        )
        assert updated["priority"] == "medium"
        assert updated["name"] == "Q1 Push (revised)"

    def test_update_persists_hydrated_default(self, tmp_workspace):
        """After update with hydration, the default is written to disk."""
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Sarah", "last_name": "Chen"},
        )

        update_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
            data={"last_name": "Johnson"},
            schema=self.SCHEMA_V2,
        )

        # Read raw (no schema) — default should now be persisted
        raw = get_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
        )
        assert raw["score"] == 0


class TestRelationshipCallbacks:
    """Test the on_relationships_changed callback on CRUD operations."""

    def test_create_with_relationships_fires_callback(self, tmp_workspace):
        calls = []
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={
                "first_name": "Alice",
                "relationships": [{"rel": "works_at", "target": "co_01ABC"}],
            },
            on_relationships_changed=lambda eid, old, new: calls.append((eid, old, new)),
        )
        assert len(calls) == 1
        assert calls[0][0] == created["id"]
        assert calls[0][1] == []
        assert calls[0][2] == [{"rel": "works_at", "target": "co_01ABC"}]

    def test_create_without_relationships_no_callback(self, tmp_workspace):
        calls = []
        create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Alice"},
            on_relationships_changed=lambda eid, old, new: calls.append((eid, old, new)),
        )
        assert len(calls) == 0

    def test_create_without_callback_no_error(self, tmp_workspace):
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={
                "first_name": "Alice",
                "relationships": [{"rel": "works_at", "target": "co_01ABC"}],
            },
        )
        assert created["relationships"] == [{"rel": "works_at", "target": "co_01ABC"}]

    def test_update_changed_relationships_fires_callback(self, tmp_workspace):
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={
                "first_name": "Alice",
                "relationships": [{"rel": "works_at", "target": "co_01OLD"}],
            },
        )

        calls = []
        update_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
            data={"relationships": [{"rel": "works_at", "target": "co_01NEW"}]},
            on_relationships_changed=lambda eid, old, new: calls.append((eid, old, new)),
        )
        assert len(calls) == 1
        assert calls[0][0] == created["id"]
        assert calls[0][1] == [{"rel": "works_at", "target": "co_01OLD"}]
        assert calls[0][2] == [{"rel": "works_at", "target": "co_01NEW"}]

    def test_update_unchanged_relationships_no_callback(self, tmp_workspace):
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={
                "first_name": "Alice",
                "relationships": [{"rel": "works_at", "target": "co_01ABC"}],
            },
        )

        calls = []
        update_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
            data={"first_name": "Alice Updated"},
            on_relationships_changed=lambda eid, old, new: calls.append((eid, old, new)),
        )
        assert len(calls) == 0

    def test_update_without_callback_no_error(self, tmp_workspace):
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={"first_name": "Alice"},
        )
        updated = update_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
            data={"relationships": [{"rel": "works_at", "target": "co_01ABC"}]},
        )
        assert updated["relationships"] == [{"rel": "works_at", "target": "co_01ABC"}]

    def test_hard_delete_fires_callback(self, tmp_workspace):
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={
                "first_name": "Alice",
                "relationships": [{"rel": "works_at", "target": "co_01ABC"}],
            },
        )

        calls = []
        delete_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
            hard=True,
            on_relationships_changed=lambda eid, old, new: calls.append((eid, old, new)),
        )
        assert len(calls) == 1
        assert calls[0][0] == created["id"]
        assert calls[0][1] == [{"rel": "works_at", "target": "co_01ABC"}]
        assert calls[0][2] == []

    def test_soft_delete_no_callback(self, tmp_workspace):
        created = create_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            entity_type="contact",
            plural="contacts",
            prefix="ct",
            data={
                "first_name": "Alice",
                "relationships": [{"rel": "works_at", "target": "co_01ABC"}],
            },
        )

        calls = []
        delete_entity(
            root=tmp_workspace,
            namespace=NAMESPACE,
            plural="contacts",
            entity_id=created["id"],
            hard=False,
            on_relationships_changed=lambda eid, old, new: calls.append((eid, old, new)),
        )
        assert len(calls) == 0
