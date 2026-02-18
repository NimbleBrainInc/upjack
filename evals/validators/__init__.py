"""Upjack eval validators — deterministic checks for generated apps."""

from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from validators import integration, manifest, schema, seed, structure
from validators._types import Finding

# Re-export Finding so other code can do `from validators import Finding`
__all__ = ["Finding", "ValidationResult", "run_all"]


@dataclass
class ValidationResult:
    """Aggregated result from all validators."""

    findings: list[Finding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(f.severity == "error" for f in self.findings) and not self.errors

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error") + len(self.errors)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warning")

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "findings": [
                {"rule": f.rule, "severity": f.severity, "message": f.message, "file": f.file}
                for f in self.findings
            ],
            "errors": self.errors,
        }


_VALIDATORS = [
    ("manifest", manifest.validate),
    ("schema", schema.validate),
    ("seed", seed.validate),
    ("structure", structure.validate),
    ("integration", integration.validate),
]


def run_all(app_dir: Path, case: dict[str, Any]) -> ValidationResult:
    """Run all validators against a generated app directory."""
    result = ValidationResult()

    for name, validate_fn in _VALIDATORS:
        try:
            findings = validate_fn(app_dir, case)
            result.findings.extend(findings)
        except Exception:
            tb = traceback.format_exc()
            result.errors.append(f"Validator '{name}' crashed:\n{tb}")

    return result
