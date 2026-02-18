"""Manifest validator — rules M-1 through M-14."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from validators._types import Finding

VALID_CATEGORIES = {
    "sales",
    "marketing",
    "operations",
    "research",
    "finance",
    "hr",
    "engineering",
    "support",
    "custom",
}

VALID_HOOK_EVENTS = {
    "entity.created",
    "entity.updated",
    "entity.deleted",
    "entity.status_changed",
    "app.installed",
    "app.updated",
}

NAMESPACE_RE = re.compile(r"^apps/[a-z][a-z0-9-]*$")
NAME_RE = re.compile(r"^@[a-z0-9-]+/[a-z][a-z0-9-]*$")
PREFIX_RE = re.compile(r"^[a-z]{2,4}$")
ENTITY_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def validate(app_dir: Path, case: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    manifest_path = app_dir / "manifest.json"

    if not manifest_path.exists():
        findings.append(Finding("M-0", "error", "manifest.json not found", "manifest.json"))
        return findings

    try:
        raw = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as e:
        findings.append(
            Finding("M-0", "error", f"manifest.json is invalid JSON: {e}", "manifest.json")
        )
        return findings

    # Extract upjack block
    upjack = raw.get("_meta", {}).get("ai.nimblebrain/upjack")
    if upjack is None:
        findings.append(
            Finding("M-0", "error", "Missing _meta['ai.nimblebrain/upjack'] block", "manifest.json")
        )
        return findings

    # M-1: manifest_version
    mv = raw.get("manifest_version")
    if mv != "0.4":
        findings.append(
            Finding("M-1", "error", f"manifest_version must be '0.4', got '{mv}'", "manifest.json")
        )

    # M-2: upjack_version
    uv = upjack.get("upjack_version")
    if uv != "0.1":
        findings.append(
            Finding("M-2", "error", f"upjack_version must be '0.1', got '{uv}'", "manifest.json")
        )

    # M-3: namespace format
    ns = upjack.get("namespace", "")
    if not NAMESPACE_RE.match(ns):
        findings.append(
            Finding(
                "M-3",
                "error",
                f"namespace must match apps/[a-z][a-z0-9-]*, got '{ns}'",
                "manifest.json",
            )
        )

    # M-4: name format
    name = raw.get("name", "")
    if name and not NAME_RE.match(name):
        findings.append(
            Finding(
                "M-4",
                "warning",
                f"name should match @scope/name pattern, got '{name}'",
                "manifest.json",
            )
        )

    # Entities
    entities = upjack.get("entities", [])
    if not entities:
        findings.append(Finding("M-5", "error", "entities array is empty", "manifest.json"))
        return findings

    prefixes_seen: dict[str, str] = {}

    for i, entity in enumerate(entities):
        ename = entity.get("name", f"<entity[{i}]>")

        # M-5: entity required fields
        for req in ("name", "schema", "prefix"):
            if req not in entity:
                findings.append(
                    Finding(
                        "M-5",
                        "error",
                        f"Entity '{ename}' missing required field '{req}'",
                        "manifest.json",
                    )
                )

        # Entity name format
        if "name" in entity and not ENTITY_NAME_RE.match(entity["name"]):
            findings.append(
                Finding(
                    "M-5",
                    "error",
                    f"Entity name '{entity['name']}' must match [a-z][a-z0-9_]*",
                    "manifest.json",
                )
            )

        # M-6: non-singleton plural
        plural = entity.get("plural")
        singleton = entity.get("singleton", False)
        if plural and not singleton and plural == ename:
            findings.append(
                Finding(
                    "M-6",
                    "warning",
                    f"Entity '{ename}' plural is same as name (expected pluralized form)",
                    "manifest.json",
                )
            )

        # M-8: prefix format
        prefix = entity.get("prefix", "")
        if prefix and not PREFIX_RE.match(prefix):
            findings.append(
                Finding(
                    "M-8",
                    "error",
                    f"Entity '{ename}' prefix must be 2-4 lowercase chars, got '{prefix}'",
                    "manifest.json",
                )
            )

        # M-9: prefix uniqueness
        if prefix:
            if prefix in prefixes_seen:
                findings.append(
                    Finding(
                        "M-9",
                        "error",
                        f"Prefix '{prefix}' used by both '{prefixes_seen[prefix]}' and '{ename}'",
                        "manifest.json",
                    )
                )
            else:
                prefixes_seen[prefix] = ename

        # M-11: schema file exists
        schema_path = entity.get("schema", "")
        if schema_path and not (app_dir / schema_path).exists():
            findings.append(
                Finding(
                    "M-11",
                    "error",
                    f"Schema file '{schema_path}' not found for entity '{ename}'",
                    schema_path,
                )
            )

    # M-10: category enum
    display = upjack.get("display", {})
    category = display.get("category")
    if category and category not in VALID_CATEGORIES:
        findings.append(
            Finding(
                "M-10",
                "error",
                f"Invalid category '{category}', must be one of: {sorted(VALID_CATEGORIES)}",
                "manifest.json",
            )
        )

    # M-12: skill file existence
    for skill in upjack.get("skills", []):
        if skill.get("source") == "bundled":
            skill_path = skill.get("path", "")
            if skill_path and not (app_dir / skill_path).exists():
                findings.append(
                    Finding(
                        "M-12", "error", f"Bundled skill file '{skill_path}' not found", skill_path
                    )
                )

    # M-14: hook event enum
    for hook in upjack.get("hooks", []):
        event = hook.get("event", "")
        if event not in VALID_HOOK_EVENTS:
            findings.append(
                Finding(
                    "M-14",
                    "error",
                    f"Invalid hook event '{event}', must be one of: {sorted(VALID_HOOK_EVENTS)}",
                    "manifest.json",
                )
            )

    # Case-level expectations
    expect = case.get("expect", {})

    # Expected entities by name
    for expected_entity in expect.get("entities", []):
        exp_name = expected_entity.get("name")
        if exp_name and not any(e.get("name") == exp_name for e in entities):
            findings.append(
                Finding(
                    "EXPECT-ENTITY",
                    "error",
                    f"Expected entity '{exp_name}' not found in manifest",
                    "manifest.json",
                )
            )

    # Expected entity count range
    ec = expect.get("entity_count")
    if ec:
        lo, hi = ec
        actual = len(entities)
        if not (lo <= actual <= hi):
            findings.append(
                Finding(
                    "EXPECT-ENTITY-COUNT",
                    "error",
                    f"Expected {lo}-{hi} entities, got {actual}",
                    "manifest.json",
                )
            )

    # Expected skill count range
    sc = expect.get("skill_count")
    if sc:
        lo, hi = sc
        actual = len(upjack.get("skills", []))
        if not (lo <= actual <= hi):
            findings.append(
                Finding(
                    "EXPECT-SKILL-COUNT",
                    "error",
                    f"Expected {lo}-{hi} skills, got {actual}",
                    "manifest.json",
                )
            )

    return findings
