"""Tests for upjack.schema module."""

import json
import logging

import jsonschema
import pytest

from upjack.schema import (
    hydrate_defaults,
    load_schema,
    resolve_entity_schema,
    validate_entity,
    validate_schema_change,
)


class TestLoadSchema:
    def test_loads_valid_schema(self, tmp_path):
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        schema_path = tmp_path / "test.schema.json"
        schema_path.write_text(json.dumps(schema))

        result = load_schema(schema_path)
        assert result == schema

    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_schema(tmp_path / "missing.schema.json")


class TestValidateEntity:
    def test_valid_entity(self, sample_schema):
        data = {
            "id": "ct_01JKXM9V3QWERTY123456ABCDF",
            "type": "contact",
            "version": 1,
            "created_at": "2026-02-17T12:00:00Z",
            "updated_at": "2026-02-17T12:00:00Z",
            "first_name": "Sarah",
            "last_name": "Chen",
        }
        validate_entity(data, sample_schema)

    def test_rejects_missing_required(self, sample_schema):
        data = {
            "id": "ct_01JKXM9V3QWERTY123456ABCDF",
            "type": "contact",
        }
        with pytest.raises(jsonschema.ValidationError):
            validate_entity(data, sample_schema)

    def test_allows_additional_properties(self, sample_schema):
        data = {
            "id": "ct_01JKXM9V3QWERTY123456ABCDF",
            "type": "contact",
            "version": 1,
            "created_at": "2026-02-17T12:00:00Z",
            "updated_at": "2026-02-17T12:00:00Z",
            "first_name": "Sarah",
            "last_name": "Chen",
            "custom_field": "extra data",
        }
        validate_entity(data, sample_schema)


class TestHydrateDefaults:
    def test_fills_missing_field_with_default(self):
        schema = {
            "properties": {
                "name": {"type": "string"},
                "priority": {"type": "string", "default": "medium"},
            }
        }
        data = {"name": "test"}
        result = hydrate_defaults(data, schema)
        assert result["priority"] == "medium"
        assert result["name"] == "test"

    def test_does_not_overwrite_existing_field(self):
        schema = {
            "properties": {
                "priority": {"type": "string", "default": "medium"},
            }
        }
        data = {"priority": "high"}
        result = hydrate_defaults(data, schema)
        assert result["priority"] == "high"

    def test_does_not_mutate_input(self):
        schema = {
            "properties": {
                "priority": {"type": "string", "default": "medium"},
            }
        }
        data = {"name": "test"}
        hydrate_defaults(data, schema)
        assert "priority" not in data

    def test_handles_allof_with_ref(self):
        """Schemas using allOf with $ref to base entity schema."""
        schema = {
            "allOf": [{"$ref": "https://upjack.dev/schemas/v1/upjack-entity.schema.json"}],
            "properties": {
                "score": {"type": "integer", "default": 0},
            },
        }
        data = {"id": "ct_01JKXM9V3QWERTY123456ABCDF", "type": "contact"}
        result = hydrate_defaults(data, schema)
        # App-level default applied
        assert result["score"] == 0
        # Base schema defaults applied (tags, relationships, etc.)
        assert result["tags"] == []
        assert result["relationships"] == []

    def test_no_defaults_returns_copy(self):
        schema = {
            "properties": {
                "name": {"type": "string"},
            }
        }
        data = {"name": "test"}
        result = hydrate_defaults(data, schema)
        assert result == data
        assert result is not data

    def test_object_default(self):
        schema = {
            "properties": {
                "config": {
                    "type": "object",
                    "default": {"retries": 3},
                },
            }
        }
        data = {}
        result = hydrate_defaults(data, schema)
        assert result["config"] == {"retries": 3}

    def test_array_default(self):
        schema = {
            "properties": {
                "channels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["email"],
                },
            }
        }
        data = {}
        result = hydrate_defaults(data, schema)
        assert result["channels"] == ["email"]


class TestResolveEntitySchema:
    def test_creates_allof_composition(self):
        base = {"type": "object", "properties": {"id": {"type": "string"}}}
        app = {"properties": {"name": {"type": "string"}}}

        result = resolve_entity_schema(base, app)

        assert "$schema" in result
        assert "allOf" in result
        assert len(result["allOf"]) == 2
        assert result["allOf"][0] == base
        assert result["allOf"][1] == app


