"""NimbleBrain Upjack — schema-driven entity management for AI-native applications."""

__version__ = "0.1.1"

from upjack.app import UpjackApp
from upjack.entity import (
    Entity,
    create_entity,
    delete_entity,
    get_entity,
    list_entities,
    update_entity,
)
from upjack.ids import generate_id, parse_id, validate_id
from upjack.paths import entity_dir, entity_path, schema_dir
from upjack.schema import (
    hydrate_defaults,
    load_schema,
    resolve_entity_schema,
    validate_entity,
    validate_schema_change,
)
from upjack.search import search_entities

__all__ = [
    "UpjackApp",
    "Entity",
    "create_entity",
    "update_entity",
    "get_entity",
    "list_entities",
    "delete_entity",
    "generate_id",
    "parse_id",
    "validate_id",
    "hydrate_defaults",
    "load_schema",
    "validate_entity",
    "resolve_entity_schema",
    "validate_schema_change",
    "search_entities",
    "entity_dir",
    "entity_path",
    "schema_dir",
]
