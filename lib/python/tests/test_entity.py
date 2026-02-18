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
