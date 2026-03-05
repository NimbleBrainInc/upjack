"""Tests for upjack.app module."""

import json

import pytest

from upjack.app import UpjackApp
from upjack.ids import validate_id

NAMESPACE = "apps/crm"
ENTITIES = [
    {
        "name": "contact",
        "plural": "contacts",
        "schema": "schemas/contact.schema.json",
        "prefix": "ct",
    },
    {
        "name": "company",
        "plural": "companies",
        "schema": "schemas/company.schema.json",
        "prefix": "co",
    },
]


@pytest.fixture
def app(tmp_workspace):
    return UpjackApp(
        namespace=NAMESPACE,
        entities=ENTITIES,
        root=tmp_workspace,
    )


class TestUpjackApp:
    def test_create_entity(self, app):
        result = app.create_entity("contact", {"first_name": "Sarah", "last_name": "Chen"})
        assert validate_id(result["id"])
        assert result["id"].startswith("ct_")
        assert result["type"] == "contact"
        assert result["first_name"] == "Sarah"

    def test_get_entity(self, app):
        created = app.create_entity("contact", {"first_name": "Sarah"})
        result = app.get_entity("contact", created["id"])
        assert result["id"] == created["id"]
        assert result["first_name"] == "Sarah"

    def test_update_entity(self, app):
        created = app.create_entity("contact", {"first_name": "Sarah"})
        updated = app.update_entity("contact", created["id"], {"last_name": "Chen"})
        assert updated["first_name"] == "Sarah"
        assert updated["last_name"] == "Chen"

    def test_list_entities(self, app):
        app.create_entity("contact", {"first_name": "Alice"})
        app.create_entity("contact", {"first_name": "Bob"})
        results = app.list_entities("contact")
        assert len(results) == 2

    def test_delete_entity(self, app):
        created = app.create_entity("contact", {"first_name": "Sarah"})
        result = app.delete_entity("contact", created["id"])
        assert result["status"] == "deleted"

    def test_multiple_entity_types(self, app):
        contact = app.create_entity("contact", {"first_name": "Sarah"})
        company = app.create_entity("company", {"name": "Acme Corp"})
        assert contact["id"].startswith("ct_")
        assert company["id"].startswith("co_")

    def test_unknown_entity_type_raises(self, app):
        with pytest.raises(ValueError, match="Unknown entity type"):
            app.create_entity("nonexistent", {"name": "test"})

    def test_default_plural(self, tmp_workspace):
        """Entity without explicit plural gets name + 's'."""
        app = UpjackApp(
            namespace=NAMESPACE,
            entities=[{"name": "deal", "schema": "schemas/deal.schema.json", "prefix": "dl"}],
            root=tmp_workspace,
        )
        result = app.create_entity("deal", {"title": "Big Deal"})
        assert result["type"] == "deal"
        # Should be stored under 'deals/' (default plural)
        path = tmp_workspace / NAMESPACE / "data" / "deals" / f"{result['id']}.json"
        assert path.exists()


