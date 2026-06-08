"""Tests for report_generator module."""

import os
import json
from modules.report_generator import ReportGenerator
from modules.scoring_engine import ScoringEngine


def test_generate_markdown():
    """Verify markdown report generation works end-to-end."""
    gen = ReportGenerator()

    gene_info = {
        "input": "HER2",
        "symbol": "ERBB2",
        "ensembl_id": "ENSG00000141736",
        "entrez_id": "2064",
        "full_name": "erb-b2 receptor tyrosine kinase 2",
        "synonyms": ["HER-2", "NEU"],
        "status": "resolved_local",
    }

    evidence = {
        "target_overview": {
            "protein_class": "Kinase / Receptor",
            "subcellular_location": "Cell membrane",
            "function_summary": "ERBB2 is a member of the EGFR family of receptor tyrosine kinases. It plays a key role in cell growth, differentiation, and survival. Amplification and overexpression of ERBB2 are associated with aggressive tumor behavior in breast and gastric cancers.",
        },
        "disease_relevance": {
            "target_cancer_overexpression": "high",
            "prognostic_associated": True,
            "mutation_cnv_frequency": 0.20,
            "opentargets_association": True,
            "literature_level": "high",
        },
        "expression": {
            "tumor_expression": "high",
            "tumor_normal_diff": "significant",
            "protein_evidence": True,
            "tissue_specificity": "high",
        },
        "dependency": {
            "target_cancer_dependency": "strong",
            "pan_cancer_rank": "selective",
            "is_common_essential": False,
            "mutation_conditioned_dep": True,
        },
        "mechanism": {
            "relevant_pathway_count": 4,
            "mechanism_strength": "well_established",
            "connects_to_disease_hallmarks": True,
        },
        "druggability": {
            "approved_drugs": 5,
            "clinical_candidates": 10,
            "active_compounds": 50,
            "modality_fit": "strong",
        },
        "safety": {
            "normal_tissue_risk": "moderate",
            "is_common_essential": False,
            "critical_organ_expression": ["heart"],
        },
        "clinical_competition": {
            "approved_drugs_count": 5,
            "active_clinical_trials": 50,
            "differentiation_opportunity": "moderate",
        },
        "data_sources": {
            "TCGA": "Pan-Cancer Atlas, v36",
            "DepMap": "CRISPR Gene Effect, 24Q4",
            "Open Targets": "2024.12",
            "ChEMBL": "v34",
            "GTEx": "v10",
        },
    }

    engine = ScoringEngine(scenario="adc")
    score_result = engine.score(evidence)

    md = gen.generate_markdown(
        target_symbol="ERBB2",
        disease="Gastric Cancer",
        gene_info=gene_info,
        evidence=evidence,
        score_result=score_result,
    )

    # Verify key sections exist
    assert "# Target Assessment Report" in md
    assert "ERBB2" in md
    assert "Gastric Cancer" in md
    assert "Executive Summary" in md
    assert "Target Overview" in md
    assert "Disease Relevance" in md
    assert "Expression & Safety Window" in md
    assert "Functional Dependency" in md
    assert "Mechanistic Rationale" in md
    assert "Druggability & Clinical Landscape" in md
    assert "Final Recommendation" in md

    # Save sample
    output_path = gen.save_markdown(md, "/root/target_assessment/outputs/reports/test_erbb2_gastric.md")
    assert os.path.exists(output_path)
    print(f"Report saved to: {output_path}")
    print(f"Report length: {len(md)} chars")
    print("Markdown generation test passed!")


def test_excel_export():
    """Verify Excel export works."""
    gen = ReportGenerator()
    evidence = {"disease_relevance": {"key": "val"}}
    score_result = {
        "scores": {"disease_relevance": 12, "expression": 10},
        "total_score": 75.0,
        "weights": {"disease_relevance": 0.15, "expression": 0.15},
    }
    path = "/root/target_assessment/outputs/tables/test_evidence.xlsx"
    result = gen.export_excel(evidence, score_result, output_path=path)
    assert os.path.exists(path)
    print(f"Excel saved to: {result}")
    print("Excel export test passed!")


if __name__ == "__main__":
    test_generate_markdown()
    test_excel_export()
    print("\nAll report generator tests passed!")
