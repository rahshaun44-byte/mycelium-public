#!/usr/bin/env python3
"""
Test Suite: Athena Scientific Continuity & Research Exploration Engine
======================================================================
Validates the Chief Architect's Mandate on Scientific Continuity:
- Verification of 10 mandated scientific knowledge domains:
  Physics, Quantum Information, Mathematics, Computational Science,
  Machine Learning, Computer Science, Hardware/Information Security,
  Communications Engineering, Biotechnology, Neuroscience.
- Ingestion pipeline idempotence and domain metadata integrity.
- Domain-targeted semantic retrieval and cross-domain inquiry.
- Formal hypothesis synthesis with falsification bounds and control experiments.
- Research frontier exploration and interdisciplinary bottleneck detection.
- FastAPI endpoint contracts on Athena Node (:8005 / :8001).
- Fail-closed behavior on invalid inputs or missing parameters.
"""

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sentinel.intelligence.scientific_engine import (
    AthenaScientificEngine,
    MANDATED_DOMAINS,
    chunk_markdown_document,
)
from mcp_layer.athena_api import app


@pytest.fixture(scope="module")
def sci_engine():
    engine = AthenaScientificEngine()
    engine.ingest_scientific_domains(force_refresh=False)
    return engine


@pytest.fixture(scope="module")
def api_client():
    return TestClient(app)


def test_ten_mandated_domains_registered():
    """All 10 required scientific domains are present in registry."""
    expected_domains = [
        "Physics",
        "Quantum Information",
        "Mathematics",
        "Computational Science",
        "Machine Learning",
        "Computer Science",
        "Hardware/Information Security",
        "Communications Engineering",
        "Biotechnology",
        "Neuroscience",
    ]
    for d in expected_domains:
        assert d in MANDATED_DOMAINS, f"Missing mandated domain: {d}"
        assert (ROOT_DIR / "sentinel" / "knowledge_base" / "scientific_domains" / MANDATED_DOMAINS[d]["file"]).is_file()


def test_chunking_preserves_content_and_boundaries():
    """Chunker correctly splits markdown headings without data loss."""
    sample = "# Title\nParagraph 1\n## Section 2\nParagraph 2\n### Sub\nParagraph 3"
    chunks = chunk_markdown_document(sample, chunk_size=50, chunk_overlap=10)
    assert len(chunks) >= 2
    full_recombined = " ".join(chunks)
    assert "Paragraph 1" in full_recombined
    assert "Paragraph 3" in full_recombined


def test_ingestion_pipeline_idempotence(sci_engine):
    """Re-ingesting scientific domains preserves vector store consistency without corruption."""
    res = sci_engine.ingest_scientific_domains(force_refresh=False)
    assert res["domains_processed"] == 10
    assert res["total_chunks_ingested"] >= 10
    for d, meta in res["domain_breakdown"].items():
        assert meta["status"] == "INGESTED"
        assert meta["chunks"] > 0


@pytest.mark.parametrize("domain,query,expected_term", [
    ("Physics", "Landauer's principle minimum energy dissipation", "Landauer"),
    ("Quantum Information", "GHZ state entanglement witness fidelity", "GHZ"),
    ("Mathematics", "Module-LWE lattice cryptography hardness", "LWE"),
    ("Computational Science", "Formal verification F* theorem proving", "Formal"),
    ("Machine Learning", "Transformer unit hypersphere cosine similarity", "Transformer"),
    ("Computer Science", "WebAssembly Wasmtime sandbox in-process gatekeeper", "WebAssembly"),
    ("Hardware/Information Security", "Pluton TPM 2.0 PCR attestation and StrongBox", "Pluton"),
    ("Communications Engineering", "Tailscale WireGuard encrypted mesh loopback", "WireGuard"),
    ("Biotechnology", "Mol* mmCIF 3D macromolecular conformation", "mmCIF"),
    ("Neuroscience", "Leaky integrate-and-fire membrane homeostasis", "Leaky"),
])
def test_domain_targeted_scientific_inquiry(sci_engine, domain, query, expected_term):
    """Domain-filtered inquiries retrieve semantically relevant evidence excerpts."""
    res = sci_engine.scientific_inquiry(query, domain=domain, top_k=2)
    assert res["matches_found"] > 0
    assert res["target_domain"] == domain
    top_match = res["matches"][0]
    assert top_match["domain"] == domain
    assert top_match["similarity_score"] > 0.30
    assert any(expected_term.lower() in m["excerpt"].lower() for m in res["matches"])


