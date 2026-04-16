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

# Canonical $id / $ref URL for the bundled base entity schema. App schemas
# reference this via `allOf: [{"$ref": BASE_ENTITY_REF}]` so apps can layer
# their own fields on top of the framework-managed ones.
BASE_ENTITY_REF = "https://upjack.dev/schemas/v1/upjack-entity.schema.json"

# The bundled copy of the base entity schema, loaded once at import time.
_BASE_SCHEMA = json.loads((_SCHEMAS_DIR / "upjack-entity.schema.json").read_text())
_BASE_RESOURCE = referencing.Resource.from_contents(
    _BASE_SCHEMA, default_specification=referencing.jsonschema.DRAFT202012
)
_REGISTRY = referencing.Registry().with_resource(BASE_ENTITY_REF, _BASE_RESOURCE)


def load_schema(path: str | Path) -> dict[str, Any]:
    """Load a JSON Schema from disk and inline the base-entity ``$ref``.

    Any ``allOf: [{"$ref": BASE_ENTITY_REF}]`` entry is replaced with the
    bundled base-entity schema inline, so every downstream consumer sees a
    fully self-contained schema. This is the single source of truth for
    $ref resolution — no caller needs to do it again.
    """
    schema = json.loads(Path(path).read_text())
    _inline_base_entity_ref(schema)
    return schema


def _inline_base_entity_ref(node: Any) -> None:
    """Walk a schema in place, replacing every ``$ref: BASE_ENTITY_REF`` dict
    with a deep copy of the bundled base schema contents.

    The inlined copy keeps its ``$id`` so downstream consumers can identify
    it (e.g., to filter it out when projecting the schema onto a tool input
    that excludes base fields). ``$schema`` is dropped — it's a meta keyword
    that doesn't belong inside an ``allOf`` member.
    """
    if isinstance(node, dict):
        all_of = node.get("allOf")
        if isinstance(all_of, list):
            for i, sub in enumerate(all_of):
                if isinstance(sub, dict) and sub.get("$ref") == BASE_ENTITY_REF:
                    inlined = copy.deepcopy(_BASE_SCHEMA)
                    inlined.pop("$schema", None)
                    all_of[i] = inlined
        for value in node.values():
            _inline_base_entity_ref(value)
    elif isinstance(node, list):
        for item in node:
            _inline_base_entity_ref(item)


def validate_entity(data: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate entity data against a JSON Schema.

    Uses JSON Schema draft 2020-12 validation. The registry resolves any
    remaining ``$ref`` to the base entity schema locally, so validation works
    even if the caller handed us a schema that bypassed ``load_schema``.
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
    """Fill missing fields in ``data`` with defaults from ``schema``.

    Walks the schema's ``properties`` and any ``allOf`` members. Assumes
    ``schema`` has been loaded via :func:`load_schema` (so any base-entity
    ``$ref`` has been inlined) — does not resolve live ``$ref`` values.
    Operates on a shallow copy of ``data``.
    """
    result = dict(data)
    _apply_property_defaults(result, schema)
    return result


def _apply_property_defaults(data: dict[str, Any], schema: dict[str, Any]) -> None:
    """Apply defaults from a single schema node's properties and allOf members."""
    for sub in schema.get("allOf", []):
        if isinstance(sub, dict):
            _apply_property_defaults(data, sub)

    props = schema.get("properties", {})
    for field_name, field_schema in props.items():
        if field_name not in data and "default" in field_schema:
            data[field_name] = copy.deepcopy(field_schema["default"])


def resolve_entity_schema(
    base_schema: dict[str, Any], app_schema: dict[str, Any]
) -> dict[str, Any]:
    """Create a composed schema from the base entity schema and an app schema.

    Uses ``allOf`` composition so both base and app constraints apply.
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

    Expects ``schema`` to be already self-contained (loaded via
    :func:`load_schema`). Strips JSON Schema meta keywords that don't belong
    in a tool output schema. MCP requires ``type: "object"`` on every
    outputSchema.
    """
    result = copy.deepcopy(schema)
    result.pop("$schema", None)
    result.pop("$id", None)
    if "type" not in result:
        result["type"] = "object"
    return result


def build_list_output_schema(entity_schema: dict[str, Any]) -> dict[str, Any]:
    """Build an output schema for a list/search response envelope."""
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
