"""JSON Schema loading and validation for upjack entities."""

import json
from pathlib import Path
from typing import Any

import referencing
import referencing.jsonschema
from jsonschema import Draft202012Validator

_SCHEMAS_DIR = Path(__file__).parent / "schemas"

# Load the bundled base entity schema and build a registry so that
# app schemas using $ref to the remote URL resolve locally.
_BASE_SCHEMA = json.loads((_SCHEMAS_DIR / "upjack-entity.schema.json").read_text())
_BASE_RESOURCE = referencing.Resource.from_contents(
    _BASE_SCHEMA, default_specification=referencing.jsonschema.DRAFT202012
)
_REGISTRY = referencing.Registry().with_resource(
    "https://upjack.dev/schemas/v1/upjack-entity.schema.json", _BASE_RESOURCE
)


def load_schema(path: str | Path) -> dict[str, Any]:
    """Load a JSON Schema from a file path.

    Args:
        path: Path to the .schema.json file.

    Returns:
        Parsed JSON Schema as a dict.

    Raises:
        FileNotFoundError: If the schema file doesn't exist.
        json.JSONDecodeError: If the file isn't valid JSON.
    """
    path = Path(path)
    return json.loads(path.read_text())


def validate_entity(data: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate entity data against a JSON Schema.

    Uses JSON Schema draft 2020-12 validation. Resolves $ref to the
    base entity schema via a bundled local copy.

    Args:
        data: Entity data to validate.
        schema: JSON Schema to validate against.

    Raises:
        jsonschema.ValidationError: If validation fails.
    """
    validator = Draft202012Validator(schema, registry=_REGISTRY)
    validator.validate(data)


def resolve_entity_schema(
    base_schema: dict[str, Any], app_schema: dict[str, Any]
) -> dict[str, Any]:
    """Create a composed schema from base entity schema and app-specific schema.

    Uses allOf composition so both base and app constraints apply.

    Args:
        base_schema: The upjack-entity base schema.
        app_schema: The app-specific entity schema.

    Returns:
        Composed schema with allOf referencing both.
    """
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "allOf": [base_schema, app_schema],
    }
