"""
LLM Assessor - LLM 综合评估模块

Uses an LLM (via OpenAI-compatible API) to generate comprehensive,
evidence-aware target assessment reports, replacing template-based
recommendations with nuanced reasoning across all 8 dimensions.
"""

import json
import logging
from typing import Optional

from openai import OpenAI

from config import (
    LLM_ENABLED,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_TIMEOUT,
    LLM_TEMPERATURE,
    LLM_LANGUAGE,
    is_llm_available,
)

logger = logging.getLogger(__name__)

# ── Prompt templates ───────────────────────────────────────────────────────

SYSTEM_PROMPT_ZH = """你是一位资深药物靶点评估专家，拥有20年制药行业研发经验。你的任务是基于提供的多维度证据，对靶点进行综合性评估。

评估原则：
1. 基于证据，不做无根据的推测
2. 关注维度间的关联（如高表达+强依赖性=功能重要性）
3. 识别证据中的矛盾或缺口
4. 根据scenario给出差异化建议（research / drug_development / adc / small_molecule）
5. 对已验证药靶（有批准药物），承认其临床验证价值，同时指出差异化开发的机会
6. 对癌症生物学证据薄弱的非癌靶点，明确指出评估场景的局限性

输出格式：严格按以下JSON格式返回，不要输出其他内容：
{
  "summary": "一段话综合总结（150-250字），涵盖靶点与疾病的关联强度、核心证据亮点、关键风险",
  "strengths": ["优势1", "优势2", "优势3"],
  "weaknesses": ["不足1", "不足2", "不足3"],
  "recommendation": "具体可操作的推进建议（150-250字），包含下一步实验/数据补充方向、差异化策略、注意事项"
}"""

SYSTEM_PROMPT_EN = """You are a senior drug target assessment expert with 20 years of pharmaceutical R&D experience. Your task is to comprehensively evaluate a drug target based on multi-dimensional evidence provided.

Assessment principles:
1. Base conclusions on evidence, do not speculate without data
2. Focus on cross-dimension relationships (e.g., high expression + strong dependency = functional importance)
3. Identify contradictions or gaps in evidence
4. Provide differentiated recommendations based on scenario (research / drug_development / adc / small_molecule)
5. For validated drug targets (with approved drugs), acknowledge clinical validation while identifying differentiation opportunities
6. For non-cancer targets with weak cancer biology evidence, clearly state the limitations of the assessment context

Output format: Return strictly in the following JSON format, nothing else:
{
  "summary": "A comprehensive paragraph summary (100-200 words) covering target-disease association strength, key evidence highlights, and critical risks",
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "weaknesses": ["weakness 1", "weakness 2", "weakness 3"],
  "recommendation": "Specific actionable recommendations (100-200 words) including next experimental/data steps, differentiation strategy, and cautions"
}"""

USER_PROMPT_ZH = """## 评估场景
- 靶点基因: {gene_symbol}
- 适应症/疾病: {disease}
- 评估场景: {scenario}
- 靶点原型: {archetype}

## 评分结果
- 总评分: {total_score}/100
- 等级: {grade} ({grade_text})

### 各维度得分:

{dimension_scores}

### 各维度证据详情:

#### 疾病相关性 (Disease Relevance)
- 肿瘤过表达: {dr_overexpression}
- 预后关联: {dr_prognostic}
- 突变/CNV频率: {dr_mutation_freq}
- Open Targets关联: {dr_ot_association}
- 文献水平: {dr_literature}

#### 表达谱 (Expression)
- 肿瘤表达水平: {expr_tumor}
- 肿瘤vs正常差异: {expr_tn_diff}
- 蛋白证据: {expr_protein}
- 组织特异性: {expr_specificity}

#### 功能依赖性 (Dependency)
- 靶点癌症依赖性: {dep_level}
- 泛癌选择性: {dep_pancancer}
- 是否为通用必需基因: {dep_common_essential}
- 突变条件依赖性: {dep_mutation_cond}

#### 机制学 (Mechanism)
- 相关通路数: {mech_pathways}
- 机制强度: {mech_strength}
- 连接疾病标志性通路: {mech_hallmarks}

#### 可药性 (Druggability)
- 已批准药物数: {drug_approved}
- 临床候选分子数: {drug_clinical}
- 活性化合物数: {drug_active}
- 模态匹配度: {drug_modality}

#### 安全性 (Safety)
- 正常组织风险: {safety_normal_risk}
- 通用必需基因: {safety_common_essential}
- 关键器官表达: {safety_critical_organs}

#### 临床竞争 (Clinical Competition)
- 已批准药物数: {comp_approved}
- 活跃临床试验数: {comp_trials}
- 差异化机会: {comp_diff}

#### 场景匹配度 (Scenario Fit)
- 评估场景: {scenario}

请基于以上证据，给出综合性评估报告。"""

