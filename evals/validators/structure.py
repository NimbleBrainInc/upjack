"""Structure validator — checks context.md, server.py, README.md, and skill files."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from validators._types import Finding


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
    entities = upjack.get("entities", [])
    entity_names = [e.get("name", "") for e in entities]

    # --- context.md ---
    context_rel = upjack.get("context", "context.md")
    context_path = app_dir / context_rel
    if not context_path.exists():
        findings.append(
            Finding("STRUCT-CTX-1", "error", f"Context file '{context_rel}' not found", context_rel)
        )
    else:
        ctx_text = context_path.read_text()
        ctx_lines = ctx_text.splitlines()

        if "## Entity Relationships" not in ctx_text:
            findings.append(
                Finding(
                    "STRUCT-CTX-2",
                    "warning",
                    "context.md missing '## Entity Relationships' section",
                    context_rel,
                )
            )

        if len(ctx_lines) > 50:
            findings.append(
                Finding(
                    "STRUCT-CTX-3",
                    "warning",
                    f"context.md is {len(ctx_lines)} lines (recommended <50)",
                    context_rel,
                )
            )

    # --- server.py ---
    server_path = app_dir / "server.py"
    if not server_path.exists():
        findings.append(Finding("STRUCT-SRV-1", "error", "server.py not found", "server.py"))
    else:
        srv_text = server_path.read_text()
        srv_lines = [line for line in srv_text.splitlines() if line.strip()]

        if "from upjack.server import create_server" not in srv_text:
            findings.append(
                Finding(
                    "STRUCT-SRV-2",
                    "error",
                    "server.py must import create_server from upjack.server",
                    "server.py",
                )
            )

        if "create_server(" not in srv_text:
            findings.append(
                Finding(
                    "STRUCT-SRV-3",
                    "error",
                    "server.py must call create_server()",
                    "server.py",
                )
            )

        if "__name__" not in srv_text or "mcp.run()" not in srv_text:
            findings.append(
                Finding(
                    "STRUCT-SRV-4",
                    "error",
                    "server.py must have __main__ guard calling mcp.run()",
                    "server.py",
                )
            )

        if len(srv_lines) > 10:
            findings.append(
                Finding(
                    "STRUCT-SRV-5",
                    "warning",
                    f"server.py has {len(srv_lines)} non-blank lines (expected ~5 for 3-tier pattern)",
                    "server.py",
                )
            )

    # --- README.md ---
    readme_path = app_dir / "README.md"
    if not readme_path.exists():
        findings.append(Finding("STRUCT-README-1", "error", "README.md not found", "README.md"))
    else:
        readme_text = readme_path.read_text()

        # Check entity mentions
        for ename in entity_names:
            if ename not in readme_text.lower():
                findings.append(
                    Finding(
                        "STRUCT-README-2",
                        "warning",
                        f"README.md doesn't mention entity '{ename}'",
                        "README.md",
                    )
                )

        # Check for code block
        if "```" not in readme_text:
            findings.append(
                Finding(
                    "STRUCT-README-3",
                    "warning",
                    "README.md has no code blocks",
                    "README.md",
                )
            )

        # Check skill references
        skills = upjack.get("skills", [])
        for skill in skills:
            if skill.get("source") == "bundled":
                skill_path = skill.get("path", "")
                # Extract skill name from path like skills/task-management/SKILL.md
                skill_dir = Path(skill_path).parent.name
                if (
                    skill_dir
                    and skill_dir not in readme_text
                    and skill_dir.replace("-", " ") not in readme_text.lower()
                ):
                    findings.append(
                        Finding(
                            "STRUCT-README-4",
                            "info",
                            f"README.md doesn't reference skill '{skill_dir}'",
                            "README.md",
                        )
                    )

    # --- Skill files ---
    for skill in upjack.get("skills", []):
        if skill.get("source") != "bundled":
            continue

        skill_rel = skill.get("path", "")
        skill_path = app_dir / skill_rel

        if not skill_path.exists():
            continue  # manifest validator handles this

        skill_text = skill_path.read_text()
        skill_name = Path(skill_rel).parent.name

        required_sections = ["## When to Use", "## Process", "## Rules"]
        for section in required_sections:
            if section not in skill_text:
                # Also check lowercase and flexible whitespace
                pattern = re.compile(re.escape(section), re.IGNORECASE)
                if not pattern.search(skill_text):
                    findings.append(
                        Finding(
                            "STRUCT-SKILL-1",
                            "error",
                            f"Skill '{skill_name}' missing '{section}' section",
                            skill_rel,
                        )
                    )

    return findings
