"""Shared types for validators."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Finding:
    """A single validation finding."""

    rule: str
    severity: str  # "error" | "warning" | "info"
    message: str
    file: str | None = None
