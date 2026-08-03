# Target Assessment Tool · 靶点价值评估器

输入一个靶点基因和疾病/癌种，从多维度自动生成靶点价值评估报告，帮助判断：**这个靶点是否值得继续做、在哪个适应症中最有潜力、下一步应该补什么证据。**

Given a target gene and disease/cancer type, this tool automatically generates a multi-dimensional target assessment report to help answer: **is this target worth pursuing, which indication has the most potential, and what evidence gaps need to be filled next.**

---

## Table of Contents

- [Quick Start](#quick-start)
- [What This Tool Does](#what-this-tool-does)
- [Offline Database 离线数据库](#offline-database)
- [Data Sources](#data-sources)
- [Scoring Model](#scoring-model)
- [Result Interpretation](#result-interpretation)
- [Web App Usage](#web-app-usage)
- [CLI Usage](#cli-usage)
- [Project Architecture](#project-architecture)
- [Maintenance Guide](#maintenance-guide)
- [FAQ](#faq)

---

## Quick Start

```bash
# Install dependencies  安装依赖
pip install -r requirements.txt

# Build offline database (first time only — do once, then run offline forever)
# 构建离线数据库（仅首次需要 — 完成后即可永久离线运行）
python3.8 data/build_offline_db.py

# CLI — quick assessment from command line
# 命令行快速评估
python3.8 run.py --gene EGFR --disease NSCLC

# Web app — interactive browser interface
# Web 交互界面
streamlit run app.py
```

### CLI vs Web App

| | CLI (`run.py`) | Web App (`app.py`) |
|---|---|---|
| **Interface / 界面** | Terminal / 终端 | Browser (Streamlit) / 浏览器 |
| **Use case / 用途** | Batch evaluation, scripting, quick lookups / 批量评估、脚本、快速查询 | Interactive exploration, presentations / 交互探索、演示 |
| **Output / 输出** | Prints summary to stdout + saves files / 终端打印 + 保存文件 | Interactive charts + download buttons / 交互图表 + 下载按钮 |
| **Best for / 适合** | Power users, automation / 高级用户、自动化 | First-time users, demos / 新用户、演示 |

---

### Requirements / 环境要求

- Python 3.8+
- Offline mode / 离线模式：**no internet required** / 无需联网（recommended / 推荐）
- Online fallback / 联网备用：internet access required only when SQLite DB is absent / 仅在无 SQLite 数据库时需要
- Dependencies / 依赖包：`streamlit`, `pandas`, `numpy`, `httpx`, `plotly`, `openpyxl`, `markdown`, `weasyprint`

---

## What This Tool Does

This is a **multi-dimensional target assessment engine** for drug discovery and biomedical research. Given a gene symbol and a disease/cancer type, it:

1. **Resolves** the gene symbol to an official HGNC identifier (offline DB → mygene.info API fallback)
2. **Collects evidence** from the offline SQLite database (primary) or live APIs (fallback)
3. **Scores** the target across 8 dimensions with scenario-based weighting
4. **Generates** a structured report (Markdown / HTML / Excel)

The tool is designed as a **decision-support system** — it helps researchers and drug developers quickly triage targets before investing in deep manual curation.

---

这是一个**多维靶点评估引擎**，用于药物发现和生物医学研究。输入基因符号和疾病/癌种后，它会：

1. **解析**基因符号为标准化 HGNC 标识符（离线数据库 → mygene.info API 兜底）
2. **收集**来自离线 SQLite 数据库（主路径）或在线 API（备用）的多方证据
3. **评分**：基于场景权重对 8 个维度进行加权评分
4. **生成**结构化报告（Markdown / HTML / Excel）

该工具定位为**决策支持系统**，帮助研究人员和药物开发者在投入深度人工调研之前，快速筛选靶点。

---

## Offline Database 离线数据库

The offline SQLite database (`data/processed/target_assessment.db`) bundles all evidence data into a single ~1.2 GB file, enabling **sub-second queries without any network access**.

离线 SQLite 数据库（`data/processed/target_assessment.db`）将所有证据数据打包到单个约 1.2 GB 文件中，实现**亚秒级查询，完全无需网络**。

### Database Contents / 数据库内容

| Table / 表 | Rows / 行数 | Source / 来源 | Description / 说明 |
|-------------|-------------|---------------|---------------------|
| `genes` | ~194,000 | NCBI Gene | Gene symbols, Ensembl IDs, aliases / 基因符号、Ensembl ID、别名 |
| `opentargets` | ~500,000 | Open Targets Platform | Target-disease association scores / 靶点-疾病关联评分 |
| `chembl_drugs` | ~2,000 | ChEMBL | Approved/clinical/active drug counts per target / 每个靶点的已批准/临床/活性药物数 |
| `depmap_crispr` | ~18,000 | DepMap | CRISPR dependency scores by cancer type / 按癌种分类的 CRISPR 依赖性评分 |
| `tcga_expression` | ~20,000 | TCGA | Tumor expression (TPM, log2FC) by cancer type / 按癌种分类的肿瘤表达数据 |
| `tcga_mutation` | ~20,000 | TCGA | Mutation & CNV frequencies by cancer type / 按癌种分类的突变和拷贝数变异频率 |

### Building the Database / 构建数据库

**First-time build / 首次构建** (requires network / 需要网络):

```bash
# Full build — downloads all upstream data (~1.5 GB download)
# 完整构建 — 下载所有上游数据（约 1.5 GB 下载量）
python3.8 data/build_offline_db.py

# Build only with local CSV files (no external downloads)
# 仅使用本地 CSV 文件构建（不下载外部数据）
python3.8 data/build_offline_db.py --only-local

# Build only the genes table
# 仅构建基因表
python3.8 data/build_offline_db.py --only-genes
```

### Updating the Database / 更新数据库

When upstream data sources release new versions, you can update individual tables without rebuilding everything:

当上游数据源发布新版本时，你可以单独更新各个表，无需重建整个数据库：

```bash
# Update specific tables / 更新特定表
python3.8 data/update_offline_db.py --table depmap_crispr      # DepMap CRISPR data
python3.8 data/update_offline_db.py --table tcga                # Both TCGA tables
python3.8 data/update_offline_db.py --table genes               # NCBI gene info
python3.8 data/update_offline_db.py --table opentargets         # Open Targets associations
python3.8 data/update_offline_db.py --table chembl              # ChEMBL drug counts

# Dry-run — check what would be updated without making changes
# 预演模式 — 检查哪些内容会被更新，不实际修改
python3.8 data/update_offline_db.py --table depmap_crispr --dry-run

# Full rebuild with backup / 全量重建并备份
python3.8 data/update_offline_db.py --full
```

The update script:
- **Backs up** the existing database before making changes
- **Validates** the updated table after import (row count, schema check)
- **Supports rollback** if validation fails
- Updates **in-place** on the existing database (no full rebuild needed for single tables)

更新脚本会：
- 修改前**备份**现有数据库
- 导入后**验证**更新后的表（行数、schema 检查）
- 验证失败时**支持回滚**
- 对现有数据库**原地更新**（单表无需全量重建）

### Typical Update Cadence / 典型更新周期

| Data Source / 数据源 | Update Frequency / 更新频率 | When to Update / 何时更新 |
|----------------------|----------------------------|--------------------------|
| NCBI Gene | Quarterly / 每季度 | When new gene annotations are released |
| DepMap | Quarterly / 每季度 | When new CRISPR screen releases drop (e.g., 24Q4) |
| TCGA | Rarely / 很少 | TCGA data is relatively stable; update if reprocessed |
| Open Targets | Monthly / 每月 | Platform releases are monthly; significant changes quarterly |
| ChEMBL | Quarterly / 每季度 | New ChEMBL versions (e.g., 37 → 38) |

---

## Data Sources / 数据来源

### Primary: Offline SQLite Database / 离线 SQLite 数据库（主路径）

When `data/processed/target_assessment.db` exists, all evidence is queried from it directly with **sub-second latency and zero network calls**. See [Offline Database](#offline-database) above.

数据库存在时，所有证据直接从 SQLite 查询，**亚秒级延迟，零网络调用**。详见上方离线数据库章节。

### Fallback: Live APIs / 在线 API（备用路径）

If the offline database is not available, the tool falls back to live API queries:

如果离线数据库不可用，工具回退到在线 API 查询：

| Source / 来源 | Method | What It Provides / 提供内容 | Rate Limit |
|--------|--------|---------------------------|------------|
| **Open Targets Platform** | GraphQL API | Target-disease association score (0–1), evidence breakdown by type | No strict limit |
| **ChEMBL** | REST API | Drug counts by phase, modality fit assessment | ~1 request/s |
| **ClinicalTrials.gov** | REST API v2 | Active clinical trial counts, differentiation opportunity | ~50 requests/min |
| **mygene.info** | REST API | Gene symbol resolution, Ensembl ID lookup | No strict limit |

### Local Data Files / 本地数据文件

| Source / 来源 | File / 文件 | What It Provides / 提供内容 |
|--------|------|---------------------------|
| **DepMap** | `data/processed/depmap_crispr_summary.csv` | CRISPR gene effect scores (Chronos), selectivity, percentile ranks |
| **TCGA** | `data/processed/tcga_expression_summary.csv` | Median TPM (tumor/normal), log2FC, overexpression category |
| **TCGA** | `data/processed/tcga_mutation_summary.csv` | Mutation frequency, CNV amp/del frequency, prognostic association |

### Sample Data (fallback) / 示例数据（兜底）

Pre-curated evidence for canonical targets (EGFR, ERBB2, CLDN18, MUC1, BRCA1, KRAS) in `modules/sample_data.py`. Used to fill gaps when real data returns sparse results for well-known targets.

预置的经典靶点证据（EGFR, ERBB2, CLDN18, MUC1, BRCA1, KRAS）在 `modules/sample_data.py` 中。用于补充知名靶点在实际数据中稀疏的字段。

### Evidence Collection Priority / 证据收集优先级

```
Offline SQLite DB (primary, <1s)  →  Sample Data (enrichment)  →  Generic Template (fallback)
     ↓ (if DB unavailable)
Live APIs (fallback, 5–15s)
```

---

## Scoring Model / 评分模型

### Overview / 概述

The total score is a **weighted sum of 8 dimension scores**, normalized to 0–100.

总分是**8个维度分数的加权求和**，归一化到 0–100。

### Formula / 公式

```
Total Score = Σ ( dimension_raw_score / dimension_max × dimension_weight ) × 100
```

Where:
- `dimension_raw_score` — raw score for each dimension (0 to dimension_max)
- `dimension_max` — maximum possible raw score for that dimension
- `dimension_weight` — scenario-dependent weight (sum of all weights = 1.0)

### Dimension Max Scores & Weights by Scenario

| Dimension / 维度 | Max | general | research | drug_dev | adc | small_mol |
|-----------|-----|---------|----------|----------|-----|-----------|
| disease_relevance 疾病相关性 | 15 | 0.15 | **0.20** | 0.15 | 0.10 | 0.10 |
| expression 表达谱 | 15 | 0.15 | 0.15 | 0.15 | **0.25** | 0.10 |
| dependency 依赖性 | 15 | 0.15 | 0.10 | 0.15 | 0.10 | 0.15 |
| mechanism 机制通路 | 15 | 0.15 | **0.20** | 0.10 | 0.05 | 0.15 |
| druggability 可药性 | 15 | 0.15 | 0.10 | 0.15 | 0.20 | **0.25** |
| safety 安全性 | 10 | 0.10 | 0.10 | **0.15** | **0.20** | 0.15 |
| clinical_competition 临床格局 | 10 | 0.10 | 0.10 | 0.10 | 0.05 | 0.05 |
| scenario_fit 场景匹配 | 5 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 |
| **Sum / 合计** | | **1.00** | **1.00** | **1.00** | **1.00** | **1.00** |

### Dimension Scoring Rules / 维度评分规则

#### 1. Disease Relevance 疾病相关性 (max: 15 points)

Assesses how strongly the target is linked to the disease through expression, mutation, literature, and database annotations.

评估靶点通过表达、突变、文献和数据库注释与疾病的关联强度。

| Evidence / 证据 | Condition / 条件 | Points / 分值 |
|----------|-----------|--------|
| Target overexpression in cancer / 靶点过表达 | `"high"` 高 | +6.0 |
| | `"moderate"` 中 | +3.75 |
| | `"low"` 低 | +0.75 |
| Prognostic association / 预后关联 | True / 是 | +3.0 |
| Mutation/CNV frequency / 突变/CNV 频率 | > 10% | +3.0 |
| | > 3% | +1.5 |
| Open Targets association | score > 0.01 | +1.5 |
| Literature evidence / 文献证据 | `"high"` 高 | +1.5 |
| | `"moderate"` 中 | +0.75 |

#### 2. Expression Profile 表达谱 (max: 15 points)

Evaluates tumor expression level and tumor-vs-normal specificity — critical for ADC/antibody targets.

评估肿瘤表达水平和肿瘤-正常组织特异性 — 对 ADC/抗体靶点至关重要。

| Evidence / 证据 | Condition / 条件 | Points / 分值 |
|----------|-----------|--------|
| Tumor expression level / 肿瘤表达水平 | `"high"` 高 | +6.0 |
| | `"moderate"` 中 | +3.75 |
| | `"low"` 低 | +0.75 |
| Tumor-normal differential / 肿瘤-正常差异 | `"significant"` (log2FC > 2) | +4.5 |
| | `"moderate"` (log2FC > 1) | +2.25 |
| Protein-level evidence / 蛋白水平证据 | True / 是 | +2.25 |
| Tissue specificity / 组织特异性 | `"high"` 高 | +2.25 |
| | `"moderate"` 中 | +1.2 |

#### 3. Functional Dependency 功能性依赖 (max: 15 points)

Based on DepMap CRISPR knockout screens. Stronger dependency = more points. **Common essential genes are penalized** (capped at 30% of max).

基于 DepMap CRISPR 敲除筛选。依赖性越强越得分。**常见必需基因会被降权**（上限为最高分的 30%）。

| Evidence / 证据 | Condition / 条件 | Points / 分值 |
|----------|-----------|--------|
| Cancer dependency level / 癌症依赖性 | `"strong"` (Chronos < −0.5) | +7.5 |
| | `"moderate"` (Chronos < −0.3) | +4.5 |
| | `"weak"` (Chronos ≥ −0.3) | +1.5 |
| Pan-cancer selectivity / 泛癌选择性 | `"selective"` 选择性 | +3.75 |
| | `"moderate_selective"` 中等选择性 | +1.5 |
| **Common essential cap** / 常见必需基因上限 | If true | **max 4.5 pts total** |
| Mutation-conditioned dependency / 突变条件依赖 | True / 是 | +3.75 |

#### 4. Mechanism & Pathway Evidence 机制通路证据 (max: 15 points)

Evaluates biological rationale: how well-understood is the mechanism linking the target to the disease?

评估生物学机制：靶点与疾病关联的机制有多清晰？

| Evidence / 证据 | Condition / 条件 | Points / 分值 |
|----------|-----------|--------|
| Relevant pathway count / 相关通路数 | ≥ 3 pathways | +5.25 |
| | 1–2 pathways | +3.0 |
| Mechanism strength / 机制强度 | `"well_established"` 充分验证 | +5.25 |
| | `"partially_established"` 部分验证 | +3.0 |
| Connects to disease hallmarks / 连接疾病特征 | True / 是 | +4.5 |

#### 5. Druggability 可药性 (max: 15 points)

Assesses the existing drug development landscape for the target.

评估靶点已有的药物开发格局。

| Evidence / 证据 | Condition / 条件 | Points / 分值 |
|----------|-----------|--------|
| Approved drugs / 已批准药物 | ≥ 1 | +6.0 |
| Clinical candidates / 临床候选药物 | ≥ 1 | +3.75 |
| Active compounds / 活性化合物 | ≥ 1 | +2.25 |
| Modality fit / 形式匹配 | `"strong"` 强 | +3.0 |
| | `"moderate"` 中 | +1.5 |

#### 6. Safety Risk 安全性风险 (max: 10 points)

Starts at full score and deducts for safety concerns. **Higher score = safer.**

初始满分，从安全性风险中扣分。**分数越高 = 越安全。**

| Risk Factor / 风险因素 | Condition / 条件 | Penalty / 扣分 |
|-------------|-----------|---------|
| Normal tissue expression / 正常组织表达 | `"high"` 高 | −6.0 |
| | `"moderate"` 中 | −3.0 |
| | `"low"` 低 | −1.0 |
| Common essential gene / 常见必需基因 | True / 是 | −5.0 |
| Critical organ expression / 关键器官表达 | ≥ 2 organs | −3.0 |
| | 1 organ | −1.5 |

#### 7. Clinical & Competitive Landscape 临床格局 (max: 10 points)

Higher score = more validated target (not necessarily less competitive).

分数越高 = 靶点越被临床验证（不意味着竞争越小）。

| Evidence / 证据 | Condition / 条件 | Points / 分值 |
|----------|-----------|--------|
| Approved drugs (competition) / 已批准药物 | ≥ 2 | +5.0 |
| | 1 | +3.5 |
| Active clinical trials / 活跃临床试验 | ≥ 10 | +3.0 |
| | 3–9 | +1.5 |
| Differentiation opportunity / 差异化机会 | `"high"` 高 | +2.0 |
| | `"moderate"` 中 | +1.0 |

#### 8. Scenario Fit 场景匹配 (max: 5 points)

Bonus points for how well the target profile matches the chosen assessment scenario.

根据靶点特征与所选评估场景的匹配程度给予加分。

| Scenario / 场景 | Scoring Criteria / 评分标准 |
|----------|-----------------|
| **research** 基金/SCI | Literature level (+40%), mechanism strength (+40%), tumor expression (+20%) |
| **drug_development** 药物研发 | Modality fit (+35%), dependency (+35%), safety window (+30%) |
| **adc** ADC/抗体 | Protein evidence (+40%), tumor-normal differential (+35%), safety window (+25%) |
| **small_molecule** 小分子 | Modality fit (+40%), active compounds (+30%), mechanism (+30%) |
| **general** 通用 | Flat 50% baseline |

### Grade Assignment / 等级划分

| Score Range / 分数 | Grade / 等级 | Interpretation / 解释 |
|-------------|-------|----------------|
| 80 – 100 | **A** | 强推荐 — 多维证据较强，适合深入验证/立项 / Strong recommendation — strong multi-dimensional evidence |
| 65 – 80 | **B** | 有潜力 — 有一定证据，但需补关键缺口 / Promising — has evidence but needs key gaps filled |
| 50 – 65 | **C** | 谨慎推进 — 证据不完整或风险较明显 / Proceed cautiously — incomplete evidence or notable risk |
| 35 – 50 | **D** | 低优先级 — 当前证据不足，不建议作为核心靶点 / Low priority — insufficient evidence |
| 0 – 35 | **E** | 不推荐 — 缺乏关键支持或风险较高 / Not recommended — lacks critical support or high risk |

### Concrete Example / 计算示例: ERBB2 + Breast Cancer (drug_development)

```
disease_relevance:  13.8 / 15  × 0.15 = 0.138
expression:          13.8 / 15  × 0.15 = 0.138
dependency:          11.2 / 15  × 0.15 = 0.112
mechanism:           10.5 / 15  × 0.10 = 0.070
druggability:        12.8 / 15  × 0.15 = 0.128
safety:               7.0 / 10  × 0.15 = 0.105
clinical_competition: 5.0 / 10  × 0.10 = 0.050
scenario_fit:         2.0 /  5  × 0.05 = 0.020
                                  --------
Weighted sum:                            0.761
Total Score: 0.761 × 100 = 76.1 → Grade B
```

---

## Result Interpretation / 结果解读

### What a High Score (A) Means / 高分 (A) 的含义

- Multiple independent lines of evidence support the target / 多方面独立证据支持该靶点
- Strong disease relevance, well-characterized mechanism, established drugs / 强疾病相关性、机制清晰、已有药物
- **Action / 行动:** Proceed to in-depth validation, IND-enabling studies, or grant writing / 进入深度验证、IND申报或基金撰写
- **Example / 示例:** EGFR in NSCLC, ERBB2 in Breast Cancer, KRAS in Pancreatic Cancer

### What a Moderate Score (B) Means / 中等分 (B) 的含义

- Some evidence dimensions are strong, but others have gaps / 部分维度的证据较强，但存在缺口
- The target shows promise but needs additional validation / 靶点有潜力但需补充验证
- **Action / 行动:** Identify and fill the specific evidence gaps shown in the report / 定位并填补报告中显示的具体证据缺口
- **Example / 示例:** CLDN18 in Gastric Cancer (emerging ADC target, limited drug history)

### What a Low Score (C/D/E) Means / 低分 (C/D/E) 的含义

- Limited or conflicting evidence across multiple dimensions / 多维度证据有限或矛盾
- May be a tumor suppressor, common essential gene, or understudied target / 可能是抑癌基因、常见必需基因或研究不足
- **Action / 行动:** Re-evaluate target selection; if pursuing, plan significant foundational experiments / 重新评估靶点选择；如继续推进需规划大量基础实验
- **Example / 示例:** BRCA1 in Ovarian Cancer (tumor suppressor, PARP inhibitor context)

### How to Use the Radar Chart / 雷达图使用指南

The radar chart shows each dimension as a percentage of its maximum score. A balanced chart with broad coverage is better than one with a single spike. Gaps in the chart directly indicate where more evidence is needed.

雷达图将每个维度显示为其最高分的百分比。覆盖面广的均衡图表优于仅有一个尖峰的图表。图表中的缺口直接提示需要补充证据的方向。

---

## Web App Usage / Web 应用使用

### Input Fields / 输入字段

| Field / 字段 | Description / 说明 | Example / 示例 |
|-------|-------------|---------|
| **Target Gene** 靶点基因 | HGNC gene symbol or common alias / 基因符号或常用别名 | `EGFR`, `HER2`, `CLDN18`, `PD-L1` |
| **Disease / Cancer Type** 疾病/癌种 | Disease name (English) / 疾病名称（英文） | `NSCLC`, `Breast Cancer`, `Gastric Cancer` |
| **Scenario** 场景 | Assessment context that determines dimension weights / 决定维度权重的评估场景 | `research` 基金/SCI, `drug_development` 药研, `adc`, `small_molecule`, `general` |
| **Modality** 药物形式 | Drug modality of interest (optional) / 关注的药物形式（可选） | `small_molecule`, `antibody`, `adc`, `protac`, `rna` |

### Output / 输出

1. **Summary cards** 摘要卡片 — Gene info, total score, grade, scenario
2. **One-line recommendation** 一行建议 — Actionable guidance based on score
3. **Radar chart** 雷达图 — Visual comparison of all 8 dimensions
4. **Score table** 评分表 — Per-dimension scores with percentages
5. **Strengths / Risks / Gaps** 优势/风险/缺口 — Three-column evidence summary
6. **Downloadable reports** 可下载报告 — Markdown (.md), HTML (.html), Excel (.xlsx)

---

## CLI Usage / 命令行使用

The CLI tool (`run.py`) runs a complete target assessment from the command line and saves the report files locally.

CLI 工具（`run.py`）从命令行运行完整评估并保存报告文件。

### Basic Syntax / 基本语法

```bash
python3.8 run.py --gene <GENE> --disease <DISEASE> [OPTIONS]
```

### Arguments / 参数

| Argument / 参数 | Short | Required / 必填 | Description / 说明 | Default |
|----------|-------|----------|-------------|---------|
| `--gene` | `-g` | Yes / 是 | HGNC gene symbol or common alias / 基因符号或别名 | — |
| `--disease` | `-d` | Yes / 是 | Disease or cancer type name / 疾病或癌种名称 | — |
| `--scenario` | `-s` | No | Assessment scenario / 评估场景 | `general` |
| `--modality` | `-m` | No | Drug modality of interest / 关注的药物形式 | `any` |
| `--output-dir` | `-o` | No | Custom output root directory / 自定义输出目录 | `outputs/` |
| `--weights` | `-w` | No | Custom dimension weights (JSON file or string) / 自定义权重 | scenario defaults |
| `--quiet` | `-q` | No | Minimal output (scripting mode) / 静默模式 | off |

### Scenario Options / 场景选项

| Value / 值 | Label / 名称 | Use Case / 用途 |
|-------|-------|----------|
| `general` | 通用评估 | Default, balanced weights / 默认均衡权重 |
| `research` | 科研基金/SCI | Emphasizes literature & mechanism / 侧重文献和机制 |
| `drug_development` | 药物研发立项 | Emphasizes safety & modality fit / 侧重安全性和形式匹配 |
| `adc` | ADC/抗体靶点 | Emphasizes expression & tumor-normal differential / 侧重表达和肿瘤-正常差异 |
| `small_molecule` | 小分子靶点 | Emphasizes druggability & active compounds / 侧重可药性和活性化合物 |

### Modality Options / 药物形式选项

`any`, `small_molecule`, `antibody`, `adc`, `protac`, `rna`

### Output Files / 输出文件

Each run generates three files in the output directory:

每次运行在输出目录生成三个文件：

```
outputs/
├── reports/
│   ├── target_assessment_{GENE}_{DISEASE}_{timestamp}.md   # Markdown report
│   └── target_assessment_{GENE}_{DISEASE}_{timestamp}.html # Styled HTML report
└── tables/
    └── evidence_{GENE}_{DISEASE}_{timestamp}.xlsx          # Excel evidence table
                                                             #   Sheet 1: Evidence
                                                             #   Sheet 2: Scores
```

### Examples / 示例

```bash
# Quick evaluation with minimal typing 快速评估
python3.8 run.py -g EGFR -d NSCLC

# Evaluate an ADC target with the ADC-specific scenario 评估 ADC 靶点
python3.8 run.py --gene CLDN18 --disease "Gastric Cancer" --scenario adc

# Save results to a custom directory 保存到自定义目录
python3.8 run.py -g BRCA1 -d "Ovarian Cancer" -s research -o ./my_results

# Custom dimension weights via JSON string 自定义权重（JSON 字符串）
python3.8 run.py -g KRAS -d NSCLC -w '{"disease_relevance": 0.25, "dependency": 0.20}'

# Custom weights via JSON file 自定义权重（JSON 文件）
python3.8 run.py -g EGFR -d NSCLC -w ./my_weights.json

# Scripting mode — quiet output, just the file paths 静默模式
python3.8 run.py -g KRAS -d "Pancreatic Cancer" -q
```

### Terminal Output / 终端输出

The CLI prints a summary to stdout including:
- Gene info (symbol, full name, Ensembl ID)
- Total score and grade
- One-line recommendation
- Target archetype 靶点原型（突变驱动型 / 表达驱动型 / 依赖驱动型 / 药物已验证型 / 均衡型）
- Per-dimension score bars (text-based)

### Using in Shell Scripts / 在 Shell 脚本中使用

```bash
#!/bin/bash
# Batch evaluate multiple targets 批量评估多个靶点
for gene in EGFR ERBB2 CLDN18 KRAS BRCA1; do
    python3.8 run.py -g "$gene" -d "NSCLC" -q
    echo "---"
done
```

---

## Project Architecture / 项目架构

```
target_assessment/
├── app.py                         # Streamlit web application / Web 应用
├── run.py                         # CLI tool (batch/scripting) / 命令行工具
├── config.py                      # Weights, thresholds, API endpoints, gene aliases
├── requirements.txt               # Python dependencies / 依赖
├── project.md                     # Full project plan (Chinese) / 完整项目方案
│
├── modules/                       # Core logic / 核心逻辑
│   ├── gene_resolver.py           # Gene symbol → HGNC (offline DB → mygene.info fallback)
│   ├── data_manager.py            # Central orchestrator (offline-first, API fallback)
│   ├── offline_provider.py        # SQLite-backed evidence provider (all 6 dimensions)
│   ├── scoring_engine.py          # Multi-dimensional scoring & grading / 多维评分
│   ├── report_generator.py        # Markdown / HTML / Excel report generation
│   ├── sample_data.py             # Pre-curated evidence for canonical targets
│   ├── opentargets_client.py      # Open Targets GraphQL client (fallback)
│   ├── chembl_client.py           # ChEMBL REST client (fallback)
│   ├── clinicaltrials_client.py   # ClinicalTrials.gov REST v2 client (fallback)
│   ├── depmap_module.py           # DepMap CRISPR data (local CSV reader)
│   └── tcga_module.py             # TCGA expression & mutation (local CSV reader)
│
├── data/
│   ├── build_offline_db.py        # Full offline DB builder / 离线数据库构建脚本
│   ├── update_offline_db.py       # Incremental DB updater / 增量更新脚本
│   ├── processed/                 # Preprocessed data files / 预处理数据
│   │   ├── target_assessment.db   # Offline SQLite database (~1.2 GB) / 离线数据库
│   │   ├── depmap_crispr_summary.csv
│   │   ├── tcga_expression_summary.csv
│   │   ├── tcga_mutation_summary.csv
│   │   └── Homo_sapiens.gene_info.gz
│   ├── raw/                       # Raw downloaded data / 原始下载数据
│   └── cache/                     # API response cache (auto-generated) / API 缓存
│
├── templates/
│   ├── report_template.md         # Markdown report template / 报告模板
│   └── prompt_target_summary.txt  # AI prompt template
│
├── tests/
│   ├── test_data_manager.py
│   ├── test_gene_resolver.py
│   ├── test_scoring.py
│   └── test_report.py
│
└── outputs/
    ├── reports/                   # Generated markdown & HTML reports / 生成的报告
    └── tables/                    # Generated Excel evidence tables / 生成的 Excel 表格
```

### Data Flow / 数据流

```
User Input (gene + disease + scenario)
       │
       ▼
GeneResolver ─── Offline DB (genes table) ──► Standardized symbol + Ensembl ID
       │              └── mygene.info API (fallback)
       ▼
DataManager ─── Offline DB (all 6 tables, <1s) ──► Complete evidence dict
       │         └── Live APIs (fallback, 5–15s)
       ▼
ScoringEngine ─── 8 dimensions × scenario weights ──► Total score + Grade + Archetype
       │
       ▼
ReportGenerator ─── Markdown / HTML / Excel ──► Downloadable reports
```

---

## Maintenance Guide / 维护指南

### Updating the Offline Database / 更新离线数据库

See [Offline Database](#offline-database) above for build and update commands.

推荐定期更新离线数据库以获取最新数据。构建和更新命令详见上方离线数据库章节。

Typical workflow / 典型工作流：

```bash
# 1. Update preprocessed CSV files with new data
#    Replace data/processed/depmap_crispr_summary.csv with new version
#    Replace data/processed/tcga_expression_summary.csv with new version
#    Replace data/processed/tcga_mutation_summary.csv with new version

# 2. Update specific tables from the new CSVs
python3.8 data/update_offline_db.py --table depmap_crispr
python3.8 data/update_offline_db.py --table tcga

# 3. Update upstream data (Open Targets, ChEMBL)
python3.8 data/update_offline_db.py --table opentargets
python3.8 data/update_offline_db.py --table chembl

# 4. Full rebuild if many sources changed
python3.8 data/update_offline_db.py --full
```

### Adding a New Disease Mapping / 添加新疾病映射

Edit `EFO_DISEASE_MAP` and `DISEASE_CATEGORIES` in `config.py`:

编辑 `config.py` 中的 `EFO_DISEASE_MAP` 和 `DISEASE_CATEGORIES`：

```python
EFO_DISEASE_MAP = {
    # ... existing entries / 已有条目 ...
    "new disease name": "EFO_XXXXXXXXX",
}
```

Find EFO IDs at: https://www.ebi.ac.uk/ols/ontologies/efo

### Updating DepMap Data / 更新 DepMap 数据

1. Download the latest CRISPR gene effect file from https://depmap.org/portal/download/
2. Preprocess it to match the schema in `data/processed/depmap_crispr_summary.csv`:

```csv
gene,primary_disease,mean_chronos_score,num_cell_lines,pan_cancer_mean_score,pan_cancer_percentile,selectivity_category
```

3. Replace the CSV file
4. Run: `python3.8 data/update_offline_db.py --table depmap_crispr`

### Updating TCGA Data / 更新 TCGA 数据

1. Download expression and mutation data from cBioPortal, TCGA GDC, or similar
2. Preprocess into two files:

**Expression** (`tcga_expression_summary.csv`):
```csv
gene,cancer_type,median_tpm_tumor,median_tpm_normal,log2fc_tumor_normal,overexpression_category,tumor_normal_diff_category,tissue_specificity
```

**Mutation** (`tcga_mutation_summary.csv`):
```csv
gene,cancer_type,mutation_freq,cnv_amp_freq,cnv_del_freq,total_alteration_freq,prognostic_associated
```

3. Replace the CSV files
4. Run: `python3.8 data/update_offline_db.py --table tcga`

### Clearing API Cache / 清除 API 缓存

```bash
rm data/cache/*.json
```

The cache stores API responses keyed by gene+disease. Clear it after updating local data or if you suspect stale results.

缓存按基因+疾病键存储 API 响应。更新本地数据或怀疑缓存过期后清除。

### Adding a New Data Source / 添加新数据源

1. Create a new client module in `modules/` (follow the pattern of existing clients)
2. Add the client initialization in `DataManager.__init__`
3. Call the client in `DataManager._build_from_real_sources`
4. Map the client's output to the evidence dict dimensions
5. Add the corresponding table to `build_offline_db.py` and `offline_provider.py`
6. Add tests in `tests/`

### Tuning Scoring Weights / 调整评分权重

Edit `SCENARIO_WEIGHTS` in `config.py`. Each weight dictionary must sum to 1.0. Dimension max scores are in `DIMENSION_MAX`. Individual scoring rules are in `ScoringEngine` methods.

编辑 `config.py` 中的 `SCENARIO_WEIGHTS`。每个权重字典总和必须为 1.0。维度最高分在 `DIMENSION_MAX` 中。具体评分规则在 `ScoringEngine` 方法中。

### Running Tests / 运行测试

```bash
python3.8 -m pytest tests/ -v
```

Note: Tests use the offline DB when available, so most tests now run without internet. API-dependent tests skip automatically when the DB is present.

注意：离线 DB 可用时，测试优先使用离线数据，大部分测试无需网络。依赖 API 的测试在 DB 存在时自动跳过。

---

## FAQ

### Q: Does this tool require API keys? / 需要 API 密钥吗？

No. All data sources (Open Targets, ChEMBL, ClinicalTrials.gov, mygene.info) are free and open-access. No registration required.

不需要。所有数据源均为免费开放获取，无需注册。

### Q: Can I run this completely offline? / 可以完全离线运行吗？

Yes. Build the offline SQLite database once with `python3.8 data/build_offline_db.py` (requires ~1.5 GB download, ~10–30 minutes), and all subsequent runs use only local data with sub-second queries. No internet needed.

可以。首次运行 `python3.8 data/build_offline_db.py` 构建离线数据库（需下载约 1.5 GB，耗时约 10–30 分钟），之后所有运行都只使用本地数据，亚秒级查询，完全无需网络。

### Q: How do I update the offline database when new data is released? / 上游数据更新后如何更新离线数据库？

Use `python3.8 data/update_offline_db.py --table <name>` for single-table updates, or `--full` for a complete rebuild. The script backs up your existing database before making changes. See the [Offline Database](#offline-database) section for details.

使用 `python3.8 data/update_offline_db.py --table <表名>` 单表更新，或用 `--full` 全量重建。脚本会在修改前自动备份现有数据库。详见[离线数据库](#offline-database)章节。

### Q: Why do some targets show 0 for certain dimensions? / 为什么某些靶点在部分维度得分是 0？

If the gene is not in DepMap/TCGA local data files or not found in the APIs, that dimension defaults to `"unknown"` and scores 0. This is expected for:
- Very new or poorly annotated genes / 很新或注释不全的基因
- Non-human genes / 非人类基因
- Genes not studied in the specified disease context / 在指定疾病背景下未被研究的基因

### Q: How do I interpret "differentiation opportunity = high"? / 如何理解"差异化机会 = 高"？

It means few active clinical trials exist for this target in this disease — you have room to differentiate. But it also means the target is less clinically validated. Balance this with the overall score and your risk tolerance.

表示该靶点在该疾病中的活跃临床试验较少 — 有差异化空间。但也意味着靶点的临床验证较少。需与总体评分和风险偏好结合判断。

### Q: Why does BRCA1 score low despite being clinically important? / 为什么 BRCA1 临床很重要但得分低？

BRCA1 is a tumor suppressor — it is **lost** in cancer, not overexpressed. You can't "drug" a missing protein. The scoring model correctly identifies this as poor druggability. In practice, BRCA1 status is used for **patient stratification** (PARP inhibitor sensitivity), not as a direct drug target.

BRCA1 是抑癌基因 — 在癌症中**丢失**而非过表达。无法"靶向"一个缺失的蛋白。评分模型正确识别了其可药性差。实践中 BRCA1 状态用于**患者分层**（PARP 抑制剂敏感性），而非直接药靶。

### Q: Can I use this for non-cancer diseases? / 可以用于非癌症疾病吗？

Yes. The scoring model is disease-agnostic. However, the current data sources (TCGA, DepMap) are cancer-focused. For non-cancer diseases, you may get sparse results. Add appropriate data sources for your disease area.

可以。评分模型不限于癌症。但当前数据源（TCGA, DepMap）以癌症为主。非癌症疾病可能得到稀疏结果，需添加相应疾病领域的数据源。

### Q: How do I cite this tool? / 如何引用此工具？

The tool aggregates data from public databases. Cite the underlying data sources:

本工具聚合来自公共数据库的数据。请引用底层数据源：

- **Open Targets**: Ochoa et al. (2023), *Nucleic Acids Research*
- **ChEMBL**: Mendez et al. (2019), *Nucleic Acids Research*
- **DepMap**: Tsherniak et al. (2017), *Cell*
- **TCGA**: The Cancer Genome Atlas Research Network
- **ClinicalTrials.gov**: U.S. National Library of Medicine
- **NCBI Gene**: Brown et al. (2015), *Nucleic Acids Research*
