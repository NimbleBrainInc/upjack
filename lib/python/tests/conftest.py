"""Shared fixtures for upjack tests."""

from pathlib import Path

import pytest

SAMPLE_ENTITY_SCHEMA = {
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
        "email": {"type": "string", "format": "email"},
    },
    "required": ["id", "type", "version", "created_at", "updated_at", "first_name", "last_name"],
    "additionalProperties": True,
}

SAMPLE_ENTITIES = [
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
def tmp_workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace directory."""
    return tmp_path


@pytest.fixture
def sample_schema() -> dict:
    """Return a sample entity schema for testing."""
    return SAMPLE_ENTITY_SCHEMA


@pytest.fixture
def sample_entities() -> list[dict]:
    """Return sample entity definitions."""
    return SAMPLE_ENTITIES
