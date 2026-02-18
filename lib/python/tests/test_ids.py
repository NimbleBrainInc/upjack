"""Tests for upjack.ids module."""

import pytest

from upjack.ids import generate_id, parse_id, validate_id


class TestGenerateId:
    def test_generates_valid_id(self):
        result = generate_id("ct")
        assert validate_id(result)
        assert result.startswith("ct_")

    def test_different_prefixes(self):
        for prefix in ["ct", "co", "dl", "act", "rpt"]:
            result = generate_id(prefix)
            assert result.startswith(f"{prefix}_")
            assert validate_id(result)

    def test_unique_ids(self):
        ids = {generate_id("ct") for _ in range(100)}
        assert len(ids) == 100

    def test_rejects_invalid_prefix_too_short(self):
        with pytest.raises(ValueError, match="Invalid prefix"):
            generate_id("c")

    def test_rejects_invalid_prefix_too_long(self):
        with pytest.raises(ValueError, match="Invalid prefix"):
            generate_id("contact")

    def test_rejects_uppercase_prefix(self):
        with pytest.raises(ValueError, match="Invalid prefix"):
            generate_id("CT")

    def test_rejects_numeric_prefix(self):
        with pytest.raises(ValueError, match="Invalid prefix"):
            generate_id("12")


class TestParseId:
    def test_parses_valid_id(self):
        entity_id = generate_id("ct")
        prefix, ulid_str = parse_id(entity_id)
        assert prefix == "ct"
        assert len(ulid_str) == 26

    def test_parses_longer_prefix(self):
        entity_id = generate_id("act")
        prefix, ulid_str = parse_id(entity_id)
        assert prefix == "act"

    def test_rejects_invalid_id(self):
        with pytest.raises(ValueError, match="Invalid entity ID"):
            parse_id("bad_id")


class TestValidateId:
    def test_valid_id(self):
        entity_id = generate_id("ct")
        assert validate_id(entity_id) is True

    def test_invalid_format(self):
        assert validate_id("not-an-id") is False
        assert validate_id("") is False
        assert validate_id("ct_short") is False
        assert validate_id("CT_01JKXM9V3QWERTY123456ABCDF") is False
