#!/usr/bin/env python3
"""Validate the CRM example app.

Loads the manifest, creates sample entities, validates them against
schemas, and verifies CRUD operations work end-to-end.

Usage:
    cd examples/crm
    uv run --project ../../lib python validate.py
"""

import json
import sys
import tempfile
from pathlib import Path

from upjack import UpjackApp

EXAMPLE_DIR = Path(__file__).parent


def main() -> int:
    errors: list[str] = []

    # Load app from manifest
    print("Loading CRM manifest...")
    app = UpjackApp.from_manifest(EXAMPLE_DIR / "manifest.json", root=tempfile.mkdtemp())

    # Verify all entity types loaded
    expected_types = {"contact", "company", "deal", "pipeline", "activity"}
    actual_types = set(app._entities.keys())
    if actual_types != expected_types:
        errors.append(f"Entity types mismatch: expected {expected_types}, got {actual_types}")
    print(f"  Entity types: {sorted(actual_types)}")

    # Verify schemas loaded
    print(f"  Schemas loaded: {sorted(app._schemas.keys())}")

    # Create a contact
    print("\nCreating contact...")
    contact = app.create_entity("contact", {
        "first_name": "Test",
        "last_name": "User",
        "email": "test@example.com",
        "title": "Engineer",
        "lead_score": 50,
        "lifecycle_stage": "lead",
    })
    assert contact["type"] == "contact"
    assert contact["id"].startswith("ct_")
    assert contact["first_name"] == "Test"
    assert contact["status"] == "active"
    print(f"  Created: {contact['id']}")

    # Create a company
    print("Creating company...")
    company = app.create_entity("company", {
        "name": "Test Corp",
        "industry": "Technology",
        "size": "51-200",
    })
    assert company["id"].startswith("co_")
    print(f"  Created: {company['id']}")

    # Create a deal
    print("Creating deal...")
    deal = app.create_entity("deal", {
        "title": "Test Deal",
        "stage": "Prospecting",
        "value": 10000,
        "probability": 10,
        "relationships": [
            {"rel": "primary_contact", "target": contact["id"]},
            {"rel": "company", "target": company["id"]},
        ],
    })
    assert deal["id"].startswith("dl_")
    assert len(deal["relationships"]) == 2
    print(f"  Created: {deal['id']}")

    # Validate graph traversal — get_related forward
    print("\nValidating graph traversal...")
    print("  get_related (forward)...")
    related_fwd = app.get_related(deal["id"], direction="forward")
    related_fwd_ids = {r["id"] for r in related_fwd}
    if contact["id"] not in related_fwd_ids:
        errors.append(f"get_related forward missing contact {contact['id']}")
    if company["id"] not in related_fwd_ids:
        errors.append(f"get_related forward missing company {company['id']}")
    print(f"    Found {len(related_fwd)} related entities")

    # Validate graph traversal — query_by_relationship
    print("  query_by_relationship (deal->company)...")
    deals_for_company = app.query_by_relationship("deal", "company", company["id"])
    deals_for_company_ids = {d["id"] for d in deals_for_company}
    if deal["id"] not in deals_for_company_ids:
        errors.append(f"query_by_relationship did not find deal {deal['id']} for company {company['id']}")
    print(f"    Found {len(deals_for_company)} deal(s) for company")

    # Validate graph traversal — get_composite
    print("  get_composite (deal)...")
    composite = app.get_composite("deal", deal["id"])
    composite_related = composite.get("_related", {})
    composite_contact_ids = {r["id"] for r in composite_related.get("primary_contact", [])}
    composite_company_ids = {r["id"] for r in composite_related.get("company", [])}
    if contact["id"] not in composite_contact_ids:
        errors.append(f"get_composite _related missing contact under primary_contact")
    if company["id"] not in composite_company_ids:
        errors.append(f"get_composite _related missing company under company")
    print(f"    _related keys: {sorted(composite_related.keys())}")

    # Validate rebuild_index
    print("  rebuild_index...")
    from upjack.relations import rebuild_index
    index = rebuild_index(app.root, app.namespace, app._entity_defs_list())
    index_entry_count = sum(len(v) for v in index.values())
    if index_entry_count < 2:
        errors.append(f"rebuild_index returned only {index_entry_count} entries, expected at least 2")
    print(f"    Index entries: {index_entry_count}")

    # Create a pipeline (singleton)
    print("Creating pipeline...")
    pipeline_data = json.loads((EXAMPLE_DIR / "seed" / "default-pipeline.json").read_text())
    pipeline_data.pop("type", None)
    pipeline_data.pop("version", None)
    pipeline = app.create_entity("pipeline", pipeline_data)
    assert pipeline["id"].startswith("pl_")
    assert len(pipeline["stages"]) == 6
    print(f"  Created: {pipeline['id']} ({len(pipeline['stages'])} stages)")

    # Create an activity
    print("Creating activity...")
    activity = app.create_entity("activity", {
        "activity_type": "note",
        "subject": "Initial qualification",
        "body": "Test User looks promising. VP title, mid-size company.",
        "relationships": [
            {"rel": "contact", "target": contact["id"]},
        ],
    })
    assert activity["id"].startswith("act_")
    print(f"  Created: {activity['id']}")

    # Update contact with lead score
    print("\nUpdating contact lead score...")
    updated = app.update_entity("contact", contact["id"], {"lead_score": 75})
    assert updated["lead_score"] == 75
    assert updated["first_name"] == "Test"  # merge preserved existing fields
    print(f"  Updated: lead_score = {updated['lead_score']}")

    # List entities
    print("\nListing contacts...")
    contacts = app.list_entities("contact")
    assert len(contacts) == 1
    print(f"  Found: {len(contacts)} contact(s)")

    # Get entity
    print("Getting deal...")
    fetched = app.get_entity("deal", deal["id"])
    assert fetched["title"] == "Test Deal"
    print(f"  Fetched: {fetched['title']}")

    # Soft delete
    print("Soft-deleting activity...")
    deleted = app.delete_entity("activity", activity["id"])
    assert deleted["status"] == "deleted"
    print(f"  Deleted: {deleted['id']} (status={deleted['status']})")

    # Verify deleted entity doesn't appear in active list
    activities = app.list_entities("activity", status="active")
    assert len(activities) == 0
    print(f"  Active activities: {len(activities)}")

    # Schema validation: should reject invalid data
    print("\nTesting schema validation...")
    try:
        app.create_entity("contact", {"email": "missing-names@example.com"})
        errors.append("Schema validation should have rejected contact without first_name/last_name")
    except Exception:
        print("  Correctly rejected contact missing required fields")

    try:
        app.create_entity("contact", {
            "first_name": "Bad",
            "last_name": "Score",
            "lead_score": 150,  # max is 100
        })
        errors.append("Schema validation should have rejected lead_score > 100")
    except Exception:
        print("  Correctly rejected lead_score > 100")

    try:
        app.create_entity("deal", {"title": "No Stage"})
        errors.append("Schema validation should have rejected deal without stage")
    except Exception:
        print("  Correctly rejected deal missing required stage")

    # Results
    print()
    if errors:
        print(f"FAILED — {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    else:
        print("PASSED — CRM example validates successfully")
        return 0


if __name__ == "__main__":
    sys.exit(main())
