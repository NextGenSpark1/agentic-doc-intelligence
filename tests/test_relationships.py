"""Relationship discovery."""
from backend.pipeline.build_relationships import compute_relationships


def test_finds_shared_bank_account_and_principal(sample_extractions):
    edges = compute_relationships(sample_extractions)
    labels = {e["relationship_type"] for e in edges}
    assert "shared_bank_account" in labels
    assert "shared_principal" in labels


def test_shared_account_links_the_two_vendors(sample_extractions):
    edge = next(e for e in compute_relationships(sample_extractions)
                if e["relationship_type"] == "shared_bank_account")
    assert {edge["source_name"], edge["target_name"]} == {"Nova Build", "Apex Supplies"}