USER_PROMPT_EN = """## Assessment Context
- Target Gene: {gene_symbol}
- Disease/Indication: {disease}
- Assessment Scenario: {scenario}
- Target Archetype: {archetype}

## Scoring Results
- Total Score: {total_score}/100
- Grade: {grade} ({grade_text})

### Dimension Scores:

{dimension_scores}

### Evidence Details:

#### Disease Relevance
- Tumor Overexpression: {dr_overexpression}
- Prognostic Association: {dr_prognostic}
- Mutation/CNV Frequency: {dr_mutation_freq}
- Open Targets Association: {dr_ot_association}
- Literature Level: {dr_literature}

#### Expression
- Tumor Expression Level: {expr_tumor}
- Tumor vs Normal Difference: {expr_tn_diff}
- Protein Evidence: {expr_protein}
- Tissue Specificity: {expr_specificity}

#### Dependency
- Target Cancer Dependency: {dep_level}
- Pan-Cancer Selectivity: {dep_pancancer}
- Common Essential Gene: {dep_common_essential}
- Mutation-Conditioned Dependency: {dep_mutation_cond}

#### Mechanism
- Relevant Pathway Count: {mech_pathways}
- Mechanism Strength: {mech_strength}
- Connects to Disease Hallmarks: {mech_hallmarks}

#### Druggability
- Approved Drugs: {drug_approved}
- Clinical Candidates: {drug_clinical}
- Active Compounds: {drug_active}
- Modality Fit: {drug_modality}

#### Safety
- Normal Tissue Risk: {safety_normal_risk}
- Common Essential Gene: {safety_common_essential}
- Critical Organ Expression: {safety_critical_organs}

#### Clinical Competition
- Approved Drugs Count: {comp_approved}
- Active Clinical Trials: {comp_trials}
- Differentiation Opportunity: {comp_diff}

#### Scenario Fit
- Assessment Scenario: {scenario}

Based on the above evidence, provide a comprehensive assessment report."""


