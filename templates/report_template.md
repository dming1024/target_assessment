# Target Assessment Report
## 靶点价值评估报告

---

### Report Information

| Field | Value |
|-------|-------|
| **Target Gene** | {{ target_symbol }} ({{ target_name }}) |
| **Disease / Cancer Type** | {{ disease }} |
| **Scenario** | {{ scenario_label }} |
| **Report Date** | {{ report_date }} |
| **Data Version** | {{ data_version }} |

---

## 1. Executive Summary · 评估总览

### Overall Score: **{{ total_score }} / 100** — Grade **{{ grade }}**

> **{{ grade_text }}**

### One-line Conclusion
{{ recommendation }}

### Key Strengths
{{ strengths }}

### Key Risks
{{ risks }}

---

## 2. Target Overview · 靶点概览

| Attribute | Value |
|-----------|-------|
| **Gene Symbol** | {{ target_symbol }} |
| **Full Name** | {{ target_name }} |
| **Ensembl ID** | {{ ensembl_id }} |
| **Entrez ID** | {{ entrez_id }} |
| **Protein Class** | {{ protein_class }} |
| **Subcellular Location** | {{ subcellular_location }} |
| **Aliases** | {{ aliases }} |

### Function Summary
{{ function_summary }}

---

## 3. Multi-Dimensional Score · 多维度评分

{{ score_table }}

### Score Distribution (Radar Chart Data)
{{ radar_data }}

---

## 4. Disease Relevance · 疾病相关性

### Summary
{{ disease_relevance_summary }}

| Evidence Item | Finding | Strength |
|---------------|---------|----------|
| Tumor Expression | {{ dr_tumor_expression }} | {{ dr_tumor_strength }} |
| Prognostic Association | {{ dr_prognostic }} | {{ dr_prognostic_strength }} |
| Mutation / CNV | {{ dr_mutation }} | {{ dr_mutation_strength }} |
| Database Association | {{ dr_database }} | {{ dr_database_strength }} |
| Literature Support | {{ dr_literature }} | {{ dr_literature_strength }} |

**Score: {{ score_disease_relevance }} / {{ max_disease_relevance }}**

---

## 5. Expression & Safety Window · 表达谱与安全窗口

### Summary
{{ expression_summary }}

| Evidence Item | Finding | Strength |
|---------------|---------|----------|
| Tumor Expression | {{ ex_tumor }} | {{ ex_tumor_strength }} |
| Tumor vs Normal | {{ ex_tn_diff }} | {{ ex_tn_strength }} |
| Protein Evidence | {{ ex_protein }} | {{ ex_protein_strength }} |
| Tissue Specificity | {{ ex_specificity }} | {{ ex_specificity_strength }} |
| Normal Tissue Risk | {{ ex_risk }} | {{ ex_risk_strength }} |

**Expression Score: {{ score_expression }} / {{ max_expression }}**
**Safety Score: {{ score_safety }} / {{ max_safety }}**

---

## 6. Functional Dependency · 功能依赖性

### Summary
{{ dependency_summary }}

| Evidence Item | Finding | Strength |
|---------------|---------|----------|
| Target Cancer Dependency | {{ dep_target }} | {{ dep_target_strength }} |
| Pan-Cancer Selectivity | {{ dep_selectivity }} | {{ dep_selectivity_strength }} |
| Common Essential Risk | {{ dep_essential }} | {{ dep_essential_strength }} |
| Mutation-Conditioned Dependency | {{ dep_cond }} | {{ dep_cond_strength }} |

**Score: {{ score_dependency }} / {{ max_dependency }}**

---

## 7. Mechanistic Rationale · 机制通路证据

### Summary
{{ mechanism_summary }}

| Evidence Item | Finding | Strength |
|---------------|---------|----------|
| Relevant Pathways | {{ mech_pathways }} | {{ mech_pathways_strength }} |
| Mechanism Strength | {{ mech_strength }} | {{ mech_strength_label }} |
| Disease Hallmark Connection | {{ mech_hallmark }} | {{ mech_hallmark_strength }} |

**Score: {{ score_mechanism }} / {{ max_mechanism }}**

---

## 8. Druggability & Clinical Landscape · 可药性与临床格局

### Summary
{{ druggability_summary }}

| Evidence Item | Finding | Strength |
|---------------|---------|----------|
| Approved Drugs | {{ drug_approved }} | {{ drug_approved_strength }} |
| Clinical Candidates | {{ drug_clinical }} | {{ drug_clinical_strength }} |
| Active Compounds | {{ drug_compounds }} | {{ drug_compounds_strength }} |
| Modality Fit | {{ drug_modality }} | {{ drug_modality_strength }} |
| Clinical Trials (Active) | {{ drug_trials }} | {{ drug_trials_strength }} |
| Differentiation Opportunity | {{ drug_diff }} | {{ drug_diff_strength }} |

**Druggability Score: {{ score_druggability }} / {{ max_druggability }}**
**Clinical/Competitive Score: {{ score_clinical }} / {{ max_clinical }}**

---

## 9. Final Recommendation · 最终建议

### Is this target worth pursuing?

{{ final_judgment }}

### Recommended scenarios:
{{ recommended_scenarios }}

### Suggested next steps:
{{ next_steps }}

### Missing evidence to address:
{{ missing_evidence }}

---

## Appendix

### Data Sources
{{ data_sources }}

### Scoring Methodology
Scores are computed based on the **{{ scenario_label }}** scenario weighting. Each dimension is scored on its own scale and weighted according to the scenario. The weighted sum is normalized to a 100-point scale.

### Disclaimer
This report is an automated pre-screening tool. All conclusions are based on publicly available data and should be independently verified. This report does NOT constitute a guarantee that the target will be successful in research or drug development. Key decisions should be supported by additional experimental validation and expert consultation.

---

*Report generated by Target Assessment Tool · 靶点价值评估器*
*{{ report_date }}*
