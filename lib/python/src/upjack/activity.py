"""Activity entity definition and helpers for upjack apps.

Activities are entities that record events against other entities.  They
use the existing CRUD, search, and relationship infrastructure so they
get indexing, querying, and MCP tools for free.

Opt-in via ``"activities": true`` in the manifest's upjack extension.
"""

import json
from pathlib import Path
from typing import Any

_SCHEMA_PATH = Path(__file__).parent / "schemas" / "activity.schema.json"

ACTIVITY_ENTITY_DEF: dict[str, Any] = {
    "name": "activity",
    "plural": "activities",
    "prefix": "act",
    "schema": str(_SCHEMA_PATH),
}


def get_activity_schema() -> dict[str, Any]:
    """Load the built-in activity schema from the package's schemas directory."""
    return json.loads(_SCHEMA_PATH.read_text())
