# 靶点价值评估器 — Target Assessment Tool

输入一个靶点基因和疾病/癌种，从多维度自动生成靶点价值评估报告，帮助判断：**这个靶点是否值得继续做、在哪个适应症中最有潜力、下一步应该补什么证据。**

---

## 目录

- [快速开始](#快速开始)
- [这个工具做什么](#这个工具做什么)
- [离线数据库](#离线数据库)
- [数据来源](#数据来源)
- [评分模型](#评分模型)
- [结果解读](#结果解读)
- [Web 应用使用](#web-应用使用)
- [命令行使用](#命令行使用)
- [项目架构](#项目架构)
- [维护指南](#维护指南)
- [常见问题](#常见问题)

---

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 构建离线数据库（仅首次需要 — 完成后即可永久离线运行）
python3.8 data/build_offline_db.py

# 命令行快速评估
python3.8 run.py --gene EGFR --disease NSCLC

# Web 交互界面
streamlit run app.py
```

### CLI vs Web App

| | CLI (`run.py`) | Web App (`app.py`) |
|---|---|---|
| **界面** | 终端 | 浏览器 (Streamlit) |
| **用途** | 批量评估、脚本、快速查询 | 交互探索、演示 |
| **输出** | 终端打印 + 保存文件 | 交互图表 + 下载按钮 |
| **适合** | 高级用户、自动化 | 新用户、演示 |

---

### 环境要求

- Python 3.8+
- 离线模式：**无需联网**（推荐）
- 联网备用：仅在无 SQLite 数据库时需要
- 依赖包：`streamlit`, `pandas`, `numpy`, `httpx`, `plotly`, `openpyxl`, `markdown`, `weasyprint`

---

## 这个工具做什么

这是一个**多维靶点评估引擎**，用于药物发现和生物医学研究。输入基因符号和疾病/癌种后，它会：

1. **解析**基因符号为标准化 HGNC 标识符（离线数据库 → mygene.info API 兜底）
2. **收集**来自离线 SQLite 数据库（主路径）或在线 API（备用）的多方证据
3. **评分**：基于场景权重对 8 个维度进行加权评分
4. **生成**结构化报告（Markdown / HTML / Excel）

该工具定位为**决策支持系统**，帮助研究人员和药物开发者在投入深度人工调研之前，快速筛选靶点。

---

## 离线数据库

离线 SQLite 数据库（`data/processed/target_assessment.db`）将所有证据数据打包到单个约 1.2 GB 文件中，实现**亚秒级查询，完全无需网络**。

### 数据库内容

| 表 | 行数 | 来源 | 说明 |
|-------------|-------------|---------------|---------------------|
| `genes` | ~194,000 | NCBI Gene | 基因符号、Ensembl ID、别名 |
| `opentargets` | ~500,000 | Open Targets Platform | 靶点-疾病关联评分 |
| `chembl_drugs` | ~2,000 | ChEMBL | 每个靶点的已批准/临床/活性药物数 |
| `depmap_crispr` | ~18,000 | DepMap | 按癌种分类的 CRISPR 依赖性评分 |
| `tcga_expression` | ~20,000 | TCGA | 按癌种分类的肿瘤表达数据 |
| `tcga_mutation` | ~20,000 | TCGA | 按癌种分类的突变和拷贝数变异频率 |

### 构建数据库

**首次构建**（需要网络）:

```bash
# 完整构建 — 下载所有上游数据（约 1.5 GB 下载量）
python3.8 data/build_offline_db.py

# 仅使用本地 CSV 文件构建（不下载外部数据）
python3.8 data/build_offline_db.py --only-local

# 仅构建基因表
python3.8 data/build_offline_db.py --only-genes
```

### 更新数据库

当上游数据源发布新版本时，你可以单独更新各个表，无需重建整个数据库：

```bash
# 更新特定表
python3.8 data/update_offline_db.py --table depmap_crispr      # DepMap CRISPR 数据
python3.8 data/update_offline_db.py --table tcga                # 两个 TCGA 表
python3.8 data/update_offline_db.py --table genes               # NCBI 基因信息
python3.8 data/update_offline_db.py --table opentargets         # Open Targets 关联数据
python3.8 data/update_offline_db.py --table chembl              # ChEMBL 药物计数

# 预演模式 — 检查哪些内容会被更新，不实际修改
python3.8 data/update_offline_db.py --table depmap_crispr --dry-run

# 全量重建并备份
python3.8 data/update_offline_db.py --full
```

更新脚本会：
- 修改前**备份**现有数据库
- 导入后**验证**更新后的表（行数、schema 检查）
- 验证失败时**支持回滚**
- 对现有数据库**原地更新**（单表无需全量重建）

### 典型更新周期

| 数据源 | 更新频率 | 何时更新 |
|----------------------|----------------------------|--------------------------|
| NCBI Gene | 每季度 | 新基因注释发布时 |
| DepMap | 每季度 | 新 CRISPR 筛选版本发布时（如 24Q4） |
| TCGA | 很少 | TCGA 数据相对稳定；如有重新处理可更新 |
| Open Targets | 每月 | 平台每月发布；每季度有重大变化 |
| ChEMBL | 每季度 | ChEMBL 新版本发布时（如 37 → 38） |

---

## 数据来源

### 离线 SQLite 数据库（主路径）

数据库存在时，所有证据直接从 SQLite 查询，**亚秒级延迟，零网络调用**。详见上方离线数据库章节。

### 在线 API（备用路径）

如果离线数据库不可用，工具回退到在线 API 查询：

| 来源 | 方法 | 提供内容 | 频率限制 |
|--------|--------|---------------------------|------------|
| **Open Targets Platform** | GraphQL API | 靶点-疾病关联评分 (0–1)，按类型分类的证据明细 | 无严格限制 |
| **ChEMBL** | REST API | 按阶段分类的药物计数，形式匹配评估 | ~1 请求/秒 |
| **ClinicalTrials.gov** | REST API v2 | 活跃临床试验计数，差异化机会评估 | ~50 请求/分钟 |
| **mygene.info** | REST API | 基因符号解析，Ensembl ID 查找 | 无严格限制 |

### 本地数据文件

| 来源 | 文件 | 提供内容 |
|--------|------|---------------------------|
| **DepMap** | `data/processed/depmap_crispr_summary.csv` | CRISPR 基因效应评分 (Chronos)、选择性、百分位排名 |
| **TCGA** | `data/processed/tcga_expression_summary.csv` | 中位数 TPM（肿瘤/正常）、log2FC、过表达类别 |
| **TCGA** | `data/processed/tcga_mutation_summary.csv` | 突变频率、CNV 扩增/缺失频率、预后关联 |

### 示例数据（兜底）

预置的经典靶点证据（EGFR, ERBB2, CLDN18, MUC1, BRCA1, KRAS）在 `modules/sample_data.py` 中。用于补充知名靶点在实际数据中稀疏的字段。

### 证据收集优先级

```
离线 SQLite 数据库 (主路径, <1s)  →  示例数据 (补充)  →  通用模板 (兜底)
     ↓ (数据库不可用时)
在线 API (备用路径, 5–15s)
```

---

## 评分模型

### 概述

总分是**8个维度分数的加权求和**，归一化到 0–100。

### 公式

```
Total Score = Σ ( dimension_raw_score / dimension_max × dimension_weight ) × 100
```

其中：
- `dimension_raw_score` — 每个维度的原始得分（0 到 dimension_max）
- `dimension_max` — 该维度的最高可能原始分
- `dimension_weight` — 场景相关权重（所有权重之和 = 1.0）

### 各维度最高分与场景权重

| 维度 | 最高分 | general | research | drug_dev | adc | small_mol |
|-----------|-----|---------|----------|----------|-----|-----------|
| 疾病相关性 | 15 | 0.15 | **0.20** | 0.15 | 0.10 | 0.10 |
| 表达谱 | 15 | 0.15 | 0.15 | 0.15 | **0.25** | 0.10 |
| 依赖性 | 15 | 0.15 | 0.10 | 0.15 | 0.10 | 0.15 |
| 机制通路 | 15 | 0.15 | **0.20** | 0.10 | 0.05 | 0.15 |
| 可药性 | 15 | 0.15 | 0.10 | 0.15 | 0.20 | **0.25** |
| 安全性 | 10 | 0.10 | 0.10 | **0.15** | **0.20** | 0.15 |
| 临床格局 | 10 | 0.10 | 0.10 | 0.10 | 0.05 | 0.05 |
| 场景匹配 | 5 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 |
| **合计** | | **1.00** | **1.00** | **1.00** | **1.00** | **1.00** |

### 维度评分规则

#### 1. 疾病相关性 (最高分: 15)

评估靶点通过表达、突变、文献和数据库注释与疾病的关联强度。

| 证据 | 条件 | 分值 |
|----------|-----------|--------|
| 靶点过表达 | `"high"` 高 | +6.0 |
| | `"moderate"` 中 | +3.75 |
| | `"low"` 低 | +0.75 |
| 预后关联 | True / 是 | +3.0 |
| 突变/CNV 频率 | > 10% | +3.0 |
| | > 3% | +1.5 |
| Open Targets 关联 | score > 0.01 | +1.5 |
| 文献证据 | `"high"` 高 | +1.5 |
| | `"moderate"` 中 | +0.75 |

#### 2. 表达谱 (最高分: 15)

评估肿瘤表达水平和肿瘤-正常组织特异性 — 对 ADC/抗体靶点至关重要。

| 证据 | 条件 | 分值 |
|----------|-----------|--------|
| 肿瘤表达水平 | `"high"` 高 | +6.0 |
| | `"moderate"` 中 | +3.75 |
| | `"low"` 低 | +0.75 |
| 肿瘤-正常差异 | `"significant"` (log2FC > 2) | +4.5 |
| | `"moderate"` (log2FC > 1) | +2.25 |
| 蛋白水平证据 | True / 是 | +2.25 |
| 组织特异性 | `"high"` 高 | +2.25 |
| | `"moderate"` 中 | +1.2 |

#### 3. 功能性依赖 (最高分: 15)

基于 DepMap CRISPR 敲除筛选。依赖性越强越得分。**常见必需基因会被降权**（上限为最高分的 30%）。

| 证据 | 条件 | 分值 |
|----------|-----------|--------|
| 癌症依赖性 | `"strong"` (Chronos < −0.5) | +7.5 |
| | `"moderate"` (Chronos < −0.3) | +4.5 |
| | `"weak"` (Chronos ≥ −0.3) | +1.5 |
| 泛癌选择性 | `"selective"` 选择性 | +3.75 |
| | `"moderate_selective"` 中等选择性 | +1.5 |
| **常见必需基因上限** | 如果命中 | **最高 4.5 分** |
| 突变条件依赖 | True / 是 | +3.75 |

#### 4. 机制通路证据 (最高分: 15)

评估生物学机制：靶点与疾病关联的机制有多清晰？

| 证据 | 条件 | 分值 |
|----------|-----------|--------|
| 相关通路数 | ≥ 3 条通路 | +5.25 |
| | 1–2 条通路 | +3.0 |
| 机制强度 | `"well_established"` 充分验证 | +5.25 |
| | `"partially_established"` 部分验证 | +3.0 |
| 连接疾病特征 | True / 是 | +4.5 |

#### 5. 可药性 (最高分: 15)

评估靶点已有的药物开发格局。

| 证据 | 条件 | 分值 |
|----------|-----------|--------|
| 已批准药物 | ≥ 1 | +6.0 |
| 临床候选药物 | ≥ 1 | +3.75 |
| 活性化合物 | ≥ 1 | +2.25 |
| 形式匹配 | `"strong"` 强 | +3.0 |
| | `"moderate"` 中 | +1.5 |

#### 6. 安全性风险 (最高分: 10)

初始满分，从安全性风险中扣分。**分数越高 = 越安全。**

| 风险因素 | 条件 | 扣分 |
|-------------|-----------|---------|
| 正常组织表达 | `"high"` 高 | −6.0 |
| | `"moderate"` 中 | −3.0 |
| | `"low"` 低 | −1.0 |
| 常见必需基因 | True / 是 | −5.0 |
| 关键器官表达 | ≥ 2 个器官 | −3.0 |
| | 1 个器官 | −1.5 |

#### 7. 临床格局 (最高分: 10)

分数越高 = 靶点越被临床验证（不意味着竞争越小）。

| 证据 | 条件 | 分值 |
|----------|-----------|--------|
| 已批准药物（竞争） | ≥ 2 | +5.0 |
| | 1 | +3.5 |
| 活跃临床试验 | ≥ 10 | +3.0 |
| | 3–9 | +1.5 |
| 差异化机会 | `"high"` 高 | +2.0 |
| | `"moderate"` 中 | +1.0 |

#### 8. 场景匹配 (最高分: 5)

根据靶点特征与所选评估场景的匹配程度给予加分。

| 场景 | 评分标准 |
|----------|-----------------|
| **research** 基金/SCI | 文献水平 (+40%)、机制强度 (+40%)、肿瘤表达 (+20%) |
| **drug_development** 药物研发 | 形式匹配 (+35%)、依赖性 (+35%)、安全窗口 (+30%) |
| **adc** ADC/抗体 | 蛋白证据 (+40%)、肿瘤-正常差异 (+35%)、安全窗口 (+25%) |
| **small_molecule** 小分子 | 形式匹配 (+40%)、活性化合物 (+30%)、机制 (+30%) |
| **general** 通用 | 均等 50% 基线 |

### 等级划分

| 分数 | 等级 | 解释 |
|-------------|-------|----------------|
| 80 – 100 | **A** | 强推荐 — 多维证据较强，适合深入验证/立项 |
| 65 – 80 | **B** | 有潜力 — 有一定证据，但需补关键缺口 |
| 50 – 65 | **C** | 谨慎推进 — 证据不完整或风险较明显 |
| 35 – 50 | **D** | 低优先级 — 当前证据不足，不建议作为核心靶点 |
| 0 – 35 | **E** | 不推荐 — 缺乏关键支持或风险较高 |

### 计算示例: ERBB2 + Breast Cancer (drug_development)

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
加权和:                                 0.761
总分: 0.761 × 100 = 76.1 → Grade B
```

---

## 结果解读

### 高分 (A) 的含义

- 多方面独立证据支持该靶点
- 强疾病相关性、机制清晰、已有药物
- **行动:** 进入深度验证、IND申报或基金撰写
- **示例:** EGFR 在 NSCLC, ERBB2 在乳腺癌, KRAS 在胰腺癌

### 中等分 (B) 的含义

- 部分维度的证据较强，但存在缺口
- 靶点有潜力但需补充验证
- **行动:** 定位并填补报告中显示的具体证据缺口
- **示例:** CLDN18 在胃癌（新兴 ADC 靶点，药物历史有限）

### 低分 (C/D/E) 的含义

- 多维度证据有限或矛盾
- 可能是抑癌基因、常见必需基因或研究不足
- **行动:** 重新评估靶点选择；如继续推进需规划大量基础实验
- **示例:** BRCA1 在卵巢癌（抑癌基因，PARP 抑制剂背景）

### 雷达图使用指南

雷达图将每个维度显示为其最高分的百分比。覆盖面广的均衡图表优于仅有一个尖峰的图表。图表中的缺口直接提示需要补充证据的方向。

---

## Web 应用使用

### 输入字段

| 字段 | 说明 | 示例 |
|-------|-------------|---------|
| **靶点基因** | 基因符号或常用别名 | `EGFR`, `HER2`, `CLDN18`, `PD-L1` |
| **疾病/癌种** | 疾病名称（英文） | `NSCLC`, `Breast Cancer`, `Gastric Cancer` |
| **场景** | 决定维度权重的评估场景 | `research` 基金/SCI, `drug_development` 药研, `adc`, `small_molecule`, `general` |
| **药物形式** | 关注的药物形式（可选） | `small_molecule`, `antibody`, `adc`, `protac`, `rna` |

### 输出

1. **摘要卡片** — 基因信息、总分、等级、场景
2. **一行建议** — 基于分数的可执行指导
3. **雷达图** — 8 个维度的可视化对比
4. **评分表** — 每个维度的得分和百分比
5. **优势/风险/缺口** — 三列证据摘要
6. **可下载报告** — Markdown (.md)、HTML (.html)、Excel (.xlsx)

---

## 命令行使用

CLI 工具（`run.py`）从命令行运行完整评估并保存报告文件。

### 基本语法

```bash
python3.8 run.py --gene <GENE> --disease <DISEASE> [OPTIONS]
```

### 参数

| 参数 | 简写 | 必填 | 说明 | 默认值 |
|----------|-------|----------|-------------|---------|
| `--gene` | `-g` | 是 | 基因符号或别名 | — |
| `--disease` | `-d` | 是 | 疾病或癌种名称 | — |
| `--scenario` | `-s` | 否 | 评估场景 | `general` |
| `--modality` | `-m` | 否 | 关注的药物形式 | `any` |
| `--output-dir` | `-o` | 否 | 自定义输出目录 | `outputs/` |
| `--weights` | `-w` | 否 | 自定义权重（JSON 字符串或文件路径） | 场景默认值 |
| `--quiet` | `-q` | 否 | 静默模式 | off |

### 场景选项

| 值 | 名称 | 用途 |
|-------|-------|----------|
| `general` | 通用评估 | 默认均衡权重 |
| `research` | 科研基金/SCI | 侧重文献和机制 |
| `drug_development` | 药物研发立项 | 侧重安全性和形式匹配 |
| `adc` | ADC/抗体靶点 | 侧重表达和肿瘤-正常差异 |
| `small_molecule` | 小分子靶点 | 侧重可药性和活性化合物 |

### 药物形式选项

`any`, `small_molecule`, `antibody`, `adc`, `protac`, `rna`

### 输出文件

每次运行在输出目录生成三个文件：

```
outputs/
├── reports/
│   ├── target_assessment_{GENE}_{DISEASE}_{timestamp}.md   # Markdown 报告
│   └── target_assessment_{GENE}_{DISEASE}_{timestamp}.html # 带样式的 HTML 报告
└── tables/
    └── evidence_{GENE}_{DISEASE}_{timestamp}.xlsx          # Excel 证据表格
                                                             #   工作表 1: Evidence
                                                             #   工作表 2: Scores
```

### 示例

```bash
# 快速评估
python3.8 run.py -g EGFR -d NSCLC

# 评估 ADC 靶点
python3.8 run.py --gene CLDN18 --disease "Gastric Cancer" --scenario adc

# 保存到自定义目录
python3.8 run.py -g BRCA1 -d "Ovarian Cancer" -s research -o ./my_results

# 自定义权重（JSON 字符串）
python3.8 run.py -g KRAS -d NSCLC -w '{"disease_relevance": 0.25, "dependency": 0.20}'

# 自定义权重（JSON 文件）
python3.8 run.py -g EGFR -d NSCLC -w ./my_weights.json

# 静默模式
python3.8 run.py -g KRAS -d "Pancreatic Cancer" -q
```

### 终端输出

CLI 会在终端打印摘要，包括：
- 基因信息（符号、全称、Ensembl ID）
- 总分和等级
- 一行建议
- 靶点原型（突变驱动型 / 表达驱动型 / 依赖驱动型 / 药物已验证型 / 均衡型）
- 每个维度的得分条形图（文本形式）

### 在 Shell 脚本中使用

```bash
#!/bin/bash
# 批量评估多个靶点
for gene in EGFR ERBB2 CLDN18 KRAS BRCA1; do
    python3.8 run.py -g "$gene" -d "NSCLC" -q
    echo "---"
done
```

---

## 项目架构

```
target_assessment/
├── app.py                         # Streamlit Web 应用
├── run.py                         # CLI 命令行工具
├── config.py                      # 权重、阈值、API 端点、基因别名
├── requirements.txt               # Python 依赖
├── project.md                     # 完整项目方案
│
├── modules/                       # 核心逻辑
│   ├── gene_resolver.py           # 基因符号 → HGNC（离线数据库 → mygene.info 兜底）
│   ├── data_manager.py            # 中央协调器（离线优先，API 备用）
│   ├── offline_provider.py        # 基于 SQLite 的证据提供（覆盖全部 6 个维度）
│   ├── scoring_engine.py          # 多维评分与等级划分
│   ├── report_generator.py        # Markdown / HTML / Excel 报告生成
│   ├── sample_data.py             # 经典靶点的预置证据
│   ├── opentargets_client.py      # Open Targets GraphQL 客户端（备用）
│   ├── chembl_client.py           # ChEMBL REST 客户端（备用）
│   ├── clinicaltrials_client.py   # ClinicalTrials.gov REST v2 客户端（备用）
│   ├── depmap_module.py           # DepMap CRISPR 数据（本地 CSV 读取器）
│   └── tcga_module.py             # TCGA 表达和突变数据（本地 CSV 读取器）
│
├── data/
│   ├── build_offline_db.py        # 离线数据库构建脚本
│   ├── update_offline_db.py       # 增量更新脚本
│   ├── processed/                 # 预处理数据
│   │   ├── target_assessment.db   # 离线 SQLite 数据库（~1.2 GB）
│   │   ├── depmap_crispr_summary.csv
│   │   ├── tcga_expression_summary.csv
│   │   ├── tcga_mutation_summary.csv
│   │   └── Homo_sapiens.gene_info.gz
│   ├── raw/                       # 原始下载数据
│   └── cache/                     # API 响应缓存（自动生成）
│
├── templates/
│   ├── report_template.md         # 报告模板
│   └── prompt_target_summary.txt  # AI 提示模板
│
├── tests/
│   ├── test_data_manager.py
│   ├── test_gene_resolver.py
│   ├── test_scoring.py
│   └── test_report.py
│
└── outputs/
    ├── reports/                   # 生成的 Markdown 和 HTML 报告
    └── tables/                    # 生成的 Excel 证据表格
```

### 数据流

```
用户输入 (基因 + 疾病 + 场景)
       │
       ▼
GeneResolver ─── 离线数据库 (genes 表) ──► 标准化符号 + Ensembl ID
       │              └── mygene.info API (备用)
       ▼
DataManager ─── 离线数据库 (全部 6 个表, <1s) ──► 完整证据字典
       │         └── 在线 API (备用, 5–15s)
       ▼
ScoringEngine ─── 8 个维度 × 场景权重 ──► 总分 + 等级 + 靶点原型
       │
       ▼
ReportGenerator ─── Markdown / HTML / Excel ──► 可下载报告
```

---

## 维护指南

### 更新离线数据库

推荐定期更新离线数据库以获取最新数据。构建和更新命令详见上方离线数据库章节。

典型工作流：

```bash
# 1. 使用新数据更新预处理的 CSV 文件
#    将 data/processed/depmap_crispr_summary.csv 替换为新版本
#    将 data/processed/tcga_expression_summary.csv 替换为新版本
#    将 data/processed/tcga_mutation_summary.csv 替换为新版本

# 2. 从新 CSV 更新特定表
python3.8 data/update_offline_db.py --table depmap_crispr
python3.8 data/update_offline_db.py --table tcga

# 3. 更新上游数据（Open Targets, ChEMBL）
python3.8 data/update_offline_db.py --table opentargets
python3.8 data/update_offline_db.py --table chembl

# 4. 如果多个数据源有变化，进行全量重建
python3.8 data/update_offline_db.py --full
```

### 添加新疾病映射

编辑 `config.py` 中的 `EFO_DISEASE_MAP` 和 `DISEASE_CATEGORIES`：

```python
EFO_DISEASE_MAP = {
    # ... 已有条目 ...
    "new disease name": "EFO_XXXXXXXXX",
}
```

EFO ID 查询地址: https://www.ebi.ac.uk/ols/ontologies/efo

### 更新 DepMap 数据

1. 从 https://depmap.org/portal/download/ 下载最新的 CRISPR 基因效应文件
2. 预处理使其匹配 `data/processed/depmap_crispr_summary.csv` 的 schema：

```csv
gene,primary_disease,mean_chronos_score,num_cell_lines,pan_cancer_mean_score,pan_cancer_percentile,selectivity_category
```

3. 替换 CSV 文件
4. 运行: `python3.8 data/update_offline_db.py --table depmap_crispr`

### 更新 TCGA 数据

1. 从 cBioPortal、TCGA GDC 或类似来源下载表达和突变数据
2. 预处理为两个文件：

**表达数据** (`tcga_expression_summary.csv`):
```csv
gene,cancer_type,median_tpm_tumor,median_tpm_normal,log2fc_tumor_normal,overexpression_category,tumor_normal_diff_category,tissue_specificity
```

**突变数据** (`tcga_mutation_summary.csv`):
```csv
gene,cancer_type,mutation_freq,cnv_amp_freq,cnv_del_freq,total_alteration_freq,prognostic_associated
```

3. 替换 CSV 文件
4. 运行: `python3.8 data/update_offline_db.py --table tcga`

### 清除 API 缓存

```bash
rm data/cache/*.json
```

缓存按基因+疾病键存储 API 响应。更新本地数据或怀疑缓存过期后清除。

### 添加新数据源

1. 在 `modules/` 中创建新的客户端模块（参考现有客户端的模式）
2. 在 `DataManager.__init__` 中添加客户端初始化
3. 在 `DataManager._build_from_real_sources` 中调用客户端
4. 将客户端输出映射到证据字典的各个维度
5. 在 `build_offline_db.py` 和 `offline_provider.py` 中添加相应的表
6. 在 `tests/` 中添加测试

### 调整评分权重

编辑 `config.py` 中的 `SCENARIO_WEIGHTS`。每个权重字典总和必须为 1.0。维度最高分在 `DIMENSION_MAX` 中。具体评分规则在 `ScoringEngine` 方法中。

### 运行测试

```bash
python3.8 -m pytest tests/ -v
```

注意：离线 DB 可用时，测试优先使用离线数据，大部分测试无需网络。依赖 API 的测试在 DB 存在时自动跳过。

---

## 常见问题

### Q: 需要 API 密钥吗？

不需要。所有数据源均为免费开放获取，无需注册。

### Q: 可以完全离线运行吗？

可以。首次运行 `python3.8 data/build_offline_db.py` 构建离线数据库（需下载约 1.5 GB，耗时约 10–30 分钟），之后所有运行都只使用本地数据，亚秒级查询，完全无需网络。

### Q: 上游数据更新后如何更新离线数据库？

使用 `python3.8 data/update_offline_db.py --table <表名>` 单表更新，或用 `--full` 全量重建。脚本会在修改前自动备份现有数据库。详见[离线数据库](#离线数据库)章节。

### Q: 为什么某些靶点在部分维度得分是 0？

如果基因不在 DepMap/TCGA 本地数据文件中，或在 API 中找不到，该维度默认为 `"unknown"` 并得 0 分。这在以下情况下是预期行为：
- 很新或注释不全的基因
- 非人类基因
- 在指定疾病背景下未被研究的基因

### Q: 如何理解"差异化机会 = 高"？

表示该靶点在该疾病中的活跃临床试验较少 — 有差异化空间。但也意味着靶点的临床验证较少。需与总体评分和风险偏好结合判断。

### Q: 为什么 BRCA1 临床很重要但得分低？

BRCA1 是抑癌基因 — 在癌症中**丢失**而非过表达。无法"靶向"一个缺失的蛋白。评分模型正确识别了其可药性差。实践中 BRCA1 状态用于**患者分层**（PARP 抑制剂敏感性），而非直接药靶。

### Q: 可以用于非癌症疾病吗？

可以。评分模型不限于癌症。但当前数据源（TCGA, DepMap）以癌症为主。非癌症疾病可能得到稀疏结果，需添加相应疾病领域的数据源。

### Q: 如何引用此工具？

本工具聚合来自公共数据库的数据。请引用底层数据源：

- **Open Targets**: Ochoa et al. (2023), *Nucleic Acids Research*
- **ChEMBL**: Mendez et al. (2019), *Nucleic Acids Research*
- **DepMap**: Tsherniak et al. (2017), *Cell*
- **TCGA**: The Cancer Genome Atlas Research Network
- **ClinicalTrials.gov**: U.S. National Library of Medicine
- **NCBI Gene**: Brown et al. (2015), *Nucleic Acids Research*
