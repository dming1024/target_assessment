"""
Target Assessment Core Logic

Extracted from api.py so that both the REST API (/assess) and the
WeChat callback (/wechat) can call the same function.
"""

from typing import Dict

from modules.gene_resolver import GeneResolver
from modules.data_manager import DataManager
from modules.scoring_engine import ScoringEngine


def run_assessment(
    gene: str,
    disease: str = "pan-cancer",
    scenario: str = "general",
) -> dict:
    """
    Run a full target assessment for a given gene.

    Returns a structured dict (always includes a 'status' key):
        status        — "success" or "error"
        error         — error message when status == "error"
        gene          — official HGNC symbol
        full_name     — gene full name
        ensembl_id    — Ensembl gene ID
        disease       — disease / cancer type
        scenario      — assessment scenario used
        total_score   — 0-100 total score
        grade         — A/B/C/D/E
        grade_label   — human-readable grade description
        recommendation — natural-language recommendation
        archetype     — target archetype
        scores        — dict of dimension → raw score (before weighting)
        weights       — dimension weights used
        adjusted_weights — archetype-adjusted weights
        evidence      — raw evidence dict (only for non-summary consumers)
    """
    # ── Validate inputs ──────────────────────────────────────────────────
    gene_input = gene.strip()
    if not gene_input:
        return {"status": "error", "error": "gene is required"}

    scenario = scenario.strip() or "general"
    if scenario not in (
        "general", "research", "drug_development", "adc", "small_molecule",
    ):
        return {
            "status": "error",
            "error": f"Invalid scenario '{scenario}'. "
                     f"Valid: general, research, drug_development, adc, small_molecule",
        }

    disease = disease.strip() or "pan-cancer"

    # ── Step 1: Resolve gene symbol ──────────────────────────────────────
    gene_info = GeneResolver().resolve(gene_input)
    if gene_info.status in ("empty_input", "unresolved"):
        return {
            "status": "error",
            "error": f"Cannot resolve gene symbol: {gene_input}",
        }

    # ── Step 2: Collect evidence ─────────────────────────────────────────
    dm = DataManager()
    evidence = dm.collect_evidence(
        gene_symbol=gene_info.symbol,
        disease=disease,
        scenario=scenario,
        ensembl_id=gene_info.ensembl_id,
    )

    # ── Step 3: Score ────────────────────────────────────────────────────
    engine = ScoringEngine(scenario=scenario,
                           gene_symbol=gene_info.symbol, disease=disease)
    result = engine.score(evidence)

    # ── Step 4: Build return dict ────────────────────────────────────────
    return {
        "status": "success",
        "error": None,
        "gene": gene_info.symbol,
        "full_name": gene_info.full_name,
        "ensembl_id": gene_info.ensembl_id,
        "disease": disease,
        "scenario": scenario,
        "total_score": result["total_score"],
        "grade": result["grade"],
        "grade_label": result["grade_text"],
        "recommendation": result["recommendation"],
        "archetype": result["archetype"],
        "scores": result["scores"],
        "weights": result["weights"],
        "adjusted_weights": result["adjusted_weights"],
        "evidence": evidence,
    }
