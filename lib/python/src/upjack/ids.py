"""Prefixed ULID generation and validation for upjack entities."""

import re

from ulid import ULID

ID_PATTERN = re.compile(r"^[a-z]{2,4}_[0-9A-HJKMNP-TV-Z]{26}$")
PREFIX_PATTERN = re.compile(r"^[a-z]{2,4}$")


def generate_id(prefix: str) -> str:
    """Generate a new prefixed ULID.

    Args:
        prefix: 2-4 lowercase letter prefix (e.g., 'ct' for contact).

    Returns:
        Prefixed ULID string (e.g., 'ct_01JKXM9V3QWERTY123456ABCDF').

    Raises:
        ValueError: If prefix doesn't match ^[a-z]{2,4}$.
    """
    if not PREFIX_PATTERN.match(prefix):
        raise ValueError(f"Invalid prefix '{prefix}': must be 2-4 lowercase letters")
    ulid = ULID()
    return f"{prefix}_{ulid!s}"


def parse_id(entity_id: str) -> tuple[str, str]:
    """Parse a prefixed ULID into (prefix, ulid_str).

    Args:
        entity_id: Prefixed ULID string.

    Returns:
        Tuple of (prefix, ulid_string).

    Raises:
        ValueError: If the ID doesn't match the expected format.
    """
    if not validate_id(entity_id):
        raise ValueError(f"Invalid entity ID: '{entity_id}'")
    prefix, ulid_str = entity_id.split("_", 1)
    return prefix, ulid_str


def validate_id(entity_id: str) -> bool:
    """Check if a string is a valid prefixed ULID.

    Args:
        entity_id: String to validate.

    Returns:
        True if valid, False otherwise.
    """
    return bool(ID_PATTERN.match(entity_id))
