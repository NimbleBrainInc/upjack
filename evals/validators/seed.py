"""Seed data validator — rules SD-1 through SD-11."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from validators._types import Finding

FORBIDDEN_FIELDS = {"id", "created_at", "updated_at"}


def validate(app_dir: Path, case: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    manifest_path = app_dir / "manifest.json"

    if not manifest_path.exists():
        return findings

    try:
        raw = json.loads(manifest_path.read_text())
    except json.JSONDecodeError:
        return findings

    upjack = raw.get("_meta", {}).get("ai.nimblebrain/upjack", {})
    seed_config = upjack.get("seed")

    if seed_config is None:
        findings.append(
            Finding("SD-0", "warning", "No seed configuration in manifest", "manifest.json")
        )
        return findings

    seed_dir_rel = seed_config.get("data", "seed/")
    seed_dir = app_dir / seed_dir_rel

    if not seed_dir.exists():
        findings.append(
            Finding("SD-0", "error", f"Seed directory '{seed_dir_rel}' not found", seed_dir_rel)
        )
        return findings

    entity_names = {e.get("name") for e in upjack.get("entities", [])}
    seed_files = sorted(seed_dir.glob("*.json"))

    if not seed_files:
        findings.append(
            Finding("SD-0", "warning", f"No seed files in '{seed_dir_rel}'", seed_dir_rel)
        )
        return findings

    for seed_file in seed_files:
        rel_path = str(seed_file.relative_to(app_dir))

        try:
            data = json.loads(seed_file.read_text())
        except json.JSONDecodeError as e:
            findings.append(Finding("SD-0", "error", f"Invalid JSON: {e}", rel_path))
            continue

        # SD-7: must be a JSON array
        if not isinstance(data, list):
            findings.append(Finding("SD-7", "error", "Seed file must be a JSON array", rel_path))
            continue

        # SD-8: 2-5 records per file
        count = len(data)
        if count < 2 or count > 5:
            findings.append(
                Finding(
                    "SD-8",
                    "warning",
                    f"Seed file has {count} records (expected 2-5)",
                    rel_path,
                )
            )

        for j, record in enumerate(data):
            if not isinstance(record, dict):
                findings.append(
                    Finding("SD-0", "error", f"Record [{j}] is not an object", rel_path)
                )
                continue

            # SD-1: has type field
            rec_type = record.get("type")
            if rec_type is None:
                findings.append(
                    Finding("SD-1", "error", f"Record [{j}] missing 'type' field", rel_path)
                )

            # SD-2: version == 1
            rec_version = record.get("version")
            if rec_version is None:
                findings.append(
                    Finding("SD-2", "warning", f"Record [{j}] missing 'version' field", rel_path)
                )
            elif rec_version != 1:
                findings.append(
                    Finding(
                        "SD-2",
                        "error",
                        f"Record [{j}] version must be 1, got {rec_version}",
                        rel_path,
                    )
                )

            # SD-3/4/5: no id, created_at, updated_at
            for forbidden in FORBIDDEN_FIELDS:
                if forbidden in record:
                    rule = {"id": "SD-3", "created_at": "SD-4", "updated_at": "SD-5"}[forbidden]
                    findings.append(
                        Finding(
                            rule,
                            "error",
                            f"Record [{j}] must not contain '{forbidden}' (auto-generated)",
                            rel_path,
                        )
                    )

            # SD-6: tags include "sample"
            tags = record.get("tags", [])
            if isinstance(tags, list) and "sample" not in tags:
                findings.append(
                    Finding(
                        "SD-6",
                        "warning",
                        f"Record [{j}] tags should include 'sample'",
                        rel_path,
                    )
                )

            # SD-11: type matches a known entity name
            if rec_type and rec_type not in entity_names:
                findings.append(
                    Finding(
                        "SD-11",
                        "error",
                        f"Record [{j}] type '{rec_type}' doesn't match any entity",
                        rel_path,
                    )
                )

    return findings