class TestFromManifest:
    def test_loads_from_manifest(self, tmp_workspace):
        manifest = {
            "manifest_version": "0.4",
            "name": "@nimblebraininc/crm",
            "version": "1.0.0",
            "_meta": {
                "ai.nimblebrain/upjack": {
                    "upjack_version": "0.1",
                    "namespace": "apps/crm",
                    "entities": [
                        {
                            "name": "contact",
                            "plural": "contacts",
                            "schema": "schemas/contact.schema.json",
                            "prefix": "ct",
                        }
                    ],
                }
            },
        }

        manifest_path = tmp_workspace / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        app = UpjackApp.from_manifest(manifest_path, root=tmp_workspace)
        assert app.namespace == "apps/crm"

        result = app.create_entity("contact", {"first_name": "Sarah"})
        assert result["id"].startswith("ct_")

    def test_loads_schemas_from_disk_and_validates(self, tmp_workspace):
        """When schema files exist on disk, from_manifest loads them and
        uses them for validation on create."""
        schemas_dir = tmp_workspace / "schemas"
        schemas_dir.mkdir()
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "value": {"type": "integer", "minimum": 0},
            },
            "required": ["name"],
        }
        (schemas_dir / "widget.schema.json").write_text(json.dumps(schema))

        manifest = {
            "manifest_version": "0.4",
            "name": "test",
            "version": "1.0.0",
            "_meta": {
                "ai.nimblebrain/upjack": {
                    "upjack_version": "0.1",
                    "namespace": "test",
                    "entities": [
                        {
                            "name": "widget",
                            "plural": "widgets",
                            "prefix": "wg",
                            "schema": "schemas/widget.schema.json",
                        }
                    ],
                }
            },
        }
        manifest_path = tmp_workspace / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        app = UpjackApp.from_manifest(manifest_path, root=tmp_workspace)

        # Schema should be loaded
        assert "widget" in app._schemas

        # Valid creation works
        widget = app.create_entity("widget", {"name": "Gizmo", "value": 42})
        assert widget["name"] == "Gizmo"

        # Invalid creation fails — missing required "name"
        from jsonschema import ValidationError

        with pytest.raises(ValidationError):
            app.create_entity("widget", {"value": 100})

        # Invalid creation fails — negative value
        with pytest.raises(ValidationError):
            app.create_entity("widget", {"name": "Bad", "value": -5})


class TestAppSchemaEvolution:
    """Test that UpjackApp hydrates defaults on read paths when schemas are loaded."""

    SCHEMA_V1 = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "first_name": {"type": "string"},
            "last_name": {"type": "string"},
        },
        "required": ["first_name"],
        "additionalProperties": True,
    }

    SCHEMA_V2 = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "first_name": {"type": "string"},
            "last_name": {"type": "string"},
            "score": {"type": "integer", "default": 0},
        },
        "required": ["first_name", "score"],
        "additionalProperties": True,
    }

    def _make_app(self, tmp_workspace, schema):
        return UpjackApp(
            namespace=NAMESPACE,
            entities=[
                {
                    "name": "contact",
                    "plural": "contacts",
                    "schema": "schemas/contact.schema.json",
                    "prefix": "ct",
                }
            ],
            root=tmp_workspace,
            schemas={"contact": schema} if schema else None,
        )

    def test_get_entity_hydrates_via_app(self, tmp_workspace):
        """Create with v1 app, read with v2 app — default filled."""
        app_v1 = self._make_app(tmp_workspace, self.SCHEMA_V1)
        created = app_v1.create_entity("contact", {"first_name": "Sarah", "last_name": "Chen"})
        assert "score" not in created

        app_v2 = self._make_app(tmp_workspace, self.SCHEMA_V2)
        result = app_v2.get_entity("contact", created["id"])
        assert result["score"] == 0
        assert result["first_name"] == "Sarah"

    def test_list_entities_hydrates_via_app(self, tmp_workspace):
        app_v1 = self._make_app(tmp_workspace, self.SCHEMA_V1)
        app_v1.create_entity("contact", {"first_name": "Alice"})
        app_v1.create_entity("contact", {"first_name": "Bob"})

        app_v2 = self._make_app(tmp_workspace, self.SCHEMA_V2)
        results = app_v2.list_entities("contact")
        assert len(results) == 2
        assert all(r["score"] == 0 for r in results)

    def test_update_entity_hydrates_via_app(self, tmp_workspace):
        """Update through v2 app succeeds even though entity was created under v1."""
        app_v1 = self._make_app(tmp_workspace, self.SCHEMA_V1)
        created = app_v1.create_entity("contact", {"first_name": "Sarah", "last_name": "Chen"})

        app_v2 = self._make_app(tmp_workspace, self.SCHEMA_V2)
        updated = app_v2.update_entity("contact", created["id"], {"last_name": "Johnson"})
        assert updated["last_name"] == "Johnson"
        assert updated["score"] == 0

    def test_search_entities_hydrates_via_app(self, tmp_workspace):
        app_v1 = self._make_app(tmp_workspace, self.SCHEMA_V1)
        app_v1.create_entity("contact", {"first_name": "Sarah"})

        app_v2 = self._make_app(tmp_workspace, self.SCHEMA_V2)
        results = app_v2.search_entities("contact", query="Sarah")
        assert len(results) == 1
        assert results[0]["score"] == 0


