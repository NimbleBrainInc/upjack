"""Integration tests using real example manifests and schemas.

These tests validate that the upjack library works correctly with the
actual CRM, Research Assistant, and Todo example apps — real schemas, real seed
data, real manifest structure. For true end-to-end MCPB bundle tests, see e2e/.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError

from upjack.app import UpjackApp
from upjack.server import create_server

# Resolve example directories relative to this file
# lib/python/tests/test_e2e.py -> lib/python/ -> lib/ -> code/
_CODE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CRM_DIR = _CODE_ROOT / "examples" / "crm"
RESEARCH_DIR = _CODE_ROOT / "examples" / "research-assistant"
TODO_DIR = _CODE_ROOT / "examples" / "todo"


def _run(coro):
    return asyncio.run(coro)


async def _list_tool_names(mcp) -> set[str]:
    from fastmcp import Client

    async with Client(mcp) as client:
        tools = await client.list_tools()
        return {t.name for t in tools}


async def _call_tool(mcp, name: str, arguments: dict | None = None) -> Any:
    from fastmcp import Client

    async with Client(mcp) as client:
        result = await client.call_tool(name, arguments or {})
        if not result.content:
            return None
        return json.loads(result.content[0].text)


async def _list_resource_uris(mcp) -> set[str]:
    from fastmcp import Client

    async with Client(mcp) as client:
        resources = await client.list_resources()
        return {str(r.uri) for r in resources}


# ===========================================================================
# CRM E2E Tests — UpjackApp level
# ===========================================================================


class TestCrmApp:
    """E2E tests using the real CRM manifest and schemas."""

    @pytest.fixture
    def crm(self, tmp_path):
        return UpjackApp.from_manifest(CRM_DIR / "manifest.json", root=tmp_path)

    def test_loads_all_entity_types(self, crm):
        """Manifest defines 5 entity types; all should be usable."""
        for entity_type in ["contact", "company", "deal", "pipeline", "activity"]:
            assert entity_type in crm._entities

    def test_schemas_loaded_for_all_entities(self, crm):
        """All 5 schemas should be loaded from disk."""
        for entity_type in ["contact", "company", "deal", "pipeline", "activity"]:
            assert entity_type in crm._schemas, f"Schema missing for {entity_type}"

    def test_create_contact_with_valid_data(self, crm):
        contact = crm.create_entity(
            "contact",
            {
                "first_name": "Alice",
                "last_name": "Chen",
                "email": "alice@example.com",
                "lead_score": 85,
                "lifecycle_stage": "lead",
            },
        )
        assert contact["id"].startswith("ct_")
        assert contact["first_name"] == "Alice"
        assert contact["lead_score"] == 85
        assert contact["status"] == "active"

    def test_contact_requires_first_and_last_name(self, crm):
        """Contact schema requires first_name and last_name."""
        with pytest.raises(ValidationError):
            crm.create_entity("contact", {"email": "no-name@example.com"})

        with pytest.raises(ValidationError):
            crm.create_entity("contact", {"first_name": "Alice"})  # missing last_name

    def test_contact_lead_score_bounded(self, crm):
        """lead_score must be 0-100."""
        with pytest.raises(ValidationError):
            crm.create_entity(
                "contact",
                {
                    "first_name": "Alice",
                    "last_name": "Chen",
                    "lead_score": 150,
                },
            )

        with pytest.raises(ValidationError):
            crm.create_entity(
                "contact",
                {
                    "first_name": "Alice",
                    "last_name": "Chen",
                    "lead_score": -10,
                },
            )

    def test_contact_lifecycle_stage_enum(self, crm):
        """lifecycle_stage must be one of the defined values."""
        with pytest.raises(ValidationError):
            crm.create_entity(
                "contact",
                {
                    "first_name": "Alice",
                    "last_name": "Chen",
                    "lifecycle_stage": "invalid_stage",
                },
            )

    def test_create_deal_with_valid_data(self, crm):
        deal = crm.create_entity(
            "deal",
            {
                "title": "Enterprise License",
                "stage": "qualification",
                "value": 50000,
                "probability": 30,
            },
        )
        assert deal["id"].startswith("dl_")
        assert deal["title"] == "Enterprise License"
        assert deal["value"] == 50000

    def test_deal_requires_title_and_stage(self, crm):
        with pytest.raises(ValidationError):
            crm.create_entity("deal", {"value": 10000})

    def test_deal_value_non_negative(self, crm):
        with pytest.raises(ValidationError):
            crm.create_entity(
                "deal",
                {
                    "title": "Bad Deal",
                    "stage": "new",
                    "value": -1000,
                },
            )

    def test_create_company(self, crm):
        company = crm.create_entity(
            "company",
            {
                "name": "Acme Corp",
                "domain": "acme.com",
                "industry": "Technology",
            },
        )
        assert company["id"].startswith("co_")

    def test_create_activity(self, crm):
        activity = crm.create_entity(
            "activity",
            {
                "activity_type": "email",
                "subject": "Follow-up on demo",
            },
        )
        assert activity["id"].startswith("act_")

    def test_create_pipeline_singleton(self, crm):
        pipeline = crm.create_entity(
            "pipeline",
            {
                "stages": [
                    {"name": "Prospecting", "order": 1, "probability": 10},
                    {"name": "Qualification", "order": 2, "probability": 25},
                ],
            },
        )
        assert pipeline["id"].startswith("pl_")

    def test_pipeline_requires_stages(self, crm):
        with pytest.raises(ValidationError):
            crm.create_entity("pipeline", {"name": "Empty Pipeline"})

    def test_full_crud_cycle(self, crm):
        """Complete create → read → update → search → list → delete cycle."""
        # Create
        contact = crm.create_entity(
            "contact",
            {
                "first_name": "Bob",
                "last_name": "Smith",
                "email": "bob@example.com",
                "lead_score": 60,
            },
        )

        # Read
        fetched = crm.get_entity("contact", contact["id"])
        assert fetched["first_name"] == "Bob"
        assert fetched["email"] == "bob@example.com"

        # Update (merge)
        updated = crm.update_entity("contact", contact["id"], {"lead_score": 90})
        assert updated["lead_score"] == 90
        assert updated["first_name"] == "Bob"  # preserved
        assert updated["email"] == "bob@example.com"  # preserved

        # Search
        results = crm.search_entities("contact", query="Bob")
        assert len(results) == 1
        assert results[0]["lead_score"] == 90

        # List
        all_contacts = crm.list_entities("contact")
        assert len(all_contacts) == 1

        # Delete
        deleted = crm.delete_entity("contact", contact["id"])
        assert deleted["status"] == "deleted"

        # Verify excluded from list
        active = crm.list_entities("contact")
        assert len(active) == 0

    def test_multiple_entity_types_coexist(self, crm):
        """Different entity types should not interfere with each other."""
        crm.create_entity("contact", {"first_name": "A", "last_name": "B"})
        crm.create_entity("company", {"name": "Acme"})
        crm.create_entity("deal", {"title": "Big Deal", "stage": "new"})

        assert len(crm.list_entities("contact")) == 1
        assert len(crm.list_entities("company")) == 1
        assert len(crm.list_entities("deal")) == 1

    def test_search_with_structured_filter(self, crm):
        crm.create_entity(
            "contact",
            {
                "first_name": "Alice",
                "last_name": "A",
                "lead_score": 90,
            },
        )
        crm.create_entity(
            "contact",
            {
                "first_name": "Bob",
                "last_name": "B",
                "lead_score": 40,
            },
        )
        crm.create_entity(
            "contact",
            {
                "first_name": "Charlie",
                "last_name": "C",
                "lead_score": 75,
            },
        )

        hot_leads = crm.search_entities(
            "contact", filter={"lead_score": {"$gte": 70}}, sort="-lead_score"
        )
        assert len(hot_leads) == 2
        assert hot_leads[0]["first_name"] == "Alice"
        assert hot_leads[1]["first_name"] == "Charlie"


# ===========================================================================
# Research Assistant E2E Tests
# ===========================================================================


class TestResearchApp:
    """E2E tests using the real Research Assistant manifest and schemas."""

    @pytest.fixture
    def research(self, tmp_path):
        return UpjackApp.from_manifest(RESEARCH_DIR / "manifest.json", root=tmp_path)

    def test_loads_all_entity_types(self, research):
        for entity_type in ["topic", "source", "note", "report"]:
            assert entity_type in research._entities

    def test_create_topic(self, research):
        topic = research.create_entity(
            "topic",
            {
                "title": "AI Agent Architectures",
                "priority": "high",
                "key_questions": ["How do agents coordinate?", "What are failure modes?"],
            },
        )
        assert topic["id"].startswith("top_")
        assert topic["title"] == "AI Agent Architectures"

    def test_topic_requires_title(self, research):
        with pytest.raises(ValidationError):
            research.create_entity("topic", {"priority": "high"})

    def test_topic_priority_enum(self, research):
        with pytest.raises(ValidationError):
            research.create_entity(
                "topic",
                {
                    "title": "Test",
                    "priority": "ultra-critical",
                },
            )

    def test_create_source(self, research):
        source = research.create_entity(
            "source",
            {
                "title": "MCP Protocol Specification",
                "url": "https://modelcontextprotocol.io",
                "source_type": "whitepaper",
                "credibility": 5,
            },
        )
        assert source["id"].startswith("src_")

    def test_create_note(self, research):
        note = research.create_entity(
            "note",
            {
                "content": "MCP uses JSON-RPC 2.0 for communication between host and server.",
                "claim_type": "fact",
                "confidence": "high",
            },
        )
        assert note["id"].startswith("nt_")

    def test_create_report(self, research):
        report = research.create_entity(
            "report",
            {
                "title": "MCP Adoption Survey",
                "body": "This report covers...",
                "executive_summary": "MCP adoption is growing rapidly.",
            },
        )
        assert report["id"].startswith("rpt_")

    def test_full_research_workflow(self, research):
        """Simulate a research workflow: topic → sources → notes → report."""
        research.create_entity(
            "topic",
            {
                "title": "MCP Protocol Adoption",
                "priority": "high",
            },
        )

        research.create_entity(
            "source",
            {
                "title": "MCP Spec v1.0",
                "source_type": "whitepaper",
            },
        )

        research.create_entity(
            "note",
            {
                "content": "MCP enables standardized tool communication for AI agents.",
            },
        )

        research.create_entity(
            "report",
            {
                "title": "MCP Analysis",
                "body": "Based on our research...",
            },
        )

        # All should coexist
        assert len(research.list_entities("topic")) == 1
        assert len(research.list_entities("source")) == 1
        assert len(research.list_entities("note")) == 1
        assert len(research.list_entities("report")) == 1

        # Search across types
        assert len(research.search_entities("topic", query="MCP")) == 1
        assert len(research.search_entities("source", query="MCP")) == 1


# ===========================================================================
# Server-level E2E Tests
# ===========================================================================


class TestCrmServer:
    """E2E tests for a server created from the CRM manifest."""

    @pytest.fixture
    def mcp(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        return create_server(CRM_DIR / "manifest.json", root=workspace)

    def test_registers_all_crm_tools(self, mcp):
        tools = _run(_list_tool_names(mcp))

        # 5 entity types × 6 tools = 30 + seed_data = 31
        expected_entity_tools = set()
        for name, plural in [
            ("contact", "contacts"),
            ("company", "companies"),
            ("deal", "deals"),
            ("pipeline", "pipelines"),
            ("activity", "activities"),
        ]:
            expected_entity_tools |= {
                f"create_{name}",
                f"get_{name}",
                f"update_{name}",
                f"list_{plural}",
                f"search_{plural}",
                f"delete_{name}",
            }

        for tool in expected_entity_tools:
            assert tool in tools, f"Missing tool: {tool}"
        assert "seed_data" in tools

    def test_registers_context_and_skill_resources(self, mcp):
        uris = _run(_list_resource_uris(mcp))
        assert "upjack://context" in uris
        assert "upjack://skills/lead-qualification" in uris
        assert "upjack://skills/deal-forecasting" in uris
        assert "upjack://skills/follow-up-email" in uris

    def test_create_contact_through_tool(self, mcp):
        result = _run(
            _call_tool(
                mcp,
                "create_contact",
                {
                    "data": {"first_name": "Sarah", "last_name": "Chen"},
                },
            )
        )
        assert result["id"].startswith("ct_")
        assert result["first_name"] == "Sarah"

    def test_seed_data_loads_crm_samples(self, mcp):
        result = _run(_call_tool(mcp, "seed_data"))
        # CRM seed has: 1 pipeline, 1 company, 2 contacts, 1 deal = 5 total
        assert len(result["loaded"]) == 5
        assert result["errors"] == []

        # Verify entities actually exist
        contacts = _run(_call_tool(mcp, "list_contacts", {}))
        assert len(contacts) == 2

    def test_server_name_is_crm(self, mcp):
        assert mcp.name == "CRM"


class TestResearchServer:
    """E2E tests for a server created from the Research Assistant manifest."""

    @pytest.fixture
    def mcp(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        return create_server(RESEARCH_DIR / "manifest.json", root=workspace)

    def test_registers_all_research_tools(self, mcp):
        tools = _run(_list_tool_names(mcp))

        for name, plural in [
            ("topic", "topics"),
            ("source", "sources"),
            ("note", "notes"),
            ("report", "reports"),
        ]:
            assert f"create_{name}" in tools
            assert f"list_{plural}" in tools

    def test_seed_data_loads_research_samples(self, mcp):
        result = _run(_call_tool(mcp, "seed_data"))
        # Research seed has 2 topics
        assert len(result["loaded"]) == 2
        assert result["errors"] == []

    def test_server_name_is_research_assistant(self, mcp):
        assert mcp.name == "Research Assistant"


# ===========================================================================
# Todo E2E Tests — UpjackApp level
# ===========================================================================


class TestTodoApp:
    """E2E tests using the real Todo manifest and schemas."""

    @pytest.fixture
    def todo(self, tmp_path):
        return UpjackApp.from_manifest(TODO_DIR / "manifest.json", root=tmp_path)

    def test_loads_all_entity_types(self, todo):
        """Manifest defines 3 entity types; all should be usable."""
        for entity_type in ["task", "project", "label"]:
            assert entity_type in todo._entities

    def test_schemas_loaded_for_all_entities(self, todo):
        """All 3 schemas should be loaded from disk."""
        for entity_type in ["task", "project", "label"]:
            assert entity_type in todo._schemas, f"Schema missing for {entity_type}"

    def test_create_task_with_valid_data(self, todo):
        task = todo.create_entity(
            "task",
            {
                "title": "Write unit tests",
                "description": "Cover all edge cases",
                "priority": "high",
                "due_date": "2026-03-01",
                "effort": "medium",
            },
        )
        assert task["id"].startswith("tsk_")
        assert task["title"] == "Write unit tests"
        assert task["priority"] == "high"
        assert task["status"] == "active"

    def test_task_requires_title(self, todo):
        """Task schema requires title."""
        with pytest.raises(ValidationError):
            todo.create_entity("task", {"priority": "high"})

    def test_task_priority_enum(self, todo):
        """priority must be one of the defined values."""
        with pytest.raises(ValidationError):
            todo.create_entity(
                "task",
                {
                    "title": "Bad priority",
                    "priority": "ultra-critical",
                },
            )

    def test_task_effort_enum(self, todo):
        """effort must be one of the defined values."""
        with pytest.raises(ValidationError):
            todo.create_entity(
                "task",
                {
                    "title": "Bad effort",
                    "effort": "enormous",
                },
            )

    def test_create_project_with_valid_data(self, todo):
        project = todo.create_entity(
            "project",
            {
                "name": "Q1 Planning",
                "description": "Quarterly planning and goal-setting",
                "color": "#3B82F6",
                "due_date": "2026-03-31",
            },
        )
        assert project["id"].startswith("prj_")
        assert project["name"] == "Q1 Planning"

    def test_project_requires_name(self, todo):
        with pytest.raises(ValidationError):
            todo.create_entity("project", {"description": "No name"})

    def test_project_color_pattern(self, todo):
        """color must be a valid hex color."""
        with pytest.raises(ValidationError):
            todo.create_entity(
                "project",
                {
                    "name": "Bad Color",
                    "color": "not-a-color",
                },
            )

    def test_create_label_with_valid_data(self, todo):
        label = todo.create_entity(
            "label",
            {
                "name": "bug",
                "color": "#EF4444",
                "description": "Something broken",
            },
        )
        assert label["id"].startswith("lbl_")
        assert label["name"] == "bug"

    def test_label_requires_name(self, todo):
        with pytest.raises(ValidationError):
            todo.create_entity("label", {"color": "#EF4444"})

    def test_full_crud_cycle(self, todo):
        """Complete create → read → update → search → list → delete cycle."""
        # Create
        task = todo.create_entity(
            "task",
            {
                "title": "Review docs",
                "priority": "medium",
                "effort": "small",
            },
        )

        # Read
        fetched = todo.get_entity("task", task["id"])
        assert fetched["title"] == "Review docs"
        assert fetched["priority"] == "medium"

        # Update (merge)
        updated = todo.update_entity("task", task["id"], {"priority": "high"})
        assert updated["priority"] == "high"
        assert updated["title"] == "Review docs"  # preserved
        assert updated["effort"] == "small"  # preserved

        # Search
        results = todo.search_entities("task", query="Review")
        assert len(results) == 1
        assert results[0]["priority"] == "high"

        # List
        all_tasks = todo.list_entities("task")
        assert len(all_tasks) == 1

        # Delete
        deleted = todo.delete_entity("task", task["id"])
        assert deleted["status"] == "deleted"

        # Verify excluded from list
        active = todo.list_entities("task")
        assert len(active) == 0

    def test_multiple_entity_types_coexist(self, todo):
        """Different entity types should not interfere with each other."""
        todo.create_entity("task", {"title": "Do something"})
        todo.create_entity("project", {"name": "My Project"})
        todo.create_entity("label", {"name": "urgent"})

        assert len(todo.list_entities("task")) == 1
        assert len(todo.list_entities("project")) == 1
        assert len(todo.list_entities("label")) == 1

    def test_search_with_structured_filter(self, todo):
        todo.create_entity(
            "task",
            {"title": "Critical bug fix", "priority": "critical", "effort": "small"},
        )
        todo.create_entity(
            "task",
            {"title": "Write docs", "priority": "low", "effort": "medium"},
        )
        todo.create_entity(
            "task",
            {"title": "Deploy release", "priority": "high", "effort": "small"},
        )

        high_priority = todo.search_entities(
            "task",
            filter={"priority": {"$in": ["critical", "high"]}},
        )
        assert len(high_priority) == 2
        titles = {t["title"] for t in high_priority}
        assert titles == {"Critical bug fix", "Deploy release"}

    def test_task_with_project_name_denormalized(self, todo):
        """project_name is a denormalized field on task."""
        task = todo.create_entity(
            "task",
            {
                "title": "Update README",
                "project_name": "Documentation",
            },
        )
        fetched = todo.get_entity("task", task["id"])
        assert fetched["project_name"] == "Documentation"


# ===========================================================================
# Todo Server-level E2E Tests
# ===========================================================================


class TestTodoServer:
    """E2E tests for a server created from the Todo manifest."""

    @pytest.fixture
    def mcp(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        return create_server(TODO_DIR / "manifest.json", root=workspace)

    def test_registers_all_todo_tools(self, mcp):
        tools = _run(_list_tool_names(mcp))

        # 3 entity types × 6 tools = 18 + seed_data = 19
        expected_entity_tools = set()
        for name, plural in [
            ("task", "tasks"),
            ("project", "projects"),
            ("label", "labels"),
        ]:
            expected_entity_tools |= {
                f"create_{name}",
                f"get_{name}",
                f"update_{name}",
                f"list_{plural}",
                f"search_{plural}",
                f"delete_{name}",
            }

        for tool in expected_entity_tools:
            assert tool in tools, f"Missing tool: {tool}"
        assert "seed_data" in tools

    def test_registers_context_and_skill_resources(self, mcp):
        uris = _run(_list_resource_uris(mcp))
        assert "upjack://context" in uris
        assert "upjack://skills/task-management" in uris

    def test_create_task_through_tool(self, mcp):
        result = _run(
            _call_tool(
                mcp,
                "create_task",
                {
                    "data": {"title": "Buy groceries"},
                },
            )
        )
        assert result["id"].startswith("tsk_")
        assert result["title"] == "Buy groceries"

    def test_seed_data_loads_todo_samples(self, mcp):
        result = _run(_call_tool(mcp, "seed_data"))
        # Todo seed has: 4 tasks + 2 projects + 3 labels = 9 total
        assert len(result["loaded"]) == 9
        assert result["errors"] == []

        # Verify entities actually exist
        tasks = _run(_call_tool(mcp, "list_tasks", {}))
        assert len(tasks) == 4

        projects = _run(_call_tool(mcp, "list_projects", {}))
        assert len(projects) == 2

        labels = _run(_call_tool(mcp, "list_labels", {}))
        assert len(labels) == 3

    def test_server_name_is_todo_list(self, mcp):
        assert mcp.name == "Todo List"
