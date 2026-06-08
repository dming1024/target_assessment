"""Tests for scoring_engine module."""

from modules.scoring_engine import ScoringEngine


def make_evidence(**overrides):
    """Helper to build evidence dict with defaults."""
    defaults = {
        "disease_relevance": {
            "target_cancer_overexpression": "high",
            "prognostic_associated": True,
            "mutation_cnv_frequency": 0.08,
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
            "relevant_pathway_count": 3,
            "mechanism_strength": "well_established",
            "connects_to_disease_hallmarks": True,
        },
        "druggability": {
            "approved_drugs": 2,
            "clinical_candidates": 3,
            "active_compounds": 10,
            "modality_fit": "strong",
        },
        "safety": {
            "normal_tissue_risk": "low",
            "is_common_essential": False,
            "critical_organ_expression": [],
        },
        "clinical_competition": {
            "approved_drugs_count": 3,
            "active_clinical_trials": 15,
            "differentiation_opportunity": "high",
        },
    }
    for key, value in overrides.items():
        if isinstance(value, dict):
            defaults[key].update(value)
        else:
            defaults[key] = value
    return defaults


def test_perfect_target_scores_high():
    """A target with all positive evidence should score A."""
    engine = ScoringEngine(scenario="general")
    evidence = make_evidence()
    result = engine.score(evidence)
    assert result["total_score"] >= 75, f"Expected >= 75, got {result['total_score']}"
    assert result["grade"] == "A"
    print(f"Perfect target score: {result['total_score']} (A)")


def test_weak_target_scores_low():
    """A target with mostly negative evidence should score D or E."""
    engine = ScoringEngine(scenario="general")
    evidence = make_evidence(
        disease_relevance={"target_cancer_overexpression": "low", "prognostic_associated": False,
                           "mutation_cnv_frequency": 0, "opentargets_association": False, "literature_level": "low"},
        expression={"tumor_expression": "low", "tumor_normal_diff": "none",
                    "protein_evidence": False, "tissue_specificity": "low"},
        dependency={"target_cancer_dependency": "weak", "pan_cancer_rank": "broad",
                    "is_common_essential": True, "mutation_conditioned_dep": False},
        mechanism={"relevant_pathway_count": 0, "mechanism_strength": "unknown",
                   "connects_to_disease_hallmarks": False},
        druggability={"approved_drugs": 0, "clinical_candidates": 0,
                      "active_compounds": 0, "modality_fit": "weak"},
        safety={"normal_tissue_risk": "high", "is_common_essential": True,
                "critical_organ_expression": ["heart", "brain", "liver"]},
        clinical_competition={"approved_drugs_count": 0, "active_clinical_trials": 0,
                             "differentiation_opportunity": "low"},
    )
    result = engine.score(evidence)
    assert result["total_score"] < 50, f"Expected < 50, got {result['total_score']}"
    assert result["grade"] in ("D", "E")
    print(f"Weak target score: {result['total_score']} ({result['grade']})")


def test_scenario_weights_differ():
    """Different scenarios should produce different total scores from same evidence."""
    evidence = make_evidence()
    research = ScoringEngine(scenario="research").score(evidence)
    drug_dev = ScoringEngine(scenario="drug_development").score(evidence)
    adc = ScoringEngine(scenario="adc").score(evidence)
    small_mol = ScoringEngine(scenario="small_molecule").score(evidence)

    # They should differ because weights differ
    scores = [r["total_score"] for r in [research, drug_dev, adc, small_mol]]
    assert len(set(scores)) > 1, f"Expected different scores across scenarios, got {scores}"
    print(f"Research: {research['total_score']}, DrugDev: {drug_dev['total_score']}, "
          f"ADC: {adc['total_score']}, SmallMol: {small_mol['total_score']}")


def test_common_essential_penalized():
    """Common essential genes should be heavily penalized on safety and dependency."""
    engine = ScoringEngine(scenario="general")
    good = make_evidence()
    bad = make_evidence(
        dependency={"target_cancer_dependency": "strong", "pan_cancer_rank": "broad",
                    "is_common_essential": True, "mutation_conditioned_dep": False},
        safety={"normal_tissue_risk": "high", "is_common_essential": True,
                "critical_organ_expression": ["heart", "brain"]},
    )
    good_result = engine.score(good)
    bad_result = engine.score(bad)
    assert bad_result["total_score"] < good_result["total_score"]
    assert bad_result["scores"]["safety"] < good_result["scores"]["safety"]
    print(f"Good safety: {good_result['scores']['safety']}, Bad safety: {bad_result['scores']['safety']}")


def test_all_grades():
    """Verify all 5 grades can be produced."""
    engine = ScoringEngine(scenario="general")
    # A
    assert engine._assign_grade(85)[0] == "A"
    # B
    assert engine._assign_grade(70)[0] == "B"
    # C
    assert engine._assign_grade(55)[0] == "C"
    # D
    assert engine._assign_grade(40)[0] == "D"
    # E
    assert engine._assign_grade(20)[0] == "E"
    print("All grade boundaries correct")


if __name__ == "__main__":
    test_perfect_target_scores_high()
    test_weak_target_scores_low()
    test_scenario_weights_differ()
    test_common_essential_penalized()
    test_all_grades()
    print("\nAll scoring engine tests passed!")
