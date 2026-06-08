"""
Report Generator - 报告生成模块

Generates Markdown, HTML, and Excel reports from evidence and scoring results.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from config import TEMPLATES_DIR, REPORTS_DIR, TABLES_DIR, DIMENSION_MAX


# Scenario labels in Chinese
SCENARIO_LABELS = {
    "research": "科研基金/SCI",
    "drug_development": "药物研发立项",
    "adc": "ADC/抗体靶点评估",
    "small_molecule": "小分子靶点评估",
    "general": "通用评估",
}


class ReportGenerator:
    """Generate target assessment reports in multiple formats."""

    def __init__(self, template_dir: str = None):
        self.template_dir = template_dir or str(TEMPLATES_DIR)

    def generate_markdown(
        self,
        target_symbol: str,
        disease: str,
        gene_info: dict,
        evidence: dict,
        score_result: dict,
        ai_interpretation: dict = None,
    ) -> str:
        """
        Generate a complete Markdown report.

        Args:
            target_symbol: HGNC gene symbol
            disease: Target disease/cancer type
            gene_info: Output from GeneResolver
            evidence: Structured evidence dictionary
            score_result: Output from ScoringEngine.score()
            ai_interpretation: Optional AI-generated text blocks

        Returns:
            Markdown-formatted report string
        """
        template_path = os.path.join(self.template_dir, "report_template.md")
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()

        report_date = datetime.now().strftime("%Y-%m-%d")

        # Build template variables
        vars_map = self._build_template_vars(
            target_symbol, disease, gene_info, evidence,
            score_result, report_date, ai_interpretation
        )

        # Simple template substitution
        result = template
        for key, value in vars_map.items():
            result = result.replace("{{ " + key + " }}", str(value))

        return result

    def _build_template_vars(
        self,
        target_symbol: str,
        disease: str,
        gene_info: dict,
        evidence: dict,
        score_result: dict,
        report_date: str,
        ai: dict = None,
    ) -> dict:
        """Build the template variable mapping."""
        scores = score_result.get("scores", {})
        scenario = score_result.get("scenario", "general")

        # Generate score table
        score_table = self._build_score_table(scores, DIMENSION_MAX, scenario)

        # Strengths and risks
        strengths, risks = self._extract_strengths_risks(scores, evidence)

        # AI interpretation or auto-generated
        if ai:
            exec_summary = ai.get("executive_summary", "")
            ai_strengths = ai.get("strengths", "")
            ai_risks = ai.get("risks", "")
            final_judgment = ai.get("final_judgment", "")
            recommended_scenarios = ai.get("recommended_scenarios", "")
            next_steps = ai.get("next_steps", "")
        else:
            exec_summary = score_result.get("recommendation", "")
            ai_strengths = "\n".join(f"- {s}" for s in strengths) if strengths else "- 暂无突出优势"
            ai_risks = "\n".join(f"- {r}" for r in risks) if risks else "- 暂无明确风险"
            final_judgment = self._auto_judgment(score_result)
            recommended_scenarios = self._auto_recommend_scenarios(score_result)
            next_steps = self._auto_next_steps(scores, evidence)

        return {
            # Report info
            "target_symbol": target_symbol,
            "target_name": gene_info.get("full_name", target_symbol),
            "disease": disease,
            "scenario_label": SCENARIO_LABELS.get(scenario, scenario),
            "report_date": report_date,
            "data_version": "MVP v0.1.0",
            # Executive summary
            "total_score": score_result.get("total_score", 0),
            "grade": score_result.get("grade", "N/A"),
            "grade_text": score_result.get("grade_text", ""),
            "recommendation": exec_summary,
            "strengths": ai_strengths,
            "risks": ai_risks,
            # Target overview
            "ensembl_id": gene_info.get("ensembl_id", ""),
            "entrez_id": gene_info.get("entrez_id", ""),
            "protein_class": evidence.get("target_overview", {}).get("protein_class", "To be determined"),
            "subcellular_location": evidence.get("target_overview", {}).get("subcellular_location", "To be determined"),
            "aliases": ", ".join(gene_info.get("synonyms", [])) or "None",
            "function_summary": evidence.get("target_overview", {}).get("function_summary", "Function summary not available."),
            # Scores
            "score_table": score_table,
            "radar_data": self._build_radar_json(scores),
            # Disease relevance
            "disease_relevance_summary": self._dim_summary("disease_relevance", evidence, scores),
            "dr_tumor_expression": self._ev(evidence, "disease_relevance.target_cancer_overexpression", "N/A"),
            "dr_tumor_strength": self._strength_label(evidence, "disease_relevance.target_cancer_overexpression"),
            "dr_prognostic": "Yes" if self._ev(evidence, "disease_relevance.prognostic_associated") else "No",
            "dr_prognostic_strength": self._strength_label(evidence, "disease_relevance.prognostic_associated"),
            "dr_mutation": f"{self._ev(evidence, 'disease_relevance.mutation_cnv_frequency', 0)*100:.1f}%",
            "dr_mutation_strength": self._freq_strength(self._ev(evidence, "disease_relevance.mutation_cnv_frequency", 0)),
            "dr_database": "Yes" if self._ev(evidence, "disease_relevance.opentargets_association") else "No",
            "dr_database_strength": self._strength_label(evidence, "disease_relevance.opentargets_association"),
            "dr_literature": self._ev(evidence, "disease_relevance.literature_level", "N/A"),
            "dr_literature_strength": self._strength_label(evidence, "disease_relevance.literature_level"),
            "score_disease_relevance": scores.get("disease_relevance", 0),
            "max_disease_relevance": DIMENSION_MAX.get("disease_relevance", 15),
            # Expression
            "expression_summary": self._dim_summary("expression", evidence, scores),
            "ex_tumor": self._ev(evidence, "expression.tumor_expression", "N/A"),
            "ex_tumor_strength": self._strength_label(evidence, "expression.tumor_expression"),
            "ex_tn_diff": self._ev(evidence, "expression.tumor_normal_diff", "N/A"),
            "ex_tn_strength": self._strength_label(evidence, "expression.tumor_normal_diff"),
            "ex_protein": "Yes" if self._ev(evidence, "expression.protein_evidence") else "No",
            "ex_protein_strength": self._strength_label(evidence, "expression.protein_evidence"),
            "ex_specificity": self._ev(evidence, "expression.tissue_specificity", "N/A"),
            "ex_specificity_strength": self._strength_label(evidence, "expression.tissue_specificity"),
            "ex_risk": self._ev(evidence, "safety.normal_tissue_risk", "N/A"),
            "ex_risk_strength": self._strength_label(evidence, "safety.normal_tissue_risk"),
            "score_expression": scores.get("expression", 0),
            "max_expression": DIMENSION_MAX.get("expression", 15),
            "score_safety": scores.get("safety", 0),
            "max_safety": DIMENSION_MAX.get("safety", 10),
            # Dependency
            "dependency_summary": self._dim_summary("dependency", evidence, scores),
            "dep_target": self._ev(evidence, "dependency.target_cancer_dependency", "N/A"),
            "dep_target_strength": self._strength_label(evidence, "dependency.target_cancer_dependency"),
            "dep_selectivity": self._ev(evidence, "dependency.pan_cancer_rank", "N/A"),
            "dep_selectivity_strength": self._strength_label(evidence, "dependency.pan_cancer_rank"),
            "dep_essential": "RISK" if self._ev(evidence, "dependency.is_common_essential") else "Clear",
            "dep_essential_strength": "High concern" if self._ev(evidence, "dependency.is_common_essential") else "Low concern",
            "dep_cond": "Yes" if self._ev(evidence, "dependency.mutation_conditioned_dep") else "No",
            "dep_cond_strength": self._strength_label(evidence, "dependency.mutation_conditioned_dep"),
            "score_dependency": scores.get("dependency", 0),
            "max_dependency": DIMENSION_MAX.get("dependency", 15),
            # Mechanism
            "mechanism_summary": self._dim_summary("mechanism", evidence, scores),
            "mech_pathways": str(self._ev(evidence, "mechanism.relevant_pathway_count", 0)),
            "mech_pathways_strength": self._count_strength(self._ev(evidence, "mechanism.relevant_pathway_count", 0)),
            "mech_strength": self._ev(evidence, "mechanism.mechanism_strength", "N/A"),
            "mech_strength_label": self._strength_label(evidence, "mechanism.mechanism_strength"),
            "mech_hallmark": "Yes" if self._ev(evidence, "mechanism.connects_to_disease_hallmarks") else "To be determined",
            "mech_hallmark_strength": self._strength_label(evidence, "mechanism.connects_to_disease_hallmarks"),
            "score_mechanism": scores.get("mechanism", 0),
            "max_mechanism": DIMENSION_MAX.get("mechanism", 15),
            # Druggability
            "druggability_summary": self._dim_summary("druggability", evidence, scores),
            "drug_approved": str(self._ev(evidence, "druggability.approved_drugs", 0)),
            "drug_approved_strength": self._count_strength(self._ev(evidence, "druggability.approved_drugs", 0)),
            "drug_clinical": str(self._ev(evidence, "druggability.clinical_candidates", 0)),
            "drug_clinical_strength": self._count_strength(self._ev(evidence, "druggability.clinical_candidates", 0)),
            "drug_compounds": str(self._ev(evidence, "druggability.active_compounds", 0)),
            "drug_compounds_strength": self._count_strength(self._ev(evidence, "druggability.active_compounds", 0)),
            "drug_modality": self._ev(evidence, "druggability.modality_fit", "N/A"),
            "drug_modality_strength": self._strength_label(evidence, "druggability.modality_fit"),
            "drug_trials": str(self._ev(evidence, "clinical_competition.active_clinical_trials", 0)),
            "drug_trials_strength": self._count_strength(self._ev(evidence, "clinical_competition.active_clinical_trials", 0)),
            "drug_diff": self._ev(evidence, "clinical_competition.differentiation_opportunity", "N/A"),
            "drug_diff_strength": self._strength_label(evidence, "clinical_competition.differentiation_opportunity"),
            "score_druggability": scores.get("druggability", 0),
            "max_druggability": DIMENSION_MAX.get("druggability", 15),
            "score_clinical": scores.get("clinical_competition", 0),
            "max_clinical": DIMENSION_MAX.get("clinical_competition", 10),
            # Final recommendation
            "final_judgment": final_judgment,
            "recommended_scenarios": recommended_scenarios,
            "next_steps": next_steps,
            "missing_evidence": self._missing_evidence(scores, evidence),
            "data_sources": self._list_data_sources(evidence),
        }

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def _ev(self, evidence: dict, path: str, default: Any = None) -> Any:
        """Get nested evidence value by dot-separated path."""
        keys = path.split(".")
        val = evidence
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
        return val if val is not None else default

    def _strength_label(self, evidence, key) -> str:
        """Map evidence value to strength label."""
        val = self._ev(evidence, key) if "." in key else evidence.get(key)
        if isinstance(val, bool):
            return "Strong" if val else "Weak"
        if val in ("high", "strong", "significant", "well_established", "selective"):
            return "Strong"
        if val in ("moderate", "moderate_selective", "partially_established"):
            return "Moderate"
        return "Weak / No data"

    def _count_strength(self, count) -> str:
        if count >= 3:
            return "Strong"
        if count >= 1:
            return "Moderate"
        return "Weak / None"

    def _freq_strength(self, freq) -> str:
        if freq > 0.10:
            return "Strong"
        if freq > 0.03:
            return "Moderate"
        return "Weak"

    def _dim_summary(self, dim: str, evidence: dict, scores: dict) -> str:
        """Generate a one-sentence summary for a dimension."""
        score = scores.get(dim, 0)
        max_s = DIMENSION_MAX.get(dim, 15)
        pct = score / max_s if max_s > 0 else 0
        if pct >= 0.8:
            return f"Evidence for this dimension is strong ({score}/{max_s})."
        elif pct >= 0.5:
            return f"Evidence is moderate ({score}/{max_s}). Some data gaps remain."
        elif pct >= 0.3:
            return f"Evidence is limited ({score}/{max_s}). Additional data needed."
        return f"Evidence is weak ({score}/{max_s}). Critical data gaps present."

    def _build_score_table(self, scores: dict, maxes: dict, scenario: str) -> str:
        """Build markdown score table."""
        dim_names = {
            "disease_relevance": "Disease Relevance · 疾病相关性",
            "expression": "Expression Profile · 表达谱",
            "dependency": "Functional Dependency · 功能依赖性",
            "mechanism": "Mechanistic Rationale · 机制通路",
            "druggability": "Druggability · 可药性",
            "safety": "Safety Liability · 安全性",
            "clinical_competition": "Clinical Landscape · 临床格局",
            "scenario_fit": f"Scenario Fit · 场景匹配 ({SCENARIO_LABELS.get(scenario, scenario)})",
        }
        rows = []
        rows.append("| Dimension | Score | Max | Rating |")
        rows.append("|-----------|-------|-----|--------|")
        for key, name in dim_names.items():
            s = scores.get(key, 0)
            m = maxes.get(key, 5)
            pct = s / m if m > 0 else 0
            if pct >= 0.8:
                bar = "★★★★★"
            elif pct >= 0.6:
                bar = "★★★★"
            elif pct >= 0.4:
                bar = "★★★"
            elif pct >= 0.2:
                bar = "★★"
            else:
                bar = "★"
            rows.append(f"| {name} | {s} | {m} | {bar} |")
        return "\n".join(rows)

    def _build_radar_json(self, scores: dict) -> str:
        """Build JSON for radar chart rendering."""
        return json.dumps(scores, ensure_ascii=False)

    def _extract_strengths_risks(self, scores: dict, evidence: dict) -> tuple:
        """Extract strengths and risks from scores."""
        strengths = []
        risks = []
        thresholds = {
            "disease_relevance": (10, 5, "疾病相关性", "疾病相关性证据不足"),
            "expression": (10, 5, "表达谱证据充分", "表达证据薄弱"),
            "dependency": (10, 4, "功能依赖性明确", "缺乏依赖性证据"),
            "mechanism": (10, 5, "机制通路证据清晰", "机制证据不足"),
            "druggability": (10, 4, "可药性证据充分", "可药性证据缺乏"),
            "safety": (7, 3, "安全性窗口较好", "存在安全性风险"),
            "clinical_competition": (7, 3, "临床验证充分", "临床证据有限"),
        }
        for dim, (high, low, strength_msg, risk_msg) in thresholds.items():
            s = scores.get(dim, 0)
            if s >= high:
                strengths.append(strength_msg)
            elif s < low:
                risks.append(risk_msg)
        return strengths, risks

    def _auto_judgment(self, score_result: dict) -> str:
        grade = score_result.get("grade", "")
        total = score_result.get("total_score", 0)
        if grade == "A":
            return "该靶点在当前评估场景中表现优异，多维度证据支持其作为核心靶点进行深入研究和开发。"
        elif grade == "B":
            return "该靶点具有较好潜力，但仍有部分关键证据需要补充。建议在补强证据后推进立项或基金申请。"
        elif grade == "C":
            return "该靶点证据尚不完整，建议谨慎推进。可作为候选方向继续追踪，但不建议立即作为核心靶点大量投入资源。"
        elif grade == "D":
            return "当前证据不支持该靶点作为优先研究对象。建议先补充基础实验数据后再行评估。"
        return "当前证据不足以支持该靶点推进。建议重新评估靶点选择。"

    def _auto_recommend_scenarios(self, score_result: dict) -> str:
        scores = score_result.get("scores", {})
        recs = []
        if scores.get("disease_relevance", 0) >= 8 and scores.get("mechanism", 0) >= 8:
            recs.append("- **基金申请**: 疾病相关性和机制证据较好，适合作为基金课题核心靶点")
        if scores.get("expression", 0) >= 8 and scores.get("dependency", 0) >= 8:
            recs.append("- **SCI论文**: 表达和功能证据较完整，可构建机制故事线")
        if scores.get("druggability", 0) >= 8 and scores.get("safety", 0) >= 5:
            recs.append("- **药物研发**: 可药性证据支持，可考虑作为药物靶点立项")
        if scores.get("expression", 0) >= 8 and scores.get("safety", 0) >= 5:
            recs.append("- **Biomarker开发**: 表达特异性较好，可开发为伴随诊断标志物")
        if not recs:
            recs.append("- 建议先补充基础实验数据，再确定适合的场景")
        return "\n".join(recs)

    def _auto_next_steps(self, scores: dict, evidence: dict) -> str:
        steps = []
        if scores.get("disease_relevance", 0) < 8:
            steps.append("- 通过IHC/RNA-seq验证靶点在目标疾病组织中的表达")
        if scores.get("dependency", 0) < 8:
            steps.append("- 在目标癌种细胞系中进行CRISPR敲除/敲降功能实验")
        if scores.get("mechanism", 0) < 8:
            steps.append("- 补充通路富集分析和上下游调控关系研究")
        if scores.get("druggability", 0) < 5:
            steps.append("- 检索ChEMBL/DrugBank等数据库确认已知活性化合物")
        if scores.get("safety", 0) < 5:
            steps.append("- 评估正常组织表达谱，重点关注心脏、肝脏、肾脏等关键器官")
        if scores.get("clinical_competition", 0) < 5:
            steps.append("- 检索ClinicalTrials.gov了解竞品临床进展")
        if not steps:
            steps.append("- 当前证据较完整，可进入人工深度评估阶段")
        return "\n".join(steps)

    def _missing_evidence(self, scores: dict, evidence: dict) -> str:
        missing = []
        if scores.get("disease_relevance", 0) < 10:
            missing.append("- **疾病相关性**: 需更多表达/突变/预后关联数据")
        if scores.get("expression", 0) < 10:
            missing.append("- **表达谱**: 需正常组织蛋白表达数据以评估安全窗口")
        if scores.get("dependency", 0) < 10:
            missing.append("- **功能依赖性**: 需CRISPR/RNAi功能实验数据")
        if scores.get("mechanism", 0) < 10:
            missing.append("- **机制通路**: 需更完整的通路和调控网络分析")
        if scores.get("druggability", 0) < 10:
            missing.append("- **可药性**: 需化合物/抗体活性数据和药物形式评估")
        if scores.get("safety", 0) < 7:
            missing.append("- **安全性**: 需正常组织表达和essential gene风险评估")
        if scores.get("clinical_competition", 0) < 7:
            missing.append("- **临床格局**: 需竞品和临床试验信息")
        if not missing:
            return "各维度证据相对完整，可进行更深入的专家评估。"
        return "\n".join(missing)

    def _list_data_sources(self, evidence: dict) -> str:
        sources = evidence.get("data_sources", {})
        if not sources:
            return "- TCGA (expression/mutation/CNV)\n- DepMap (CRISPR dependency)\n- Open Targets (disease association)\n- ChEMBL (drug/compound)\n- GTEx (normal tissue expression)"
        return "\n".join(f"- {k}: {v}" for k, v in sources.items())

    # ------------------------------------------------------------------
    # Export methods
    # ------------------------------------------------------------------

    def export_html(self, markdown_text: str, output_path: str = None) -> str:
        """Convert Markdown to a styled HTML page."""
        html = self._md_to_html(markdown_text)
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)
        return html

    def export_excel(self, evidence: dict, score_result: dict, output_path: str = None) -> str:
        """
        Export structured evidence and scores to Excel.

        Returns the output path or bytes content.
        """
        scores = score_result.get("scores", {})

        # Evidence summary sheet
        ev_rows = []
        for dim, data in evidence.items():
            if isinstance(data, dict):
                for key, val in data.items():
                    ev_rows.append({
                        "Dimension": dim,
                        "Evidence Item": key,
                        "Value": str(val),
                    })

        df_evidence = pd.DataFrame(ev_rows)

        # Scores sheet
        score_rows = []
        for dim, score in scores.items():
            max_s = DIMENSION_MAX.get(dim, 0)
            weight = score_result.get("weights", {}).get(dim, 0)
            score_rows.append({
                "Dimension": dim,
                "Score": score,
                "Max": max_s,
                "Weight": weight,
                "Weighted Contribution": round(score / max_s * weight * 100, 2) if max_s > 0 else 0,
            })
        df_scores = pd.DataFrame(score_rows)

        # Summary row
        summary_row = pd.DataFrame([{
            "Dimension": "TOTAL",
            "Score": score_result.get("total_score", 0),
            "Max": 100,
            "Weight": 1.0,
            "Weighted Contribution": score_result.get("total_score", 0),
        }])
        df_scores = pd.concat([df_scores, summary_row], ignore_index=True)

        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                df_evidence.to_excel(writer, sheet_name="Evidence", index=False)
                df_scores.to_excel(writer, sheet_name="Scores", index=False)
            return output_path

        return df_evidence, df_scores

    def _md_to_html(self, md_text: str) -> str:
        """Simple Markdown to HTML conversion with styling."""
        # Basic conversion - can be enhanced with markdown library
        import re

        css = """
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                   max-width: 900px; margin: 0 auto; padding: 20px; color: #333; line-height: 1.6; }
            h1 { color: #1a365d; border-bottom: 3px solid #3182ce; padding-bottom: 10px; }
            h2 { color: #2c5282; border-bottom: 1px solid #bee3f8; padding-bottom: 5px; margin-top: 30px; }
            h3 { color: #2b6cb0; }
            table { border-collapse: collapse; width: 100%; margin: 15px 0; }
            th, td { border: 1px solid #e2e8f0; padding: 8px 12px; text-align: left; }
            th { background-color: #ebf8ff; font-weight: 600; }
            tr:nth-child(even) { background-color: #f7fafc; }
            .score-high { color: #38a169; font-weight: bold; }
            .score-low { color: #e53e3e; font-weight: bold; }
            blockquote { border-left: 4px solid #3182ce; padding: 10px 20px;
                         background: #ebf8ff; margin: 15px 0; }
        </style>
        """

        # Convert tables
        # Headers
        md_text = re.sub(r'^\|(.+)\|\s*$\n\|[-| :]+\|\s*$\n', self._table_header_replace, md_text, flags=re.MULTILINE)
        # Rows
        md_text = re.sub(r'^\|(.+)\|\s*$', r'<tr><td>\1</td></tr>', md_text, flags=re.MULTILINE)
        md_text = md_text.replace('</td></tr>\n<tr><td>', '</td></tr><tr><td>')
        md_text = md_text.replace('<tr><td>', '<table><tr><th>', 1)
        md_text = md_text.replace('</td></tr>', '</td></tr></table>')
        # Fix th/td
        md_text = md_text.replace('<tr><th>', '<tr><th>').replace('</td></tr>', '</td></tr>')
        # Split cells
        md_text = re.sub(r'<th>(.+?)</th>', lambda m: '<th>' + '</th><th>'.join(re.split(r'\s*\|\s*', m.group(1))) + '</th>', md_text)
        md_text = re.sub(r'<td>(.+?)</td>', lambda m: '<td>' + '</td><td>'.join(re.split(r'\s*\|\s*', m.group(1))) + '</td>', md_text)

        # Headers
        md_text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', md_text, flags=re.MULTILINE)
        md_text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', md_text, flags=re.MULTILINE)
        md_text = re.sub(r'^# (.+)$', r'<h1>\1</h1>', md_text, flags=re.MULTILINE)

        # Bold
        md_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', md_text)

        # Blockquote
        md_text = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', md_text, flags=re.MULTILINE)

        # Lists
        md_text = re.sub(r'^- (.+)$', r'<li>\1</li>', md_text, flags=re.MULTILINE)

        # Horizontal rules
        md_text = re.sub(r'^---$', r'<hr>', md_text, flags=re.MULTILINE)

        # Paragraphs (double newlines)
        md_text = re.sub(r'\n\n', r'</p><p>', md_text)
        md_text = '<p>' + md_text + '</p>'

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Target Assessment Report</title>
    {css}
</head>
<body>
{md_text}
</body>
</html>"""
        return html

    def _table_header_replace(self, match):
        """Replace markdown table header with HTML header row."""
        header = match.group(1)
        cells = [c.strip() for c in header.split('|')]
        return '<table><tr>' + ''.join(f'<th>{c}</th>' for c in cells) + '</tr>\n'

    def save_markdown(self, markdown_text: str, output_path: str = None) -> str:
        """Save markdown report to file."""
        if output_path is None:
            output_path = os.path.join(
                str(REPORTS_DIR), f"target_assessment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_text)
        return output_path
