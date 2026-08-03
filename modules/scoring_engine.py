"""
Target Scoring Engine - 靶点评分引擎

Multi-dimensional scoring system that evaluates target genes across
7 dimensions with scenario-based weighting.
"""

from typing import Dict, List, Optional, Tuple

from config import SCENARIO_WEIGHTS, SCORE_GRADES, DIMENSION_MAX, ARCHETYPE_MODIFIERS


class ScoringEngine:
    """Evaluate a target gene across multiple dimensions and produce a total score."""

    def __init__(self, scenario: str = "general", custom_weights: dict = None,
                 gene_symbol: str = "", disease: str = ""):
        """
        Initialize with a scenario that determines dimension weights.

        Args:
            scenario: One of 'research', 'drug_development', 'adc',
                      'small_molecule', 'general'
            custom_weights: Optional dict mapping dimension names to weights
                            (e.g. {"disease_relevance": 0.25, "expression": 0.20, ...}).
                            Specified dimensions override scenario defaults;
                            unspecified dimensions keep scenario values.
                            All weights are normalized to sum to 1.0.
                            When provided, archetype adjustment is skipped.
        """
        self.scenario = scenario
        self.gene_symbol = gene_symbol
        self.disease = disease
        base_weights = SCENARIO_WEIGHTS.get(scenario, SCENARIO_WEIGHTS["general"])
        self.custom_weights_provided = custom_weights is not None and len(custom_weights) > 0

        if self.custom_weights_provided:
            merged = dict(base_weights)
            for dim, w in custom_weights.items():
                if dim in merged:
                    merged[dim] = float(w)
                else:
                    raise ValueError(
                        f"Unknown dimension '{dim}'. Valid dimensions: {list(base_weights.keys())}"
                    )
            # Normalize to sum to 1.0
            total = sum(merged.values())
            if total <= 0:
                raise ValueError("Sum of weights must be > 0")
            self.weights = {k: round(v / total, 4) for k, v in merged.items()}
        else:
            self.weights = base_weights

    # ── Archetype classification ──────────────────────────────────────

    def _classify_archetype(self, disease: dict, expression: dict,
                            dependency: dict, druggability: dict,
                            mechanism: dict) -> str:
        """
        Classify a target into one of five archetypes based on evidence pattern.

        Priority order (first match wins — biological signals before drug knowledge):
          1. expression_driven — strongly overexpressed (the most direct biological signal)
          2. dependency_driven — strong, selective CRISPR dependency
          3. mutation_driven   — non-trivial point-mutation frequency
          4. drug_target       — already has approved drugs (pharma-validated)
          5. balanced          — no single signal dominates

        Returns one of: expression_driven, dependency_driven, mutation_driven,
                        drug_target, balanced
        """
        overexpression = expression.get("tumor_expression", "")
        dep_level = dependency.get("target_cancer_dependency", "")
        dep_pct = dependency.get("depmap_percentile", 50) or 50
        mutation_freq = disease.get("tcga_mutation_freq", 0) or 0
        approved = druggability.get("approved_drugs", 0) or 0

        # 1. Expression-driven: the cleanest biological signal
        if overexpression in ("high",):
            return "expression_driven"

        # 2. Dependency-driven: strong & selective DepMap signal
        if dep_level == "strong" and dep_pct < 10:
            return "dependency_driven"

        # 3. Mutation-driven: non-trivial point-mutation frequency
        #    (CNV amplification is excluded — it's globally high and non-specific)
        if mutation_freq > 0.02:
            return "mutation_driven"

        # 4. Drug target: pharma-validated, biology signal unclear in our data
        if approved > 0:
            return "drug_target"

        # 5. Fallback
        return "balanced"

    # ── Scoring ────────────────────────────────────────────────────────

    def score(self, evidence: dict) -> dict:
        """
        Compute dimension scores, total, grade, and recommendation from evidence.

        Dimension weights are adjusted by target archetype so that e.g.
        mutation-driven targets aren't penalised for low expression.
        """
        disease = evidence.get("disease_relevance", {})
        expression = evidence.get("expression", {})
        drug = evidence.get("druggability", {})
        dep = evidence.get("dependency", {})

        dim_scores = {
            "disease_relevance": self._score_disease_relevance(disease),
            "expression": self._score_expression(expression),
            "dependency": self._score_dependency(dep),
            "mechanism": self._score_mechanism(evidence.get("mechanism", {})),
            "druggability": self._score_druggability(drug),
            "safety": self._score_safety(evidence.get("safety", {})),
            "clinical_competition": self._score_competition(evidence.get("clinical_competition", {})),
            "scenario_fit": self._score_scenario_fit(evidence),
        }

        # ── Apply archetype adjustment (skip if user provided custom weights) ─
        mech = evidence.get("mechanism", {})
        archetype = self._classify_archetype(disease, expression, dep, drug, mech)
        if self.custom_weights_provided:
            adjusted_weights = dict(self.weights)
        else:
            modifiers = ARCHETYPE_MODIFIERS.get(archetype, {})
            adjusted_weights = dict(self.weights)
            for dim, delta in modifiers.items():
                if dim in adjusted_weights:
                    adjusted_weights[dim] = max(0.03, min(0.35,
                        adjusted_weights[dim] + delta))
            # Normalise so weights sum to 1
            total_w = sum(adjusted_weights.values())
            if total_w > 0 and abs(total_w - 1.0) > 0.001:
                adjusted_weights = {k: v / total_w for k, v in adjusted_weights.items()}

        # Scale each dimension to fraction of its max, weight, then scale to 100
        total_score = 0.0
        for k in dim_scores:
            dim_max = DIMENSION_MAX.get(k, 1)
            fraction = dim_scores[k] / dim_max if dim_max > 0 else 0
            total_score += fraction * adjusted_weights.get(k, 0)
        total_score = round(total_score * 100, 1)

        grade, grade_text = self._assign_grade(total_score)

        # Try LLM-generated assessment first; fall back to template
        recommendation = self._try_llm_recommendation(
            evidence, dim_scores, total_score, grade, grade_text, archetype
        )
        if recommendation is None:
            recommendation = self._generate_recommendation(
                total_score, dim_scores, archetype, evidence
            )

        return {
            "scores": dim_scores,
            "dimension_max": DIMENSION_MAX,
            "weights": self.weights,
            "adjusted_weights": adjusted_weights,
            "archetype": archetype,
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

    def _try_llm_recommendation(
        self, evidence: dict, dim_scores: dict, total_score: float,
        grade: str, grade_text: str, archetype: str,
    ) -> Optional[str]:
        """Attempt LLM-generated assessment; return None if unavailable/failed."""
        try:
            from modules.llm_assessor import LLMAssessor
            assessor = LLMAssessor()
            if not assessor.available:
                return None
            return assessor.generate_assessment(
                gene_symbol=self.gene_symbol,
                disease=self.disease,
                evidence=evidence,
                scores={"scores": dim_scores, "dimension_max": DIMENSION_MAX},
                total_score=total_score,
                grade=grade,
                grade_text=grade_text,
                archetype=archetype,
                scenario=self.scenario,
            )
        except Exception:
            return None

    def _generate_recommendation(self, total: float, scores: dict,
                                  archetype: str = "balanced",
                                  evidence: dict = None) -> str:
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

        # ── Archetype-aware recommendations ───────────────────────────
        if archetype == "drug_target":
            approved = 0
            if evidence:
                approved = evidence.get("druggability", {}).get("approved_drugs", 0) or 0
            if grade in ("A", "B"):
                return (
                    f"该靶点为临床充分验证的成熟药靶（{approved}个已批准药物）。"
                    f"{'; '.join(strengths)}。"
                    f"新药研发建议聚焦：更高靶点选择性、差异化安全性窗口、"
                    f"或新作用机制的再创新策略。"
                )
            elif grade == "C":
                return (
                    f"该靶点已有{approved}个已批准药物，属于已验证的药靶，"
                    f"但部分非临床维度的证据信号较弱（如疾病表达/依赖性数据）。"
                    f"这并非否定该靶点的临床价值，而是提示当前评估数据以癌症生物学为主，"
                    f"对该类已验证的非癌/跨适应症靶点的区分度有限。"
                    f"如需差异化开发，建议关注选择性优化或新适应症拓展。"
                )
            else:  # D, E
                return (
                    f"该靶点虽有{approved}个已批准药物的临床验证，"
                    f"但在当前评估场景下癌症生物学证据不充分（注意：这不代表靶点本身缺乏价值）。"
                    f"该靶点更适合作为'已验证靶点的再创新'而非'新靶点发现'来评估。"
                    f"建议使用更聚焦的场景（如 drug_development）或提供具体适应症以获得更准确的评估。"
                )

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
