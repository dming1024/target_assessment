"""
Target Scoring Engine - 靶点评分引擎

Multi-dimensional scoring system that evaluates target genes across
7 dimensions with scenario-based weighting.
"""

from typing import Dict, List, Optional, Tuple

from config import SCENARIO_WEIGHTS, SCORE_GRADES, DIMENSION_MAX


class ScoringEngine:
    """Evaluate a target gene across multiple dimensions and produce a total score."""

    def __init__(self, scenario: str = "general"):
        """
        Initialize with a scenario that determines dimension weights.

        Args:
            scenario: One of 'research', 'drug_development', 'adc',
                      'small_molecule', 'general'
        """
        self.scenario = scenario
        self.weights = SCENARIO_WEIGHTS.get(scenario, SCENARIO_WEIGHTS["general"])

    def score(self, evidence: dict) -> dict:
        """
        Compute dimension scores, total, grade, and recommendation from evidence.

        Args:
            evidence: Dictionary with per-dimension evidence blocks.
                      Keys match the dimension names.

        Returns:
            Dict with scores, total_score, grade, grade_text, recommendation
        """
        dim_scores = {
            "disease_relevance": self._score_disease_relevance(evidence.get("disease_relevance", {})),
            "expression": self._score_expression(evidence.get("expression", {})),
            "dependency": self._score_dependency(evidence.get("dependency", {})),
            "mechanism": self._score_mechanism(evidence.get("mechanism", {})),
            "druggability": self._score_druggability(evidence.get("druggability", {})),
            "safety": self._score_safety(evidence.get("safety", {})),
            "clinical_competition": self._score_competition(evidence.get("clinical_competition", {})),
            "scenario_fit": self._score_scenario_fit(evidence),
        }

        # Scale each dimension to fraction of its max, weight, then scale to 100
        total_score = 0.0
        for k in dim_scores:
            dim_max = DIMENSION_MAX.get(k, 1)
            fraction = dim_scores[k] / dim_max if dim_max > 0 else 0
            total_score += fraction * self.weights.get(k, 0)
        total_score = round(total_score * 100, 1)

        grade, grade_text = self._assign_grade(total_score)
        recommendation = self._generate_recommendation(total_score, dim_scores)

        return {
            "scores": dim_scores,
            "dimension_max": DIMENSION_MAX,
            "weights": self.weights,
            "total_score": total_score,
            "grade": grade,
            "grade_text": grade_text,
            "recommendation": recommendation,
            "scenario": self.scenario,
        }

    # ------------------------------------------------------------------
    # Per-dimension scoring (each returns raw scaled score, max = DIMENSION_MAX)
    # ------------------------------------------------------------------

    def _score_disease_relevance(self, ev: dict) -> float:
        """
        Score disease relevance based on expression, mutation, and literature evidence.
        Max: 15 points.
        """
        max_raw = DIMENSION_MAX["disease_relevance"]  # 15
        score = 0.0

        target_expr = ev.get("target_cancer_overexpression", "")
        if target_expr == "high":
            score += max_raw * 0.40   # 6 pts
        elif target_expr == "moderate":
            score += max_raw * 0.25   # 3.75 pts
        elif target_expr == "low":
            score += max_raw * 0.05   # 0.75 pts

        if ev.get("prognostic_associated"):
            score += max_raw * 0.20   # 3 pts

        mutation_freq = ev.get("mutation_cnv_frequency", 0)
        if mutation_freq > 0.10:
            score += max_raw * 0.20   # 3 pts
        elif mutation_freq > 0.03:
            score += max_raw * 0.10   # 1.5 pts

        if ev.get("opentargets_association"):
            score += max_raw * 0.10   # 1.5 pts

        literature = ev.get("literature_level", "")
        if literature == "high":
            score += max_raw * 0.10   # 1.5 pts
        elif literature == "moderate":
            score += max_raw * 0.05   # 0.75 pts

        return round(min(score, max_raw), 1)

    def _score_expression(self, ev: dict) -> float:
        """
        Score expression profile, emphasizing tumor specificity.
        Max: 15 points.
        """
        max_raw = DIMENSION_MAX["expression"]  # 15
        score = 0.0

        tumor_level = ev.get("tumor_expression", "")
        if tumor_level == "high":
            score += max_raw * 0.40   # 6 pts
        elif tumor_level == "moderate":
            score += max_raw * 0.25   # 3.75 pts
        elif tumor_level == "low":
            score += max_raw * 0.05   # 0.75 pts

        t_n_diff = ev.get("tumor_normal_diff", "")
        if t_n_diff == "significant":
            score += max_raw * 0.30   # 4.5 pts
        elif t_n_diff == "moderate":
            score += max_raw * 0.15   # 2.25 pts

        protein_evidence = ev.get("protein_evidence", False)
        if protein_evidence:
            score += max_raw * 0.15   # 2.25 pts

        tissue_specificity = ev.get("tissue_specificity", "")
        if tissue_specificity == "high":
            score += max_raw * 0.15   # 2.25 pts
        elif tissue_specificity == "moderate":
            score += max_raw * 0.08   # 1.2 pts

        return round(min(score, max_raw), 1)

    def _score_dependency(self, ev: dict) -> float:
        """
        Score functional dependency based on DepMap-like CRISPR data.
        Max: 15 points.
        """
        max_raw = DIMENSION_MAX["dependency"]  # 15
        score = 0.0

        dep_level = ev.get("target_cancer_dependency", "")
        if dep_level == "strong":
            score += max_raw * 0.50   # 7.5 pts
        elif dep_level == "moderate":
            score += max_raw * 0.30   # 4.5 pts
        elif dep_level == "weak":
            score += max_raw * 0.10   # 1.5 pts

        pan_cancer_rank = ev.get("pan_cancer_rank", "")
        if pan_cancer_rank == "selective":
            score += max_raw * 0.25   # 3.75 pts
        elif pan_cancer_rank == "moderate_selective":
            score += max_raw * 0.10   # 1.5 pts

        if ev.get("is_common_essential"):
            return round(min(score, max_raw * 0.30), 1)  # Cap at 4.5 if common essential

        if ev.get("mutation_conditioned_dep"):
            score += max_raw * 0.25   # 3.75 pts

        return round(min(score, max_raw), 1)

    def _score_mechanism(self, ev: dict) -> float:
        """
        Score mechanistic rationale based on pathway involvement.
        Max: 15 points.
        """
        max_raw = DIMENSION_MAX["mechanism"]  # 15
        score = 0.0

        pathway_count = ev.get("relevant_pathway_count", 0)
        if pathway_count >= 3:
            score += max_raw * 0.35   # 5.25 pts
        elif pathway_count >= 1:
            score += max_raw * 0.20   # 3 pts

        mechanism_strength = ev.get("mechanism_strength", "")
        if mechanism_strength == "well_established":
            score += max_raw * 0.35   # 5.25 pts
        elif mechanism_strength == "partially_established":
            score += max_raw * 0.20   # 3 pts

        if ev.get("connects_to_disease_hallmarks"):
            score += max_raw * 0.30   # 4.5 pts

        return round(min(score, max_raw), 1)

    def _score_druggability(self, ev: dict) -> float:
        """
        Score druggability based on known compounds, approved drugs, and modality fit.
        Max: 15 points.
        """
        max_raw = DIMENSION_MAX["druggability"]  # 15
        score = 0.0

        has_approved = ev.get("approved_drugs", 0)
        if has_approved > 0:
            score += max_raw * 0.40   # 6 pts

        has_clinical = ev.get("clinical_candidates", 0)
        if has_clinical > 0:
            score += max_raw * 0.25   # 3.75 pts

        has_compounds = ev.get("active_compounds", 0)
        if has_compounds > 0:
            score += max_raw * 0.15   # 2.25 pts

        modality_fit = ev.get("modality_fit", "")
        if modality_fit == "strong":
            score += max_raw * 0.20   # 3 pts
        elif modality_fit == "moderate":
            score += max_raw * 0.10   # 1.5 pts

        return round(min(score, max_raw), 1)

    def _score_safety(self, ev: dict) -> float:
        """
        Score safety liability (higher = safer).
        Max: 10 points.
        """
        max_raw = DIMENSION_MAX["safety"]  # 10
        score = max_raw  # Start full, deduct for risks

        normal_expr_risk = ev.get("normal_tissue_risk", "")
        if normal_expr_risk == "high":
            score -= max_raw * 0.60   # -6 pts
        elif normal_expr_risk == "moderate":
            score -= max_raw * 0.30   # -3 pts
        elif normal_expr_risk == "low":
            score -= max_raw * 0.10   # -1 pt

        if ev.get("is_common_essential"):
            score -= max_raw * 0.50   # -5 pts

        critical_organs = ev.get("critical_organ_expression", [])
        if len(critical_organs) >= 2:
            score -= max_raw * 0.30   # -3 pts
        elif len(critical_organs) == 1:
            score -= max_raw * 0.15   # -1.5 pts

        return round(max(score, 0), 1)

    def _score_competition(self, ev: dict) -> float:
        """
        Score clinical/competitive landscape (higher = more validated).
        Note: high competition is a double-edged signal - it validates the target
        but means less differentiation opportunity. We score it positively
        (validated target) and let scenario_fit handle differentiation concerns.
        Max: 10 points.
        """
        max_raw = DIMENSION_MAX["clinical_competition"]  # 10
        score = 0.0

        approved = ev.get("approved_drugs_count", 0)
        if approved >= 2:
            score += max_raw * 0.50   # 5 pts
        elif approved == 1:
            score += max_raw * 0.35   # 3.5 pts

        clinical_trials = ev.get("active_clinical_trials", 0)
        if clinical_trials >= 10:
            score += max_raw * 0.30   # 3 pts
        elif clinical_trials >= 3:
            score += max_raw * 0.15   # 1.5 pts

        diff_opportunity = ev.get("differentiation_opportunity", "")
        if diff_opportunity == "high":
            score += max_raw * 0.20   # 2 pts
        elif diff_opportunity == "moderate":
            score += max_raw * 0.10   # 1 pt

        return round(min(score, max_raw), 1)

    def _score_scenario_fit(self, evidence: dict) -> float:
        """
        Score how well the target fits the chosen scenario.
        Max: 5 points.
        """
        max_raw = DIMENSION_MAX["scenario_fit"]  # 5
        score = 0.0

        if self.scenario == "research":
            if evidence.get("disease_relevance", {}).get("literature_level") in ("high", "moderate"):
                score += max_raw * 0.40
            if evidence.get("mechanism", {}).get("mechanism_strength") in ("well_established", "partially_established"):
                score += max_raw * 0.40
            if evidence.get("expression", {}).get("tumor_expression") == "high":
                score += max_raw * 0.20
        elif self.scenario == "drug_development":
            if evidence.get("druggability", {}).get("modality_fit") == "strong":
                score += max_raw * 0.35
            if evidence.get("dependency", {}).get("target_cancer_dependency") in ("strong", "moderate"):
                score += max_raw * 0.35
            if evidence.get("safety", {}).get("normal_tissue_risk") == "low":
                score += max_raw * 0.30
        elif self.scenario == "adc":
            if evidence.get("expression", {}).get("protein_evidence"):
                score += max_raw * 0.40
            if evidence.get("expression", {}).get("tumor_normal_diff") == "significant":
                score += max_raw * 0.35
            if evidence.get("safety", {}).get("normal_tissue_risk") == "low":
                score += max_raw * 0.25
        elif self.scenario == "small_molecule":
            if evidence.get("druggability", {}).get("modality_fit") == "strong":
                score += max_raw * 0.40
            if evidence.get("druggability", {}).get("active_compounds", 0) > 0:
                score += max_raw * 0.30
            if evidence.get("mechanism", {}).get("mechanism_strength") == "well_established":
                score += max_raw * 0.30
        else:
            score += max_raw * 0.50  # General scenario: neutral baseline

        return round(min(score, max_raw), 1)

    # ------------------------------------------------------------------
    # Grade assignment & recommendation
    # ------------------------------------------------------------------

    def _assign_grade(self, total: float) -> Tuple[str, str]:
        """Map total score to grade and description."""
        for (lo, hi), (grade, text) in SCORE_GRADES.items():
            if lo <= total < hi:
                return grade, text
        return "E", "不推荐 — 缺乏关键支持或风险较高"

    def _generate_recommendation(self, total: float, scores: dict) -> str:
        """Generate a brief natural-language recommendation."""
        grade, _ = self._assign_grade(total)

        strengths = []
        weaknesses = []

        if scores["disease_relevance"] >= 10:
            strengths.append("疾病相关性证据较强")
        elif scores["disease_relevance"] < 5:
            weaknesses.append("疾病相关性证据较弱")

        if scores["expression"] >= 10:
            strengths.append("表达谱证据支持")
        elif scores["expression"] < 5:
            weaknesses.append("表达证据不足或正常组织风险较高")

        if scores["dependency"] >= 10:
            strengths.append("功能依赖性明确")
        elif scores["dependency"] < 4:
            weaknesses.append("缺乏功能依赖性证据")

        if scores["druggability"] >= 10:
            strengths.append("可药性较强")
        elif scores["druggability"] < 4:
            weaknesses.append("可药性证据欠缺")

        if scores["safety"] >= 7:
            strengths.append("安全性窗口较好")
        elif scores["safety"] < 3:
            weaknesses.append("安全性风险较高，需重点关注")

        if grade == "A":
            return (
                f"综合评估显示该靶点在各维度表现优异。{'; '.join(strengths)}。"
                f"建议启动深入验证或立项流程。"
            )
        elif grade == "B":
            msg = f"该靶点具有一定潜力。{'; '.join(strengths)}。"
            if weaknesses:
                msg += f" 但仍需关注: {'; '.join(weaknesses)}。"
            return msg + " 建议补充关键证据后推进。"
        elif grade == "C":
            return (
                f"该靶点证据尚不完整。{'; '.join(weaknesses) if weaknesses else '各维度表现中等'}。"
                f"建议谨慎推进，优先补充缺失证据。"
            )
        elif grade in ("D", "E"):
            return (
                f"当前证据不足以支持该靶点作为核心研究对象。"
                f"{'; '.join(weaknesses) if weaknesses else ''}。"
                f"建议重新评估靶点选择或补充大量基础数据。"
            )
        return "无法生成推荐。"