def test_scientific_inquiry_empty_query_rejected(sci_engine):
    """Empty query fails closed with error."""
    res = sci_engine.scientific_inquiry("   ", domain="Physics")
    assert "error" in res
    assert res["matches"] == []


def test_hypothesis_synthesis_structure(sci_engine):
    """Synthesizes structured formal hypothesis with falsification criteria and controls."""
    premises = [
        "Cryogenic temperature fluctuations on transmon QPU alter coherence time.",
        "Entanglement witness expectation <W> shifts with dephasing noise.",
    ]
    hypo = sci_engine.synthesize_hypothesis(premises, target_domain="Quantum Information")
    assert hypo["hypothesis_id"].startswith("HYPO-")
    assert hypo["target_domain"] == "Quantum Information"
    assert "null_hypothesis_H0" in hypo["formal_statements"]
    assert "alternative_hypothesis_H1" in hypo["formal_statements"]
    assert len(hypo["proposed_falsification_criteria"]) >= 3
    assert len(hypo["experimental_controls"]) >= 3
    assert len(hypo["grounded_evidence"]["sources_cited"]) > 0


def test_hypothesis_synthesis_invalid_domain_raises(sci_engine):
    """Synthesizing for unverified domain raises ValueError."""
    with pytest.raises(ValueError, match="not recognized in mandated domains"):
        sci_engine.synthesize_hypothesis(["Premise 1"], target_domain="Alchemy")


def test_research_exploration_identifies_intersections(sci_engine):
    """Explores research frontiers across multiple scientific domains."""
    res = sci_engine.explore_research_frontiers("thermodynamic dissipation in neuromorphic hardware")
    assert res["domains_analyzed"] == 10
    assert len(res["frontier_intersections"]) > 0
    assert len(res["identified_cross_domain_bottlenecks"]) >= 3
    assert len(res["suggested_experimental_protocols"]) >= 3


def test_fastapi_scientific_domains_endpoint(api_client):
    """GET /scientific/domains returns catalog of 10 domains."""
    resp = api_client.get("/scientific/domains")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["mandated_domains"]) == 10
    assert "Physics" in data["mandated_domains"]
    assert "Neuroscience" in data["mandated_domains"]


def test_fastapi_scientific_inquiry_endpoint(api_client):
    """POST /scientific/inquiry executes valid query."""
    resp = api_client.post(
        "/scientific/inquiry",
        json={"query": "Pluton TPM 2.0 PCR attestation", "domain": "Hardware/Information Security", "top_k": 2},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["target_domain"] == "Hardware/Information Security"
    assert data["matches_found"] > 0


def test_fastapi_hypothesis_synthesis_endpoint(api_client):
    """POST /scientific/hypothesis_synthesis validates input and returns hypothesis."""
    resp = api_client.post(
        "/scientific/hypothesis_synthesis",
        json={
            "premises": ["Landauer limit imposes lower bound on bit erasure energy."],
            "target_domain": "Physics",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "hypothesis_id" in data
    assert "formal_statements" in data


def test_fastapi_hypothesis_synthesis_invalid_domain(api_client):
    """POST /scientific/hypothesis_synthesis rejects unknown domain with 400."""
    resp = api_client.post(
        "/scientific/hypothesis_synthesis",
        json={"premises": ["Premise"], "target_domain": "Astrology"},
    )
    assert resp.status_code == 400
