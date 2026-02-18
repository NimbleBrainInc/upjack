"""Tests for the upjack CLI."""

import json
from unittest.mock import patch

import pytest

from upjack.cli import _make_prefix, _slugify, init, main


class TestSlugify:
    def test_basic(self):
        assert _slugify("My App") == "my-app"

    def test_already_slug(self):
        assert _slugify("my-app") == "my-app"

    def test_trailing_spaces(self):
        assert _slugify(" hello world ") == "hello-world"


class TestMakePrefix:
    def test_short_name(self):
        # 4-char name stays as-is (valid 2-4 char prefix)
        assert _make_prefix("note") == "note"

    def test_two_char(self):
        assert _make_prefix("ab") == "ab"

    def test_long_name(self):
        prefix = _make_prefix("contact")
        assert 2 <= len(prefix) <= 4
        assert prefix.isalpha()
        assert prefix.islower()


class TestInit:
    def test_creates_directory_structure(self, tmp_path):
        target = tmp_path / "my-app"
        args = type("Args", (), {"directory": str(target), "name": "my-app", "entity": "note"})()
        init(args)

        assert (target / "manifest.json").exists()
        assert (target / "server.py").exists()
        assert (target / "context.md").exists()
        assert (target / "schemas" / "note.schema.json").exists()
        assert (target / "seed" / "sample-notes.json").exists()
        assert (target / "skills").is_dir()

    def test_manifest_content(self, tmp_path):
        target = tmp_path / "test-app"
        args = type("Args", (), {"directory": str(target), "name": "test-app", "entity": "task"})()
        init(args)

        manifest = json.loads((target / "manifest.json").read_text())
        assert manifest["name"] == "test-app"
        assert manifest["title"] == "Test App"

        upjack = manifest["_meta"]["ai.nimblebrain/upjack"]
        assert upjack["namespace"] == "apps/test-app"
        assert len(upjack["entities"]) == 1
        assert upjack["entities"][0]["name"] == "task"
        assert upjack["entities"][0]["prefix"] == "task"

    def test_schema_is_valid_json_schema(self, tmp_path):
        target = tmp_path / "app"
        args = type("Args", (), {"directory": str(target), "name": "app", "entity": "item"})()
        init(args)

        schema = json.loads((target / "schemas" / "item.schema.json").read_text())
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert "allOf" in schema
        assert "name" in schema["required"]

    def test_server_py_content(self, tmp_path):
        target = tmp_path / "app"
        args = type("Args", (), {"directory": str(target), "name": "app", "entity": "item"})()
        init(args)

        server_content = (target / "server.py").read_text()
        assert "create_server" in server_content
        assert "manifest.json" in server_content

    def test_refuses_nonempty_directory(self, tmp_path):
        target = tmp_path / "existing"
        target.mkdir()
        (target / "file.txt").write_text("exists")

        args = type("Args", (), {"directory": str(target), "name": "existing", "entity": "item"})()
        with pytest.raises(SystemExit):
            init(args)

    def test_generated_app_loads(self, tmp_path):
        """The generated app should be loadable by UpjackApp."""
        from upjack import UpjackApp

        target = tmp_path / "app"
        args = type("Args", (), {"directory": str(target), "name": "app", "entity": "note"})()
        init(args)

        app = UpjackApp.from_manifest(target / "manifest.json", root=tmp_path)
        note = app.create_entity("note", {"name": "Test"})
        assert note["type"] == "note"
        assert note["name"] == "Test"
        assert note["id"].startswith("note_")


class TestMainEntrypoint:
    def test_no_command_exits(self):
        with patch("sys.argv", ["upjack"]):
            with pytest.raises(SystemExit):
                main()

    def test_init_command(self, tmp_path):
        target = tmp_path / "cli-test"
        with patch(
            "sys.argv", ["upjack", "init", str(target), "--name", "cli-test", "--entity", "item"]
        ):
            main()
        assert (target / "manifest.json").exists()
