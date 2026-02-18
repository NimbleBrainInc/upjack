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
