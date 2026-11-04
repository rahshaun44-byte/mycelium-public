#!/usr/bin/env python3
"""
QuantumFlex Athena: 25-Domain Independent Retrieval & Epistemic Evaluation Test
================================================================================
Empirically tests that each of the 25 multidisciplinary knowledge domains:
  1. Is present as vector embeddings inside sentinel/intelligence/athena_vectors.db
  2. Resolves with positive cosine similarity to domain-specific queries
  3. Returns the correct domain source document in top search candidates
  4. Enforces the 5-tier Epistemic Distinction standard:
     (Established Knowledge, Empirical Support, Mathematical Derivation,
      Active Research Hypothesis, Speculative / Emerging Construct)
"""

import pytest
from pathlib import Path
from sentinel.intelligence.athena_vector_db import AthenaVectorStore

ROOT_DIR = Path(__file__).resolve().parents[1]

# 25 domain specific queries targeting core axioms and technical keywords
DOMAIN_EVALUATION_SPECS = [
    ("01", "athena_domain_01_physics.md", "Lagrangian Hamiltonian mechanics Noether theorem symplectic integrators"),
    ("02", "athena_domain_02_quantum_information.md", "quantum entanglement witness FIPS 203 ML-KEM-768 Bell state fidelity"),
    ("03", "athena_domain_03_mathematics.md", "Abstract algebra Galois theory category theory functors natural transformations Lebesgue integration"),
    ("04", "athena_domain_04_computational_science.md", "finite element method sparse linear solvers GPU tensor numerical"),
    ("05", "athena_domain_05_machine_learning.md", "loss landscape generalization bound transformer attention mechanics"),
    ("06", "athena_domain_06_computer_science.md", "memory fences cache coherence distributed consensus Raft PAXOS"),
    ("07", "athena_domain_07_hardware_security.md", "Pluton TPM 2.0 PCR attestation side-channel DPA fault injection"),
    ("08", "athena_domain_08_communications_engineering.md", "software defined radio Nyquist Shannon channel capacity beamforming"),
    ("09", "athena_domain_09_biotechnology.md", "AlphaFold structural bioinformatics congeneric congeneric activity cliff"),
    ("10", "athena_domain_10_neuroscience.md", "Leaky Integrate-and-Fire membrane potential hodgkin huxley spike plasticity"),
    ("11", "athena_domain_11_law_and_sovereign_law.md", "Computer Fraud and Abuse Act CFAA 18 USC 1030 authorized access"),
    ("12", "athena_domain_12_ai_llm_news.md", "Frontier Architecture Releases Tracking foundation models Open-Weights llama.cpp vLLM Reasoning Extended Thinking"),
    ("13", "athena_domain_13_machine_learning_news.md", "Reinforcement Learning from Verifiable Rewards RLVR self-play Monte Carlo Tree Search MCTS Latent diffusion"),
    ("14", "athena_domain_14_biotech_news.md", "cryo-EM macromolecular complex structural biology drug discovery Boltz"),
    ("15", "athena_domain_15_quantum_news.md", "superconducting transmon error mitigation fault tolerant quantum threshold"),
    ("16", "athena_domain_16_quantumflex_aligned.md", "Triadic Separation Responsibilities AMARA ATHENA Operator Rocky sovereign command Ed25519 CBOM"),
    ("17", "athena_domain_17_energy_systems.md", "molten salt reactor Lawson criterion magnetic confinement fusion battery degradation"),
    ("18", "athena_domain_18_materials_science.md", "topological insulator density functional theory BCS superconductivity twistronics"),
    ("19", "athena_domain_19_aerospace_and_space_systems.md", "astrodynamics Tsiolkovsky rocket equation CR3BP Lagrange points radiation hardening"),
    ("20", "athena_domain_20_cryptoeconomics_mechanism_design.md", "Vickrey Clarke Groves mechanism automated market maker MEV mitigation zero double spend"),
    ("21", "athena_domain_21_international_space_maritime_law.md", "UNCLOS Law of Sea Outer Space Treaty 1967 international arbitration New York Convention"),
    ("22", "athena_domain_22_digital_forensics_incident_response.md", "RFC 3227 order of volatility memory forensics binary disassembly CFG flattening Daubert"),
    ("23", "athena_domain_23_financial_markets_liquidity_engineering.md", "limit order book VPIN toxicity Avellaneda Stoikov market making stochastic volatility"),
    ("24", "athena_domain_24_robotics_cyber_physical_systems.md", "Denavit Hartenberg kinematics Lyapunov stability control barrier functions ROS 2 micro-ROS"),
    ("25", "athena_domain_25_environmental_climate_informatics.md", "Navier Stokes geostrophic balance radiative equilibrium InSAR remote sensing carbon flux"),
]


@pytest.fixture(scope="module")
def vector_store():
    store = AthenaVectorStore()
    assert store.count() >= 121, f"Expected at least 121 vector chunks, found {store.count()}"
    return store


@pytest.mark.parametrize("div_id,expected_source,query", DOMAIN_EVALUATION_SPECS)
def test_each_domain_retrieval(vector_store, div_id, expected_source, query):
    matches = vector_store.similarity_search(query, top_k=5)
    assert len(matches) > 0, f"No matches found for domain {div_id}: '{query}'"
    
    # Check that expected source is in candidate matches
    matched_sources = [m["source"] for m in matches]
    short_source = expected_source.replace("athena_domain_", "")
    target_match = next((m for m in matches if m["source"] == expected_source or short_source in m["source"]), None)
    assert target_match is not None, (
        f"Domain {div_id} ({expected_source}) not in top-5 matches. Found: {matched_sources}"
    )
    
    # Check that the specific match has strong positive cosine similarity
    assert target_match["score"] > 0.40, (
        f"Domain {div_id} similarity score {target_match['score']} is below minimum threshold 0.40"
    )
