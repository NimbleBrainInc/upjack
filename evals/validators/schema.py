"""Schema validator — rules S-1 through S-9."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from validators._types import Finding

BASE_FIELDS = {
    "id",
    "type",
    "version",
    "created_at",
    "updated_at",
    "created_by",
    "status",
    "tags",
    "source",
    "relationships",
}

EXPECTED_SCHEMA_URI = "https://json-schema.org/draft/2020-12/schema"
EXPECTED_BASE_REF = "https://upjack.dev/schemas/v1/upjack-entity.schema.json"

BASE_REQUIRED = {"id", "type", "version", "created_at", "updated_at"}


def validate(app_dir: Path, case: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    manifest_path = app_dir / "manifest.json"

    if not manifest_path.exists():
        return findings  # manifest validator handles this

    try:
        raw = json.loads(manifest_path.read_text())
    except json.JSONDecodeError:
        return findings

    upjack = raw.get("_meta", {}).get("ai.nimblebrain/upjack", {})
    entities = upjack.get("entities", [])

    for entity in entities:
        ename = entity.get("name", "unknown")
        schema_rel = entity.get("schema", "")
        schema_path = app_dir / schema_rel

        if not schema_path.exists():
            continue  # manifest validator catches missing files

        try:
            schema_data = json.loads(schema_path.read_text())
        except json.JSONDecodeError as e:
            findings.append(
                Finding("S-0", "error", f"Schema for '{ename}' is invalid JSON: {e}", schema_rel)
            )
            continue

        # S-1: $schema must be draft-2020-12
        actual_schema = schema_data.get("$schema", "")
        if actual_schema != EXPECTED_SCHEMA_URI:
            findings.append(
                Finding(
                    "S-1",
                    "error",
                    f"$schema must be '{EXPECTED_SCHEMA_URI}', got '{actual_schema}'",
                    schema_rel,
                )
            )

        # S-2: allOf must contain base ref
        all_of = schema_data.get("allOf", [])
        has_base_ref = any(item.get("$ref") == EXPECTED_BASE_REF for item in all_of)
        if not has_base_ref:
            findings.append(
                Finding(
                    "S-2",
                    "error",
                    f"Schema must have allOf with $ref to '{EXPECTED_BASE_REF}'",
                    schema_rel,
                )
            )

        # S-3: property descriptions
        properties = schema_data.get("properties", {})
        for prop_name, prop_def in properties.items():
            if prop_name in BASE_FIELDS:
                continue  # base fields checked separately
            if isinstance(prop_def, dict) and "description" not in prop_def:
                findings.append(
                    Finding(
                        "S-3",
                        "warning",
                        f"Property '{prop_name}' in '{ename}' schema missing description",
                        schema_rel,
                    )
                )

        # S-4: no base field redefinitions
        for prop_name in properties:
            if prop_name in BASE_FIELDS:
                findings.append(
                    Finding(
                        "S-4",
                        "error",
                        f"Schema for '{ename}' redefines base field '{prop_name}'",
                        schema_rel,
                    )
                )

        # S-5: no additionalProperties
        if "additionalProperties" in schema_data:
            findings.append(
                Finding(
                    "S-5",
                    "error",
                    f"Schema for '{ename}' must not set additionalProperties (base schema handles it)",
                    schema_rel,
                )
            )

        # S-6: no base fields in required
        required = schema_data.get("required", [])
        for req_field in required:
            if req_field in BASE_REQUIRED:
                findings.append(
                    Finding(
                        "S-6",
                        "error",
                        f"Schema for '{ename}' lists base field '{req_field}' in required",
                        schema_rel,
                    )
                )

        # S-7: top-level $schema present
        if "$schema" not in schema_data:
            findings.append(
                Finding("S-7", "error", f"Schema for '{ename}' missing $schema", schema_rel)
            )

        # S-8: top-level title present
        if "title" not in schema_data:
            findings.append(
                Finding("S-8", "warning", f"Schema for '{ename}' missing title", schema_rel)
            )

        # S-9: top-level description present
        if "description" not in schema_data:
            findings.append(
                Finding("S-9", "warning", f"Schema for '{ename}' missing description", schema_rel)
            )

    return findings