class LLMAssessor:
    """Generate comprehensive target assessments using an LLM."""

    def __init__(self):
        self._client: Optional[OpenAI] = None

    @property
    def available(self) -> bool:
        return is_llm_available()

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=LLM_API_KEY,
                base_url=LLM_BASE_URL,
                timeout=LLM_TIMEOUT,
            )
        return self._client

    def generate_assessment(
        self,
        gene_symbol: str,
        disease: str,
        evidence: dict,
        scores: dict,
        total_score: float,
        grade: str,
        grade_text: str,
        archetype: str,
        scenario: str,
    ) -> Optional[str]:
        """
        Generate a comprehensive LLM-based assessment.

        Returns the assessment text, or None if LLM is unavailable
        or the call fails (caller should fall back to template).
        """
        if not self.available:
            logger.info("LLM assessor not configured, skipping")
            return None

        language = LLM_LANGUAGE
        if language not in ("zh", "en"):
            language = "zh"

        system_prompt = SYSTEM_PROMPT_ZH if language == "zh" else SYSTEM_PROMPT_EN
        user_template = USER_PROMPT_ZH if language == "zh" else USER_PROMPT_EN

        # ── Build dimension scores table ──────────────────────────────
        dim_labels_zh = {
            "disease_relevance": "疾病相关性",
            "expression": "表达谱",
            "dependency": "功能依赖性",
            "mechanism": "机制学",
            "druggability": "可药性",
            "safety": "安全性",
            "clinical_competition": "临床竞争",
            "scenario_fit": "场景匹配度",
        }
        dim_labels_en = {
            "disease_relevance": "Disease Relevance",
            "expression": "Expression",
            "dependency": "Dependency",
            "mechanism": "Mechanism",
            "druggability": "Druggability",
            "safety": "Safety",
            "clinical_competition": "Clinical Competition",
            "scenario_fit": "Scenario Fit",
        }
        dim_labels = dim_labels_zh if language == "zh" else dim_labels_en
        dim_max = scores.get("dimension_max", {})

        dim_lines = []
        for key, label in dim_labels.items():
            raw = scores.get("scores", {}).get(key, 0)
            mx = dim_max.get(key, 1)
            dim_lines.append(f"- {label}: {raw}/{mx}")
        dimension_scores_str = "\n".join(dim_lines)

        # ── Extract evidence fields ───────────────────────────────────
        dr = evidence.get("disease_relevance", {})
        expr = evidence.get("expression", {})
        dep = evidence.get("dependency", {})
        mech = evidence.get("mechanism", {})
        drug = evidence.get("druggability", {})
        safety = evidence.get("safety", {})
        comp = evidence.get("clinical_competition", {})

        user_prompt = user_template.format(
            gene_symbol=gene_symbol,
            disease=disease,
            scenario=scenario,
            archetype=archetype,
            total_score=total_score,
            grade=grade,
            grade_text=grade_text,
            dimension_scores=dimension_scores_str,
            dr_overexpression=dr.get("target_cancer_overexpression", "unknown"),
            dr_prognostic=dr.get("prognostic_associated", False),
            dr_mutation_freq=dr.get("mutation_cnv_frequency", 0),
            dr_ot_association=dr.get("opentargets_association", False),
            dr_literature=dr.get("literature_level", "unknown"),
            expr_tumor=expr.get("tumor_expression", "unknown"),
            expr_tn_diff=expr.get("tumor_normal_diff", "unknown"),
            expr_protein=expr.get("protein_evidence", False),
            expr_specificity=expr.get("tissue_specificity", "unknown"),
            dep_level=dep.get("target_cancer_dependency", "unknown"),
            dep_pancancer=dep.get("pan_cancer_rank", "unknown"),
            dep_common_essential=dep.get("is_common_essential", False),
            dep_mutation_cond=dep.get("mutation_conditioned_dep", False),
            mech_pathways=mech.get("relevant_pathway_count", 0),
            mech_strength=mech.get("mechanism_strength", "unknown"),
            mech_hallmarks=mech.get("connects_to_disease_hallmarks", False),
            drug_approved=drug.get("approved_drugs", 0),
            drug_clinical=drug.get("clinical_candidates", 0),
            drug_active=drug.get("active_compounds", 0),
            drug_modality=drug.get("modality_fit", "unknown"),
            safety_normal_risk=safety.get("normal_tissue_risk", "unknown"),
            safety_common_essential=safety.get("is_common_essential", False),
            safety_critical_organs=safety.get("critical_organ_expression", []),
            comp_approved=comp.get("approved_drugs_count", 0),
            comp_trials=comp.get("active_clinical_trials", 0),
            comp_diff=comp.get("differentiation_opportunity", "unknown"),
        )

        # ── Call LLM ──────────────────────────────────────────────────
        try:
            logger.info(
                f"Calling LLM ({LLM_MODEL}) for {gene_symbol} in {disease}"
            )
            response = self.client.chat.completions.create(
                model=LLM_MODEL,
                temperature=LLM_TEMPERATURE,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=LLM_TIMEOUT,
            )

            raw = response.choices[0].message.content
            if raw is None:
                logger.warning("LLM returned empty response")
                return None

            # Strip markdown code fences if present
            raw = raw.strip()
            if raw.startswith("```"):
                # Remove ```json ... ``` wrapper
                lines = raw.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw = "\n".join(lines)

            parsed = json.loads(raw)

            # ── Format for display ────────────────────────────────────
            summary = parsed.get("summary", "")
            strengths = parsed.get("strengths", [])
            weaknesses = parsed.get("weaknesses", [])
            recommendation = parsed.get("recommendation", "")

            lines_out = []
            if summary:
                lines_out.append(summary)
            if strengths:
                if language == "zh":
                    lines_out.append("\n**核心优势：**")
                else:
                    lines_out.append("\n**Key Strengths:**")
                for s in strengths:
                    lines_out.append(f"  • {s}")
            if weaknesses:
                if language == "zh":
                    lines_out.append("\n**主要不足/风险：**")
                else:
                    lines_out.append("\n**Key Weaknesses/Risks:**")
                for w in weaknesses:
                    lines_out.append(f"  • {w}")
            if recommendation:
                if language == "zh":
                    lines_out.append(f"\n**推进建议：**\n{recommendation}")
                else:
                    lines_out.append(f"\n**Recommendations:**\n{recommendation}")

            result = "\n".join(lines_out)
            logger.info(f"LLM assessment generated ({len(result)} chars)")
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM JSON response: {e}")
            return None
        except Exception as e:
            logger.warning(f"LLM call failed: {e}")
            return None
