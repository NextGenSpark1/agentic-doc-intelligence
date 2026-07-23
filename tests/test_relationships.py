"""Relationship discovery."""
from backend.pipeline.build_relationships import _dedupe_llm_edges, compute_relationships


def test_finds_shared_bank_account_and_principal(sample_extractions):
    edges = compute_relationships(sample_extractions)
    labels = {e["relationship_type"] for e in edges}
    assert "shared_bank_account" in labels
    assert "shared_principal" in labels


def test_llm_edge_duplicating_a_rule_edge_is_dropped():
    """A provable rule edge must not be suppressed by an LLM edge asserting the same tie —
    the LLM duplicate is dropped (reversed pair + different casing still collide)."""
    rule = [{"source_name": "Nova Build", "target_name": "Apex Supplies",
             "relationship_type": "shared_bank_account", "source": "rule"}]
    llm = [{"source_name": "apex supplies", "target_name": "nova build",
            "relationship_type": "Shared_Bank_Account", "source": "llm"}]
    assert _dedupe_llm_edges(llm, rule) == []


def test_llm_edge_with_new_relationship_survives():
    """Rules and LLM run together: a genuinely new LLM edge is kept alongside the rule edge."""
    rule = [{"source_name": "Nova Build", "target_name": "Apex Supplies",
             "relationship_type": "shared_bank_account", "source": "rule"}]
    llm = [{"source_name": "Nova Build", "target_name": "Apex Supplies",
            "relationship_type": "introduced_by", "source": "llm"}]
    kept = _dedupe_llm_edges(llm, rule)
    assert len(kept) == 1
    assert kept[0]["relationship_type"] == "introduced_by"


def test_shared_account_links_the_two_vendors(sample_extractions):
    edge = next(e for e in compute_relationships(sample_extractions)
                if e["relationship_type"] == "shared_bank_account")
    assert {edge["source_name"], edge["target_name"]} == {"Nova Build", "Apex Supplies"}
