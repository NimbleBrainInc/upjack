"""Tests for upjack.schema module."""

import json

import jsonschema
import pytest

from upjack.schema import load_schema, resolve_entity_schema, validate_entity


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