class TestFromManifestMalformed:
    """Verify that from_manifest produces clear errors for incomplete manifests."""

    def test_missing_meta_raises_value_error(self, tmp_workspace):
        """A manifest with no _meta key raises ValueError about missing extension."""
        manifest = {
            "manifest_version": "0.4",
            "name": "test",
            "version": "1.0.0",
        }
        manifest_path = tmp_workspace / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        with pytest.raises(ValueError, match="missing upjack extension"):
            UpjackApp.from_manifest(manifest_path)

    def test_missing_namespace_raises_value_error(self, tmp_workspace):
        """An upjack extension missing 'namespace' raises ValueError."""
        manifest = {
            "manifest_version": "0.4",
            "name": "test",
            "version": "1.0.0",
            "_meta": {
                "ai.nimblebrain/upjack": {
                    "upjack_version": "0.1",
                    "entities": [],
                }
            },
        }
        manifest_path = tmp_workspace / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        with pytest.raises(ValueError, match="missing required field 'namespace'"):
            UpjackApp.from_manifest(manifest_path)

    def test_missing_entities_raises_value_error(self, tmp_workspace):
        """An upjack extension missing 'entities' raises ValueError."""
        manifest = {
            "manifest_version": "0.4",
            "name": "test",
            "version": "1.0.0",
            "_meta": {
                "ai.nimblebrain/upjack": {
                    "upjack_version": "0.1",
                    "namespace": "apps/crm",
                }
            },
        }
        manifest_path = tmp_workspace / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        with pytest.raises(ValueError, match="missing required field 'entities'"):
            UpjackApp.from_manifest(manifest_path)

    def test_wrong_meta_vendor_key_raises_value_error(self, tmp_workspace):
        """A manifest with _meta but wrong vendor key raises ValueError."""
        manifest = {
            "manifest_version": "0.4",
            "name": "test",
            "version": "1.0.0",
            "_meta": {
                "some.other/extension": {"data": True},
            },
        }
        manifest_path = tmp_workspace / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        with pytest.raises(ValueError, match="missing upjack extension"):
            UpjackApp.from_manifest(manifest_path)


class TestReloadSchema:
    def test_reload_picks_up_file_change(self, tmp_workspace):
        schemas_dir = tmp_workspace / "schemas"
        schemas_dir.mkdir()

        schema_v1 = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        (schemas_dir / "widget.schema.json").write_text(json.dumps(schema_v1))

        app = UpjackApp(
            namespace="test",
            entities=[
                {
                    "name": "widget",
                    "plural": "widgets",
                    "prefix": "wg",
                    "schema": "schemas/widget.schema.json",
                }
            ],
            root=tmp_workspace,
            schemas={"widget": schema_v1},
            manifest_dir=tmp_workspace,
        )

        schema_v2 = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "score": {"type": "integer", "default": 0},
            },
            "required": ["name", "score"],
        }
        (schemas_dir / "widget.schema.json").write_text(json.dumps(schema_v2))

        app.reload_schema("widget")
        assert "score" in app._schemas["widget"]["properties"]

    def test_unknown_entity_raises(self, tmp_workspace):
        app = UpjackApp(
            namespace="test",
            entities=[
                {
                    "name": "widget",
                    "plural": "widgets",
                    "prefix": "wg",
                    "schema": "schemas/widget.schema.json",
                }
            ],
            root=tmp_workspace,
            manifest_dir=tmp_workspace,
        )
        with pytest.raises(ValueError, match="Unknown entity type"):
            app.reload_schema("nonexistent")

    def test_no_manifest_dir_raises(self, tmp_workspace):
        app = UpjackApp(
            namespace="test",
            entities=[
                {
                    "name": "widget",
                    "plural": "widgets",
                    "prefix": "wg",
                    "schema": "schemas/widget.schema.json",
                }
            ],
            root=tmp_workspace,
        )
        with pytest.raises(ValueError, match="manifest_dir"):
            app.reload_schema("widget")
