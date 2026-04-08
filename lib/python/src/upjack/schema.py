"""JSON Schema loading and validation for upjack entities."""

import copy
import json
import logging
from pathlib import Path
from typing import Any

import referencing
import referencing.jsonschema
from jsonschema import Draft202012Validator

logger = logging.getLogger(__name__)

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
    missing = _check_required_without_defaults(schema)
    for field in missing:
        logger.warning(
            "Field '%s' is required but has no default — "
            "existing entities without it will fail validation",
            field,
        )

    validator = Draft202012Validator(schema, registry=_REGISTRY)
    validator.validate(data)


def hydrate_defaults(data: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Fill missing fields in data with defaults from the schema.

    Walks the schema's "properties" (and any allOf members) to find
    fields with a "default" value. If the field is absent from data,
    sets it to the default. Operates on a shallow copy — does not
    mutate the input dict.

    Args:
        data: Entity data (may be missing fields).
        schema: JSON Schema with optional "default" values on properties.

    Returns:
        A new dict with missing fields filled from schema defaults.
    """
    result = dict(data)
    _apply_property_defaults(result, schema)
    return result


def _apply_property_defaults(data: dict[str, Any], schema: dict[str, Any]) -> None:
    """Apply defaults from a single schema node's properties."""
    # Handle allOf — walk each sub-schema
    for sub in schema.get("allOf", []):
        # Resolve $ref to the base entity schema
        ref = sub.get("$ref")
        if ref and ref in _REF_MAP:
            _apply_property_defaults(data, _REF_MAP[ref])
        else:
            _apply_property_defaults(data, sub)

    props = schema.get("properties", {})
    for field_name, field_schema in props.items():
        if field_name not in data and "default" in field_schema:
            data[field_name] = copy.deepcopy(field_schema["default"])


# Map $ref URIs to resolved schemas for hydration
_REF_MAP: dict[str, dict[str, Any]] = {
    "https://upjack.dev/schemas/v1/upjack-entity.schema.json": _BASE_SCHEMA,
}


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


_BASE_FIELDS = {"id", "type", "version", "created_at", "updated_at"}


def _check_required_without_defaults(schema: dict[str, Any]) -> list[str]:
    """Return field names that are required but have no default, excluding base fields."""
    required = set(schema.get("required", []))
    properties = schema.get("properties", {})
    return [
        name
        for name in sorted(required - _BASE_FIELDS)
        if name in properties and "default" not in properties[name]
    ]


def validate_schema_change(
    old_schema: dict[str, Any],
    new_schema: dict[str, Any],
) -> list[dict[str, str]]:
    """Compare two app-level schema dicts and return a list of diagnostics.

    Compares top-level ``properties`` and ``required`` only (does not
    resolve ``$ref`` or walk ``allOf``).

    Each diagnostic is a dict with keys: ``severity``, ``field``, ``message``.
    """
    diagnostics: list[dict[str, str]] = []

    old_props = old_schema.get("properties", {})
    new_props = new_schema.get("properties", {})
    old_required = set(old_schema.get("required", []))
    new_required = set(new_schema.get("required", []))

    # Required without default
    newly_required = new_required - old_required
    for field in sorted(newly_required):
        prop = new_props.get(field, {})
        if "default" not in prop:
            diagnostics.append(
                {
                    "severity": "error",
                    "field": field,
                    "message": f"Field '{field}' is newly required but has no default",
                }
            )

    # Type change
    for field in sorted(set(old_props) & set(new_props)):
        old_type = old_props[field].get("type")
        new_type = new_props[field].get("type")
        if old_type and new_type and old_type != new_type:
            diagnostics.append(
                {
                    "severity": "error",
                    "field": field,
                    "message": f"Type changed from '{old_type}' to '{new_type}'",
                }
            )

        # Enum narrowed
        old_enum = old_props[field].get("enum")
        new_enum = new_props[field].get("enum")
        if old_enum is not None and new_enum is not None:
            if set(new_enum) < set(old_enum):
                diagnostics.append(
                    {
                        "severity": "error",
                        "field": field,
                        "message": f"Enum narrowed from {old_enum} to {new_enum}",
                    }
                )

    # Field removed
    for field in sorted(set(old_props) - set(new_props)):
        diagnostics.append(
            {
                "severity": "warning",
                "field": field,
                "message": f"Field '{field}' was removed",
            }
        )

    return diagnostics


def build_entity_output_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Build an output schema for a single-entity tool response.

    Returns the full entity schema (including base fields) with JSON Schema
    meta keywords stripped, suitable for use as a tool's ``outputSchema``.
    MCP requires ``type: "object"`` on every outputSchema.
    """
    result = copy.deepcopy(schema)
    result.pop("$schema", None)
    result.pop("$id", None)
    # MCP spec requires outputSchema to have type: "object"
    if "type" not in result:
        result["type"] = "object"
    return result


def build_list_output_schema(entity_schema: dict[str, Any]) -> dict[str, Any]:
    """Build an output schema for a list/search response envelope.

    Returns an object schema with ``entities`` (array of entity schemas)
    and ``count`` (integer).
    """
    item_schema = build_entity_output_schema(entity_schema)
    return {
        "type": "object",
        "properties": {
            "entities": {
                "type": "array",
                "items": item_schema,
            },
            "count": {
                "type": "integer",
                "description": "Number of entities returned",
            },
        },
        "required": ["entities", "count"],
    }
