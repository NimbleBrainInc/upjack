"""NimbleBrain Upjack — schema-driven entity management for AI-native applications."""

__version__ = "0.4.3"

from upjack.activity import ACTIVITY_ENTITY_DEF, get_activity_schema
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
from upjack.paths import entity_dir, entity_path, index_dir, index_path, resolve_root, schema_dir
from upjack.relations import query_reverse, rebuild_index
from upjack.schema import (
    hydrate_defaults,
    load_schema,
    resolve_entity_schema,
    validate_entity,
    validate_schema_change,
)
from upjack.search import search_entities

__all__ = [
    "ACTIVITY_ENTITY_DEF",
    "Entity",
    "UpjackApp",
    "create_entity",
    "delete_entity",
    "entity_dir",
    "entity_path",
    "generate_id",
    "get_activity_schema",
    "get_entity",
    "hydrate_defaults",
    "index_dir",
    "index_path",
    "list_entities",
    "load_schema",
    "parse_id",
    "query_reverse",
    "rebuild_index",
    "resolve_entity_schema",
    "resolve_root",
    "schema_dir",
    "search_entities",
    "update_entity",
    "validate_entity",
    "validate_id",
    "validate_schema_change",
]
