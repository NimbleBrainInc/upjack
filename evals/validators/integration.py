"""Integration validator — tests app loading, server creation, and seed data via upjack library."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from validators._types import Finding


def _setup_workspace(app_dir: Path, tmp: Path) -> Path:
    """Copy the app into a temp workspace so upjack can write entity data."""
    workspace = tmp / "workspace"
    workspace.mkdir()
    app_copy = tmp / "app"
    shutil.copytree(app_dir, app_copy)
    return app_copy


def validate(app_dir: Path, case: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    assertions = case.get("assertions", [])

    if not assertions:
        return findings

    manifest_path = app_dir / "manifest.json"
    if not manifest_path.exists():
        return findings

    with tempfile.TemporaryDirectory(prefix="upjack-eval-") as tmp_str:
        tmp = Path(tmp_str)
        app_copy = _setup_workspace(app_dir, tmp)
        workspace = tmp / "workspace"
        manifest_copy = app_copy / "manifest.json"

        # ASSERT: app_loads
        if "app_loads" in assertions:
            try:
                from upjack import UpjackApp

                UpjackApp.from_manifest(manifest_copy, root=workspace)
            except Exception as e:
                findings.append(
                    Finding(
                        "INT-APP-LOAD",
                        "error",
                        f"UpjackApp.from_manifest() raised: {e}",
                        "manifest.json",
                    )
                )

        # ASSERT: server_creates
        if "server_creates" in assertions:
            try:
                from upjack.server import create_server

                create_server(manifest_copy, root=workspace)
            except Exception as e:
                findings.append(
                    Finding(
                        "INT-SERVER-CREATE",
                        "error",
                        f"create_server() raised: {e}",
                        "manifest.json",
                    )
                )

        # ASSERT: seed_loads
        if "seed_loads" in assertions:
            try:
                from upjack import UpjackApp

                app = UpjackApp.from_manifest(manifest_copy, root=workspace)

                # Read manifest to find seed config
                raw = json.loads(manifest_copy.read_text())
                upjack = raw.get("_meta", {}).get("ai.nimblebrain/upjack", {})
                seed_config = upjack.get("seed")

                if seed_config is None:
                    findings.append(
                        Finding(
                            "INT-SEED-LOAD",
                            "warning",
                            "No seed config — skipping seed_loads assertion",
                            "manifest.json",
                        )
                    )
                else:
                    seed_dir_rel = seed_config.get("data", "seed/")
                    seed_dir = app_copy / seed_dir_rel

                    if not seed_dir.exists():
                        findings.append(
                            Finding(
                                "INT-SEED-LOAD",
                                "error",
                                f"Seed directory '{seed_dir_rel}' not found",
                                seed_dir_rel,
                            )
                        )
                    else:
                        errors = []
                        for seed_file in sorted(seed_dir.glob("*.json")):
                            try:
                                data = json.loads(seed_file.read_text())
                                if not isinstance(data, list):
                                    data = [data]
                                for record in data:
                                    entity_type = record.get("type")
                                    if entity_type:
                                        # Strip base fields before creating
                                        create_data = {
                                            k: v
                                            for k, v in record.items()
                                            if k
                                            not in (
                                                "id",
                                                "type",
                                                "version",
                                                "created_at",
                                                "updated_at",
                                                "created_by",
                                            )
                                        }
                                        app.create_entity(entity_type, create_data)
                            except Exception as e:
                                errors.append(f"{seed_file.name}: {e}")

                        if errors:
                            findings.append(
                                Finding(
                                    "INT-SEED-LOAD",
                                    "error",
                                    f"Seed loading errors: {'; '.join(errors)}",
                                    seed_dir_rel,
                                )
                            )
            except Exception as e:
                findings.append(
                    Finding(
                        "INT-SEED-LOAD",
                        "error",
                        f"seed_loads assertion failed: {e}",
                        "manifest.json",
                    )
                )

    return findings
