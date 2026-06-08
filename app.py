"""
Target Assessment Tool - 靶点价值评估器

Streamlit web application for evaluating target gene value
across multiple dimensions for research and drug development.
"""

import sys
import os

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from modules.gene_resolver import GeneResolver
from modules.scoring_engine import ScoringEngine
from modules.report_generator import ReportGenerator
from modules.data_manager import DataManager

# Page config
st.set_page_config(
    page_title="靶点价值评估器 · Target Assessment Tool",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state initialization - persists across re-runs
# ---------------------------------------------------------------------------

if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "results" not in st.session_state:
    st.session_state.results = None

# ---------------------------------------------------------------------------
# Sidebar - About & Instructions
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("# 🎯 靶点价值评估器")
    st.markdown("*Target Assessment Tool*")
    st.markdown("---")
    st.markdown(
        "输入一个靶点基因和疾病/癌种，从**疾病相关性、表达谱、"
        "功能依赖性、机制通路、可药性、安全性、临床格局**等"
        "多维度快速生成靶点价值评估报告。"
    )
    st.markdown("---")

    # Available sample targets
    dm_info = DataManager()
    available = dm_info.list_available_targets()
    st.markdown("### 📋 MVP 示例靶点")
    for t in available:
        st.markdown(f"- **{t['gene']}** · {t['disease']}")

    st.markdown("---")
    st.markdown("### 🔬 评估维度")
    dims = [
        "疾病相关性 (15分)",
        "表达谱证据 (15分)",
        "功能依赖性 (15分)",
        "机制通路证据 (15分)",
        "可药性 (15分)",
        "安全性风险 (10分)",
        "临床竞品格局 (10分)",
        "场景匹配度 (5分)",
    ]
    for d in dims:
        st.markdown(f"- {d}")

    st.markdown("---")
    st.caption("MVP v0.1.0 · 靶点初筛版")

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

st.title("🎯 靶点价值评估器")
st.markdown("*Target Assessment Tool — 输入一个靶点，快速评估其科研和药物开发价值*")

st.markdown("---")

# ---------------------------------------------------------------------------
# Input form
# ---------------------------------------------------------------------------

col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    gene_input = st.text_input(
        "🔬 Target Gene · 靶点基因",
        placeholder="e.g., EGFR, HER2, CLDN18, KRAS, BRCA1...",
        help="输入基因符号（HGNC symbol），支持常用别名",
    )

with col2:
    disease_input = st.text_input(
        "🩺 Disease / Cancer Type · 疾病/癌种",
        placeholder="e.g., NSCLC, Breast Cancer, Gastric Cancer...",
        help="输入疾病名称或癌种，用于限定评估背景",
    )

with col3:
    scenario = st.selectbox(
        "🎯 Scenario · 评估场景",
        options=["research", "drug_development", "adc", "small_molecule", "general"],
        format_func=lambda x: {
            "research": "科研基金/SCI",
            "drug_development": "药物研发立项",
            "adc": "ADC/抗体靶点",
            "small_molecule": "小分子靶点",
            "general": "通用评估",
        }[x],
        help="选择评估场景以调整各维度权重",
    )

modality = st.selectbox(
    "💊 Modality · 药物形式（可选）",
    options=["any", "small_molecule", "antibody", "adc", "protac", "rna"],
    format_func=lambda x: {
        "any": "不限",
        "small_molecule": "小分子",
        "antibody": "抗体",
        "adc": "ADC",
        "protac": "PROTAC",
        "rna": "RNA药物",
    }[x],
    help="如关注特定药物形式，可在此选择",
)

st.markdown("")

submit_col, _, _ = st.columns([1, 3, 3])
with submit_col:
    submitted = st.button(
        "🚀 生成靶点评估报告",
        type="primary",
        use_container_width=True,
    )

st.markdown("---")

# ---------------------------------------------------------------------------
# Process and display results
# ---------------------------------------------------------------------------

if submitted:
    if not gene_input.strip():
        st.error("请输入靶点基因符号")
    elif not disease_input.strip():
        st.error("请输入疾病/癌种名称")
    else:
        with st.spinner("正在评估靶点价值..."):
            # Step 1: Resolve gene symbol
            with GeneResolver() as resolver:
                gene_info = resolver.resolve(gene_input.strip())

            if gene_info.status == "empty_input":
                st.error("请输入有效的基因符号")
                st.stop()

            target_symbol = gene_info.symbol

            # Step 2: Collect evidence
            dm = DataManager()
            evidence = dm.collect_evidence(
                target_symbol,
                disease_input.strip(),
                scenario,
                ensembl_id=gene_info.ensembl_id,
            )

            # Step 3: Score
            engine = ScoringEngine(scenario=scenario)
            score_result = engine.score(evidence)

            # Step 4: Generate report
            gen = ReportGenerator()
            markdown_report = gen.generate_markdown(
                target_symbol=target_symbol,
                disease=disease_input.strip(),
                gene_info=gene_info.to_dict(),
                evidence=evidence,
                score_result=score_result,
            )

        # Store results in session state so they persist across re-runs
        st.session_state.submitted = True
        st.session_state.results = {
            "target_symbol": target_symbol,
            "gene_info": gene_info,
            "disease_input": disease_input.strip(),
            "scenario": scenario,
            "score_result": score_result,
            "evidence": evidence,
            "markdown_report": markdown_report,
        }

# ------------------------------------------------------------------
# Display results (from session state, survives re-runs)
# ------------------------------------------------------------------

if st.session_state.submitted and st.session_state.results is not None:
    r = st.session_state.results
    target_symbol = r["target_symbol"]
    gene_info = r["gene_info"]
    disease_input_val = r["disease_input"]
    scenario_val = r["scenario"]
    score_result = r["score_result"]
    evidence = r["evidence"]
    markdown_report = r["markdown_report"]

    # Top summary cards
    st.markdown("## 📊 评估结果")

    card_col1, card_col2, card_col3, card_col4 = st.columns(4)

    with card_col1:
        st.metric(
            label="靶点",
            value=target_symbol,
            delta=gene_info.full_name[:30] + "..." if len(gene_info.full_name) > 30 else gene_info.full_name,
        )

    with card_col2:
        st.metric(
            label="总分",
            value=f"{score_result['total_score']}/100",
        )

    with card_col3:
        grade_color = {
            "A": "green",
            "B": "blue",
            "C": "orange",
            "D": "red",
            "E": "red",
        }.get(score_result["grade"], "gray")
        st.markdown(
            f"**推荐等级**\n\n"
            f"### :{grade_color}[{score_result['grade']}]"
        )

    with card_col4:
        st.metric(
            label="场景",
            value={
                "research": "基金/SCI",
                "drug_development": "药物研发",
                "adc": "ADC评估",
                "small_molecule": "小分子",
                "general": "通用",
            }.get(scenario_val, scenario_val),
        )

    st.markdown("---")

    # Recommendation
    st.markdown("### 💡 一句话结论")
    st.info(score_result["recommendation"])

    # Radar chart + Score table
    chart_col, table_col = st.columns([1, 1])

    with chart_col:
        st.markdown("#### 多维评分雷达图")
        scores = score_result["scores"]
        dim_labels = {
            "disease_relevance": "疾病相关性",
            "expression": "表达谱",
            "dependency": "依赖性",
            "mechanism": "机制通路",
            "druggability": "可药性",
            "safety": "安全性",
            "clinical_competition": "临床格局",
            "scenario_fit": "场景匹配",
        }
        dim_maxes = {
            "disease_relevance": 15,
            "expression": 15,
            "dependency": 15,
            "mechanism": 15,
            "druggability": 15,
            "safety": 10,
            "clinical_competition": 10,
            "scenario_fit": 5,
        }

        categories = [dim_labels.get(k, k) for k in scores.keys()]
        values = [scores[k] / dim_maxes[k] * 100 for k in scores.keys()]

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=categories,
            fill='toself',
            name=target_symbol,
            line_color='#3182ce',
            fillcolor='rgba(49, 130, 206, 0.3)',
        ))
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                ),
            ),
            showlegend=False,
            height=400,
            margin=dict(l=60, r=60, t=30, b=30),
        )
        st.plotly_chart(fig, use_container_width=True)

    with table_col:
        st.markdown("#### 各维度得分明细")
        score_data = []
        for k in scores.keys():
            max_s = dim_maxes[k]
            s = scores[k]
            pct = s / max_s if max_s > 0 else 0
            score_data.append({
                "维度": dim_labels.get(k, k),
                "得分": f"{s}/{max_s}",
                "百分比": f"{pct:.0%}",
            })

        df_scores = pd.DataFrame(score_data)
        st.dataframe(df_scores, use_container_width=True, hide_index=True)

        # Weight info
        weights = score_result.get("weights", {})
        weight_data = []
        for k, w in weights.items():
            weight_data.append({
                "维度": dim_labels.get(k, k),
                "权重": f"{w:.0%}",
            })
        df_weights = pd.DataFrame(weight_data)
        st.caption("场景权重配置")
        st.dataframe(df_weights, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Key Strengths & Risks
    strength_col, risk_col, missing_col = st.columns(3)

    with strength_col:
        st.markdown("#### ✅ 支持证据")
        strengths_found = False
        for dim_key in scores:
            s = scores[dim_key]
            max_s = dim_maxes[dim_key]
            if s >= max_s * 0.6:
                strengths_found = True
                st.success(f"**{dim_labels[dim_key]}**: {s}/{max_s}")
        if not strengths_found:
            st.caption("暂无突出优势维度")

    with risk_col:
        st.markdown("#### ⚠️ 风险证据")
        risks_found = False
        risk_dims = {
            "safety": 7,
            "dependency": 8,
            "druggability": 8,
            "clinical_competition": 5,
        }
        for dim_key, threshold in risk_dims.items():
            s = scores.get(dim_key, 0)
            max_s = dim_maxes[dim_key]
            if s < threshold:
                risks_found = True
                st.warning(f"**{dim_labels[dim_key]}**: {s}/{max_s} (阈值: {threshold})")
        if not risks_found:
            st.caption("暂无高风险维度")

    with missing_col:
        st.markdown("#### 🔍 缺失证据")
        missing_found = False
        for dim_key in scores:
            s = scores[dim_key]
            max_s = dim_maxes[dim_key]
            if s < max_s * 0.4:
                missing_found = True
                st.info(f"**{dim_labels[dim_key]}**: 需补充数据")
        if not missing_found:
            st.caption("各维度证据相对完整")

    st.markdown("---")

    # Download buttons
    st.markdown("### 📥 下载报告")

    dl_col1, dl_col2, dl_col3 = st.columns(3)

    gen = ReportGenerator()

    with dl_col1:
        # Save markdown and offer download
        md_path = gen.save_markdown(markdown_report)
        with open(md_path, "r", encoding="utf-8") as f:
            st.download_button(
                label="📝 下载 Markdown 报告",
                data=f.read(),
                file_name=f"target_assessment_{target_symbol}_{disease_input_val.replace(' ', '_')}.md",
                mime="text/markdown",
                use_container_width=True,
            )

    with dl_col2:
        html_report = gen.export_html(markdown_report)
        st.download_button(
            label="🌐 下载 HTML 报告",
            data=html_report,
            file_name=f"target_assessment_{target_symbol}.html",
            mime="text/html",
            use_container_width=True,
        )

    with dl_col3:
        from config import TABLES_DIR
        xlsx_path = os.path.join(
            str(TABLES_DIR),
            f"evidence_{target_symbol}_{disease_input_val.replace(' ', '_')}.xlsx"
        )
        gen.export_excel(evidence, score_result, output_path=xlsx_path)
        with open(xlsx_path, "rb") as f:
            st.download_button(
                label="📊 下载 Excel 证据表",
                data=f.read(),
                file_name=f"evidence_{target_symbol}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    st.markdown("---")

    # CTA for human-enhanced version
    st.markdown("### 🔬 需要更深入的分析？")
    cta_col1, cta_col2 = st.columns([3, 1])
    with cta_col1:
        st.markdown(
            "当前报告为**自动化初筛结果**，适合快速判断靶点是否值得继续深挖。"
            "如需形成**基金前期基础报告、SCI机制故事线、企业靶点立项报告**或"
            "**适应症优先级分析**，可申请人工增强版。"
        )
    with cta_col2:
        st.button("📩 申请人工增强版", type="secondary", use_container_width=True)

    st.markdown("---")

    # Full report in expander
    with st.expander("📄 查看完整报告文本"):
        st.markdown(markdown_report)

else:
    # Show placeholder when no query yet
    st.markdown("### 👆 请在上方输入靶点基因和疾病信息，然后点击生成报告")

    # Quick start examples
    st.markdown("#### 快速开始示例")
    example_cols = st.columns(3)

    with example_cols[0]:
        st.info(
            "**EGFR + NSCLC**\n\n"
            "经典靶点，验证 druggability 和 clinical 模块。"
        )
    with example_cols[1]:
        st.success(
            "**CLDN18 + Gastric Cancer**\n\n"
            "热门 ADC / 抗体靶点，新兴机会场景。"
        )
    with example_cols[2]:
        st.warning(
            "**BRCA1 + Ovarian Cancer**\n\n"
            "DNA repair / 合成致死场景，肿瘤抑制基因评估。"
        )

    st.markdown("---")
    st.caption(
        "MVP v0.1.0 · 当前版本使用预编译示例数据，覆盖 6 个靶点。"
        "更多靶点将在后续版本中通过实时数据库查询支持。"
    )