class TestValidateSchemaChange:
    def test_no_change_returns_empty(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        assert validate_schema_change(schema, schema) == []

    def test_added_required_with_default_no_errors(self):
        old = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
        new = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "score": {"type": "integer", "default": 0},
            },
            "required": ["name", "score"],
        }
        diagnostics = validate_schema_change(old, new)
        errors = [d for d in diagnostics if d["severity"] == "error"]
        assert errors == []

    def test_added_required_without_default_error(self):
        old = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
        new = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "score": {"type": "integer"},
            },
            "required": ["name", "score"],
        }
        diagnostics = validate_schema_change(old, new)
        errors = [d for d in diagnostics if d["severity"] == "error"]
        assert len(errors) == 1
        assert errors[0]["field"] == "score"
        assert "no default" in errors[0]["message"]

    def test_type_change_error(self):
        old = {"type": "object", "properties": {"score": {"type": "integer"}}}
        new = {"type": "object", "properties": {"score": {"type": "string"}}}
        diagnostics = validate_schema_change(old, new)
        assert len(diagnostics) == 1
        assert diagnostics[0]["severity"] == "error"
        assert "Type changed" in diagnostics[0]["message"]

    def test_enum_narrowed_error(self):
        old = {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["a", "b", "c"]}},
        }
        new = {"type": "object", "properties": {"status": {"type": "string", "enum": ["a", "b"]}}}
        diagnostics = validate_schema_change(old, new)
        errors = [d for d in diagnostics if d["severity"] == "error"]
        assert len(errors) == 1
        assert "narrowed" in errors[0]["message"]

    def test_enum_widened_ok(self):
        old = {"type": "object", "properties": {"status": {"type": "string", "enum": ["a", "b"]}}}
        new = {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["a", "b", "c"]}},
        }
        diagnostics = validate_schema_change(old, new)
        errors = [d for d in diagnostics if d["severity"] == "error"]
        assert errors == []

    def test_field_removed_warning(self):
        old = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        }
        new = {"type": "object", "properties": {"name": {"type": "string"}}}
        diagnostics = validate_schema_change(old, new)
        assert len(diagnostics) == 1
        assert diagnostics[0]["severity"] == "warning"
        assert diagnostics[0]["field"] == "age"

    def test_multiple_issues(self):
        old = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "score": {"type": "integer"},
                "old_field": {"type": "string"},
            },
            "required": ["name"],
        }
        new = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "score": {"type": "string"},  # type change
                "new_required": {"type": "boolean"},  # required without default
            },
            "required": ["name", "new_required"],
        }
        diagnostics = validate_schema_change(old, new)
        assert len(diagnostics) == 3  # type change + required without default + field removed
        severities = {d["severity"] for d in diagnostics}
        assert "error" in severities
        assert "warning" in severities


class TestRequiredWithoutDefaultWarning:
    def test_warns_on_required_without_default(self, caplog):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "score": {"type": "integer"},
            },
            "required": ["name", "score"],
        }
        data = {"name": "test", "score": 5}
        with caplog.at_level(logging.WARNING, logger="upjack.schema"):
            validate_entity(data, schema)
        assert any("name" in r.message for r in caplog.records)
        assert any("score" in r.message for r in caplog.records)

    def test_no_warning_when_default_present(self, caplog):
        schema = {
            "type": "object",
            "properties": {
                "score": {"type": "integer", "default": 0},
            },
            "required": ["score"],
        }
        data = {"score": 5}
        with caplog.at_level(logging.WARNING, logger="upjack.schema"):
            validate_entity(data, schema)
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) == 0

    def test_no_warning_for_base_fields(self, caplog):
        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "type": {"type": "string"},
                "version": {"type": "integer"},
                "created_at": {"type": "string"},
                "updated_at": {"type": "string"},
            },
            "required": ["id", "type", "version", "created_at", "updated_at"],
        }
        data = {
            "id": "ct_123",
            "type": "contact",
            "version": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        with caplog.at_level(logging.WARNING, logger="upjack.schema"):
            validate_entity(data, schema)
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) == 0
