
# 靶点价值评估器（Target Assessment Tool）项目规划

> 项目定位：输入一个靶点（gene/protein）和疾病/癌种背景，自动从多维度生成靶点价值评估报告，帮助科研人员、医生、PI 或企业研发团队判断：**这个靶点是否值得继续做、适合在哪个适应症中做、下一步应该补什么证据。**

---

## 0. 项目一句话定义

**靶点价值评估器 = Target gene 输入框 + 多数据库证据抓取 + 评分模型 + AI 解释 + PDF/Excel 报告。**

它不是简单查询工具，也不是单纯生信分析，而是一个面向科研和药物研发的**决策辅助小产品**。

用户最终买的不是“表达图”或“依赖性图”，而是：

- 这个靶点值不值得继续做？
- 它在什么疾病/癌种中最有潜力？
- 是否有机制、生信、药物、临床或安全性证据支撑？
- 如果我要申请基金、写 SCI、做靶点立项或设计实验，下一步该怎么做？

---

## 1. 为什么这个产品值得做？

### 1.1 客户痛点明确

科研和药物研发中经常遇到类似问题：

- 我发现一个基因差异表达，它能不能作为课题核心？
- 这个基因能不能作为肿瘤治疗靶点？
- 这个靶点是否有 DepMap 依赖性证据？
- 它是否在正常组织中高表达，是否有安全性风险？
- 有没有已有药物、抑制剂、抗体、ADC 或临床试验？
- 它适合做小分子、抗体、ADC、PROTAC，还是不适合做药物？
- 它适合哪个癌种或疾病场景？
- 如果要写基金/SCI/企业立项报告，需要补哪些证据？

这些问题非常靠近“决策”，比“帮我做一个差异分析”更有商业价值。

### 1.2 适合做小闭环

该产品具备小闭环特征：

- 输入简单：靶点名 + 疾病/癌种 + 关注方向。
- 输出明确：PDF 靶点评估报告 + Excel 证据表。
- 能免费试用：给出简版评分和 3 条建议。
- 能低价付费：完整自动报告 49–199 元。
- 能转高价服务：人工增强版、基金前期基础包、企业靶点评估报告。
- 能沉淀资产：靶点数据库、报告模板、评分体系、案例库。

---

## 2. 目标用户与使用场景

## 2.1 用户类型 1：医生 / 高校科研人员 / 青年 PI

### 典型问题

- 我想围绕某个基因申请国自然/省自然，值得做吗？
- 这个靶点有没有疾病相关性和机制合理性？
- 是否能作为基金前期基础或 SCI 课题核心？

### 交付重点

- 疾病相关性
- 表达差异
- 机制通路
- 公共数据支持
- 前期基础补强建议
- 基金/SCI 故事线建议

### 适合产品

- 靶点科研价值简评报告
- 基金前期基础增强报告
- SCI 机制故事线报告

---

## 2.2 用户类型 2：生物医药企业 / Biotech / 药物研发团队

### 典型问题

- 某个靶点是否值得立项？
- 哪个适应症最合适？
- 是否已有竞品和临床试验？
- 是否有 druggability 和 safety 风险？
- 有没有 biomarker 人群？

### 交付重点

- 靶点立项价值
- 适应症优先级
- 竞争格局
- 可药性
- 临床试验状态
- 安全性风险
- 转化策略

### 适合产品

- Target Assessment Report
- Indication Prioritization Report
- Competitive Landscape Report
- Biomarker Strategy Report

---

## 2.3 用户类型 3：研究生 / 博士后 / 生信服务客户

### 典型问题

- 我有一堆候选基因，不知道哪个最值得验证。
- 这个基因能不能写成文章？
- 我应该补哪些分析？

### 交付重点

- 候选基因排序
- 数据证据强弱
- 机制解释
- 实验验证建议

### 适合产品

- 候选基因优先级报告
- 靶点初筛报告
- 机制卡片

---

## 3. 产品形态设计

## 3.1 产品名称候选

推荐名称：

1. **TargetLight：靶点价值评估器**
2. **TargetCompass：靶点决策罗盘**
3. **靶点体检器**
4. **靶点可行性评估器**
5. **靶点立项助手**
6. **TargetInsight Report**

如果和“本子有光”品牌结合，可以叫：

> **本子有光 · 靶点体检器**

---

## 3.2 产品输入

### 必填输入

| 字段 | 示例 | 说明 |
|---|---|---|
| Target gene | EGFR / BRCA1 / MUC1 / CLDN18 | 基因符号，需标准化为 HGNC symbol |
| 疾病/癌种 | 胃癌 / 肺癌 / 泛癌 / 乳腺癌 | 用于限定解释背景 |
| 研究目的 | 基金 / SCI / 靶点立项 / 药物研发 | 决定报告语气和评分重点 |
| 关注方向 | 疗效 / 安全性 / biomarker / 适应症 / 竞品 | 决定输出模块权重 |

### 可选输入

| 字段 | 示例 | 用途 |
|---|---|---|
| 药物形式 | 小分子 / 抗体 / ADC / PROTAC / RNA 药物 | 用于评估 modality fit |
| 用户已有证据 | 已有 IHC / RNA-seq / CRISPR / 动物实验 | 用于个性化建议 |
| 数据上传 | DEG.csv / candidate_genes.csv | 用于结合用户数据 |
| 目标报告类型 | 简版 / 标准版 / 企业版 | 控制输出长度 |

---

## 3.3 产品输出

### 免费版输出

- 靶点总体评分
- 3 条主要证据
- 3 条主要风险
- 是否值得继续深挖
- 建议补充哪些证据

### 标准自动报告输出

- PDF 报告，约 5–8 页
- Excel 证据表
- 图表：表达、依赖性、正常组织风险、药物/临床信息
- AI 解释总结
- 下一步建议

### 人工增强版输出

- 10–20 页深度 PDF
- 靶点机制故事线
- 适应症优先级
- 竞品/临床试验梳理
- 实验验证路线
- 基金/SCI/企业立项建议

---

## 4. 靶点评估维度设计

建议第一版评估 8 个维度。

---

## 4.1 Disease relevance：疾病相关性

### 核心问题

这个靶点是否和目标疾病/癌种有关？

### 证据来源

- TCGA 表达差异
- TCGA mutation / CNV
- Open Targets disease association
- PubMed 文献数量和主题
- GWAS / genetic evidence（后续版本）

### 输出内容

- 是否在目标癌种中高表达或异常改变
- 是否与分期、预后、治疗反应相关
- 是否已有疾病关联数据库证据
- 疾病相关性评分

### 评分逻辑示例

| 证据 | 加分 |
|---|---:|
| 目标癌种显著高表达 | +2 |
| 与预后或分期相关 | +1 |
| 有 mutation/CNV 频率支持 | +1 |
| Open Targets 有疾病关联 | +1 |
| 文献支持较多 | +1 |

---

## 4.2 Genetic alteration：基因组改变证据

### 核心问题

这个靶点是否存在肿瘤相关突变、扩增、融合或缺失？

### 证据来源

- TCGA mutation
- TCGA CNV
- cBioPortal API（后续接入）
- COSMIC（如有授权/手动查询）

### 输出内容

- mutation frequency
- amplification / deletion frequency
- 癌种分布
- 是否为 driver-like alteration

### 注意

不是所有高频突变都适合做靶点；也不是没有突变就不能做靶点。对于 ADC、抗体、细胞表面靶点，表达和蛋白定位可能比突变更重要。

---

## 4.3 Expression profile：表达谱证据

### 核心问题

这个靶点是否在目标疾病组织中表达，同时在关键正常组织中不过高？

### 证据来源

- TCGA tumor expression
- GTEx normal tissue expression
- Human Protein Atlas RNA/protein expression
- Single-cell expression（后续版本）

Human Protein Atlas 提供正常组织、肿瘤组织、细胞系等多类蛋白和 RNA 表达数据，可用于正常组织风险和肿瘤表达评估。

### 输出内容

- tumor expression level
- normal tissue expression risk
- tumor-normal differential expression
- tissue specificity
- protein-level support

### 风险判断

| 情况 | 解释 |
|---|---|
| 肿瘤高表达，正常组织低表达 | 好靶点特征 |
| 肿瘤高表达，但心脏/脑/肝等正常组织也高表达 | 安全性风险 |
| 只有 RNA 高表达，无蛋白证据 | 需补蛋白层面验证 |
| 目标为 ADC 靶点但膜定位不明确 | 需谨慎 |

---

## 4.4 Dependency evidence：功能依赖性证据

### 核心问题

敲除/抑制该靶点是否会影响癌细胞生存？

### 证据来源

- DepMap CRISPR gene effect
- DepMap RNAi dependency
- 癌种特异 dependency
- dependency 与 expression/mutation 相关性

DepMap 提供开放的癌症依赖性数据，包括 CRISPR 和 RNAi 等筛选数据，可用于识别癌症脆弱性和潜在治疗靶点。

### 输出内容

- 目标癌种中 dependency score 分布
- pan-cancer dependency rank
- lineage-specific dependency
- 是否为 common essential gene
- mutation-conditioned dependency（后续高级版）

### 关键解释

如果一个靶点在所有细胞中都强依赖，可能代表广泛 essential gene，具有较高毒性风险；如果只在特定癌种或特定分子背景依赖，转化价值更高。

---

## 4.5 Pathway / mechanism evidence：机制通路证据

### 核心问题

这个靶点是否处于重要疾病机制通路中？

### 证据来源

- Reactome
- KEGG
- MSigDB
- OmniPath
- STRING/PPI
- 用户上传 DEG/enrichment 结果

### 输出内容

- 所属通路
- 上游/下游关系
- 是否连接疾病关键过程
- 是否与用户研究假说一致

### 机制解释模板

> 该靶点可能通过调控 [通路/细胞过程] 影响 [疾病表型]。当前证据支持其与 [机制模块] 相关，但仍需要通过 [实验/数据] 证明因果关系。

---

## 4.6 Druggability：可药性

### 核心问题

这个靶点是否已有药物、活性化合物、抗体或可开发策略？

### 证据来源

- ChEMBL
- DrugBank
- TTD
- Open Targets
- DGIdb
- FDA approved drug lists（手动/半自动）

ChEMBL Web Services 提供化合物、靶点、药物机制和生物活性等接口，适合用于构建 druggability 和已知药物证据模块。

### 输出内容

- 是否有已知小分子/抗体
- 是否有临床或上市药物
- 是否有活性化合物
- 是否适合 ADC/抗体/PROTAC/RNA 药物
- druggability score

### modality 判断示例

| 靶点特征 | 可能药物形式 |
|---|---|
| 激酶、酶、可成药口袋 | 小分子 |
| 细胞膜蛋白、肿瘤高表达 | 抗体 / ADC / CAR-T |
| 蛋白-蛋白互作、转录因子 | PROTAC / 分子胶 / RNA 药物，难度较高 |
| 分泌蛋白 | 抗体 / ligand trap |
| 核内非酶蛋白 | 可药性较弱，需谨慎 |

---

## 4.7 Safety liability：安全性风险

### 核心问题

抑制这个靶点是否可能造成严重正常组织毒性？

### 证据来源

- GTEx normal expression
- HPA normal tissue protein expression
- DepMap common essentiality
- Mouse knockout phenotype（后续）
- Human LoF constraint / gnomAD pLI/LOEUF（后续）

### 输出内容

- 正常组织表达风险
- essential gene 风险
- 是否在心脏、脑、肝、肾、骨髓等关键组织高表达
- safety concern level

### 风险等级

| 等级 | 含义 |
|---|---|
| Low | 正常组织表达低，非广泛 essential |
| Medium | 部分正常组织表达，需注意剂量/给药方式 |
| High | 多关键组织高表达或 common essential，安全性风险较高 |

---

## 4.8 Competitive / clinical landscape：竞品和临床格局

### 核心问题

这个靶点是否已有药物、临床试验或竞争者？

### 证据来源

- ClinicalTrials.gov
- ChEMBL approved drug information
- DrugBank
- 公司官网/公告（人工增强版）
- FDA/EMA/NMPA label（人工增强版）

### 输出内容

- 已上市药物
- 临床阶段药物
- 主要公司
- 适应症分布
- 竞争强度
- 是否存在差异化机会

### 判断逻辑

| 情况 | 解释 |
|---|---|
| 已有上市药物很多 | 证明靶点可行，但竞争激烈 |
| 有早期临床药物 | 有开发热度，需找差异化 |
| 无药物但有强生物学证据 | 可能是新机会，也可能是开发难度高 |
| 靶点失败药物多 | 需分析失败原因 |

---

## 5. 总评分模型设计

## 5.1 总体评分

建议总分 100 分。

| 模块 | 权重 |
|---|---:|
| 疾病相关性 | 15 |
| 表达谱证据 | 15 |
| 功能依赖性 | 15 |
| 机制通路证据 | 15 |
| 可药性 | 15 |
| 安全性风险 | 10 |
| 竞品/临床证据 | 10 |
| 用户场景匹配度 | 5 |

### 总分解释

| 分数 | 推荐等级 | 解释 |
|---:|---|---|
| 80–100 | A：强推荐 | 多维证据较强，适合深入验证/立项 |
| 65–79 | B：有潜力 | 有一定证据，但需补关键缺口 |
| 50–64 | C：谨慎推进 | 证据不完整或风险较明显 |
| 35–49 | D：低优先级 | 当前证据不足，不建议作为核心靶点 |
| <35 | E：不推荐 | 缺乏关键支持或风险较高 |

---

## 5.2 场景化权重

不同用户场景下，权重应不同。

### 基金/SCI 场景

更关注：

- 疾病相关性
- 机制通路
- 表达差异
- 可验证性
- 前期基础可补强性

### 企业靶点立项场景

更关注：

- druggability
- dependency
- indication opportunity
- safety
- competitor landscape
- patient stratification

### ADC 场景

更关注：

- 肿瘤细胞表面表达
- 正常组织低表达
- 膜定位
- internalization evidence（后续）
- 已有 ADC 竞品

### 小分子场景

更关注：

- 酶/激酶/可成药口袋
- ChEMBL 活性化合物
- 已有抑制剂
- pathway dependency
- safety window

---

## 6. MVP 版本设计

## 6.1 MVP目标

第一版目标不是做完整数据库平台，而是实现：

> 输入 target gene + disease，输出一份结构化、可下载、能引导付费的靶点初筛报告。

### MVP 必须验证的问题

1. 用户是否愿意输入靶点？
2. 用户是否觉得报告“说到点上”？
3. 用户是否愿意下载报告？
4. 用户是否愿意为人工增强版付费？
5. 哪些用户更感兴趣：基金客户、SCI客户，还是企业客户？

---

## 6.2 MVP 输入界面

页面标题：

> 靶点价值评估器

副标题：

> 输入一个靶点，快速评估其疾病相关性、表达证据、依赖性、可药性、安全性和转化价值。

表单字段：

1. Target gene symbol
2. 疾病/癌种
3. 研究目的：基金 / SCI / 靶点立项 / 药物研发 / 其他
4. 药物形式：不限 / 小分子 / 抗体 / ADC / PROTAC / RNA药物
5. 用户已有证据，可选
6. 联系方式，可选

按钮：

> 生成靶点评估报告

---

## 6.3 MVP 输出报告结构

### 报告标题

> Target Assessment Report: [GENE] in [DISEASE]

### 模块 1：靶点概览

- Gene symbol
- Full name
- Synonyms
- Protein class
- Subcellular localization（如可获得）
- 简短功能介绍

### 模块 2：总体评分

- Total score
- Recommendation level
- 一句话结论

示例：

> 综合评估显示，XXX 在胃癌中具有一定疾病相关性和机制研究价值，但目前缺少功能依赖性和蛋白层面的安全窗口证据，建议作为基金/SCI候选靶点继续补强，而不宜直接作为药物立项靶点。

### 模块 3：多维度评分

| 维度 | 分数 | 解释 |
|---|---:|---|
| 疾病相关性 | 12/15 | 目标癌种中有表达/文献支持 |
| 表达谱 | 10/15 | 肿瘤表达较高，但正常组织风险待评估 |
| 功能依赖性 | 8/15 | DepMap 证据中等 |
| 机制通路 | 11/15 | 与关键通路相关 |
| 可药性 | 6/15 | 暂无明确成熟药物 |
| 安全性 | 7/10 | 需关注正常组织表达 |
| 竞品/临床 | 3/10 | 临床开发信息有限 |

### 模块 4：关键证据摘要

- 支持证据
- 风险证据
- 缺失证据

### 模块 5：适合的研究场景

- 适合基金？
- 适合 SCI？
- 适合药物开发？
- 适合做 biomarker？

### 模块 6：下一步建议

- 建议补什么公共数据
- 建议补什么实验
- 建议如何构建机制假说
- 是否建议进入人工深度评估

---

## 7. 数据源与模块规划

## 7.1 第一版优先接入的数据源

| 数据源 | 用途 | 接入方式 | 优先级 |
|---|---|---|---|
| HGNC / mygene.info | gene symbol 标准化 | API | P0 |
| Open Targets | target-disease association | API/GraphQL | P0 |
| DepMap | CRISPR dependency | 下载/本地预处理 | P0 |
| TCGA | 表达、突变、CNV | 本地预处理 | P0 |
| GTEx | 正常组织表达 | 本地预处理 | P1 |
| Human Protein Atlas | 正常组织/肿瘤蛋白表达 | 下载/API/半自动 | P1 |
| ChEMBL | 药物、化合物、活性 | API | P1 |
| ClinicalTrials.gov | 临床试验 | API | P2 |
| PubMed | 文献支持 | API | P2 |
| Reactome/STRING | 通路和网络 | API/下载 | P2 |

---

## 7.2 数据接入策略

第一版不建议所有数据实时查询。推荐方式：

### 本地预处理数据

适合：TCGA、DepMap、GTEx、HPA。

原因：

- 查询速度快
- 可控稳定
- 避免 API 限流
- 便于统一评分

### 实时 API 查询

适合：Open Targets、ChEMBL、PubMed、ClinicalTrials。

原因：

- 数据更新频繁
- 结构化接口较方便
- 避免自己维护全部数据库

---

## 8. 技术架构设计

## 8.1 MVP技术栈

推荐：

- 前端：Streamlit 或 FastAPI + 简单 HTML
- 后端：Python
- 数据库：SQLite
- 数据处理：pandas / numpy
- 绘图：matplotlib / plotly
- 报告：Markdown + HTML + PDF
- AI解释：LLM API
- 部署：云服务器 + Nginx + Uvicorn

---

## 8.2 项目目录结构

```text
TargetAssessmentTool/
├── app.py                         # Streamlit 或 FastAPI 入口
├── config.py                      # 配置文件
├── requirements.txt
├── README.md
├── data/
│   ├── raw/                       # 原始下载数据
│   ├── processed/                 # 预处理数据
│   └── cache/                     # API缓存
├── modules/
│   ├── gene_resolver.py            # gene symbol 标准化
│   ├── opentargets_client.py       # Open Targets 查询
│   ├── depmap_module.py            # DepMap依赖性分析
│   ├── tcga_module.py              # TCGA表达/突变/CNV
│   ├── gtex_module.py              # 正常组织表达
│   ├── hpa_module.py               # HPA蛋白表达
│   ├── chembl_client.py            # ChEMBL药物/活性
│   ├── clinicaltrials_client.py    # 临床试验
│   ├── pathway_module.py           # 通路/网络
│   ├── scoring_engine.py           # 评分系统
│   ├── report_generator.py         # 报告生成
│   └── llm_interpreter.py          # AI解释
├── templates/
│   ├── report_template.md
│   ├── prompt_target_summary.txt
│   └── prompt_recommendation.txt
├── outputs/
│   ├── reports/
│   └── tables/
└── tests/
    ├── test_gene_resolver.py
    ├── test_scoring.py
    └── test_report.py
```

---

## 8.3 数据流

```text
用户输入 target + disease
        ↓
Gene symbol 标准化
        ↓
多数据源查询 / 本地数据检索
        ↓
生成结构化证据表
        ↓
评分系统计算各维度分数
        ↓
LLM 根据结构化证据生成解释
        ↓
生成 Markdown / PDF / Excel 报告
        ↓
用户下载 + 私信/付费引导
```

---

## 9. 核心模块伪代码

## 9.1 gene_resolver.py

```python
class GeneResolver:
    def resolve(self, gene_input: str) -> dict:
        """
        输入用户填写的 gene symbol，返回标准 HGNC symbol、Ensembl ID、Entrez ID、synonyms。
        """
        # 1. uppercase
        # 2. 查询本地 gene alias 表
        # 3. 若无结果，调用 mygene.info API
        # 4. 返回标准化结果
        return {
            "input": gene_input,
            "symbol": "EGFR",
            "ensembl_id": "ENSG00000146648",
            "entrez_id": "1956",
            "full_name": "epidermal growth factor receptor",
            "status": "resolved"
        }
```

---

## 9.2 depmap_module.py

```python
class DepMapModule:
    def get_dependency_summary(self, gene: str, cancer_type: str = None) -> dict:
        """
        从本地 DepMap CRISPR gene effect 数据中提取目标基因依赖性。
        """
        # 1. 加载 gene effect matrix
        # 2. 匹配 gene
        # 3. 根据 cancer_type 过滤 cell lines
        # 4. 计算 median, mean, fraction_dependency, lineage_rank
        return {
            "gene": gene,
            "pan_cancer_median_gene_effect": -0.35,
            "target_cancer_median_gene_effect": -0.62,
            "fraction_strong_dependency": 0.28,
            "is_common_essential_risk": False,
            "score": 11
        }
```

---

## 9.3 scoring_engine.py

```python
class TargetScoringEngine:
    def score(self, evidence: dict, scenario: str = "research") -> dict:
        """
        根据结构化证据计算多维度评分。
        """
        weights = self.get_weights(scenario)
        scores = {
            "disease_relevance": self.score_disease(evidence),
            "expression": self.score_expression(evidence),
            "dependency": self.score_dependency(evidence),
            "mechanism": self.score_mechanism(evidence),
            "druggability": self.score_druggability(evidence),
            "safety": self.score_safety(evidence),
            "clinical_competition": self.score_competition(evidence)
        }
        total = sum(scores[k] * weights[k] for k in scores)
        return {
            "scores": scores,
            "total_score": round(total, 1),
            "grade": self.assign_grade(total),
            "recommendation": self.generate_recommendation(total, scores)
        }
```

---

## 9.4 report_generator.py

```python
class ReportGenerator:
    def generate_markdown(self, target: str, disease: str, evidence: dict, score: dict, llm_text: dict) -> str:
        """
        根据模板生成 Markdown 报告。
        """
        md = render_template(
            "report_template.md",
            target=target,
            disease=disease,
            evidence=evidence,
            score=score,
            interpretation=llm_text
        )
        return md

    def export_pdf(self, markdown_text: str, output_path: str):
        """
        将 Markdown 转为 PDF。
        """
        pass

    def export_excel(self, evidence_table, output_path: str):
        """
        导出结构化证据表。
        """
        pass
```

---

## 10. 报告模板设计

## 10.1 PDF报告结构

```text
封面
- Target Assessment Report
- 靶点：XXX
- 疾病：XXX
- 报告日期

1. Executive Summary
- 一句话结论
- 总分
- 推荐等级
- 主要优势
- 主要风险

2. Target Overview
- 基因名称
- 蛋白功能
- 亚细胞定位
- 基础注释

3. Disease Relevance
- 疾病相关性证据
- 表达/突变/CNV
- 文献/数据库关联

4. Expression and Safety Window
- 肿瘤表达
- 正常组织表达
- 蛋白表达证据
- 安全性窗口

5. Functional Dependency
- DepMap CRISPR dependency
- 癌种特异性
- common essential 风险

6. Mechanistic Rationale
- 通路位置
- 机制解释
- 研究假说建议

7. Druggability and Clinical Landscape
- 已知药物/化合物
- 临床试验
- 竞品格局
- 药物形式适配

8. Final Recommendation
- 是否值得继续做
- 适合基金/SCI/企业立项吗
- 下一步补证据建议

附录
- 数据源
- 评分规则
- 免责声明
```

---

## 10.2 报告结尾转化文案

> 当前报告为自动化初筛结果，适合用于判断靶点是否值得继续深挖。若需要进一步形成基金前期基础、SCI机制故事线、企业靶点立项报告或适应症优先级分析，可进入人工增强版。

---

## 11. 前端 UI 设计

## 11.1 首页

### 标题

> 靶点价值评估器

### 副标题

> 输入一个靶点，从疾病相关性、表达谱、依赖性、机制、可药性、安全性和临床格局等维度快速生成评估报告。

### 三个入口卡片

1. **科研版**
   - 适合基金/SCI选题
   - 输出：机制与前期基础建议

2. **药物研发版**
   - 适合靶点立项和适应症选择
   - 输出：可药性、安全性、竞品格局

3. **候选基因排序版**
   - 适合输入多个候选基因
   - 输出：Top gene ranking

---

## 11.2 表单页

- 靶点输入框
- 疾病/癌种输入框
- 研究目的下拉框
- 药物形式下拉框
- 已有证据文本框
- 联系方式输入框，可选
- 生成报告按钮

---

## 11.3 报告页

### 顶部卡片

- Target
- Disease
- Total score
- Recommendation grade

### 雷达图

展示 7 个维度评分。

### 证据卡片

- 强证据
- 中等证据
- 风险证据
- 缺失证据

### 操作按钮

- 下载 PDF
- 下载 Excel
- 复制报告摘要
- 申请人工增强版

---

## 12. 商业模式设计

## 12.1 免费版

价格：免费

输出：

- 总体评分
- 3 条支持证据
- 3 条风险提示
- 是否建议继续做

目的：

- 获客
- 收集线索
- 验证需求

---

## 12.2 自动报告版

价格建议：49–199 元/次

输出：

- 5–8 页 PDF
- Excel 证据表
- 基础图表

适合：

- 学生
- 科研客户
- 初步判断靶点

---

## 12.3 人工增强版

价格建议：499–1999 元/次

输出：

- 10–20 页深度报告
- 人工核查数据
- 机制假说
- 实验验证建议
- 基金/SCI应用建议

---

## 12.4 企业版

价格建议：5000–30000 元/靶点

输出：

- Target assessment report
- indication prioritization
- competitor landscape
- biomarker strategy
- druggability/safety analysis
- expert summary

---

## 13. 30天开发路线图

## 第1周：完成最小功能

目标：输入 gene + disease，生成 Markdown 报告。

任务：

- 建立项目结构
- 完成 gene resolver
- 准备 3 个本地示例数据表
- 编写评分规则初版
- 编写报告模板
- 完成 Streamlit 表单

验收标准：

- 输入 EGFR + 肺癌，能生成一份基础报告。

---

## 第2周：接入核心数据

目标：加入真实数据证据。

任务：

- 下载/预处理 DepMap gene effect
- 准备 TCGA 表达/突变/CNV摘要表
- 接入 Open Targets 查询
- 接入 ChEMBL 查询
- 完成多维评分

验收标准：

- 输入 5 个常见靶点，报告结果基本合理。

---

## 第3周：做报告和UI

目标：产品化展示。

任务：

- 加入评分卡片
- 加入雷达图
- 加入证据表
- 支持 PDF/Excel 下载
- 加入“人工增强版”引导

验收标准：

- 用户可下载完整报告。

---

## 第4周：测试和获客

目标：拿到真实用户反馈。

任务：

- 做 5 个样品报告：EGFR、HER2、MUC1、CLDN18、BRCA1
- 发小红书/公众号介绍
- 免费开放 5 个靶点测试名额
- 记录用户反馈
- 优化评分和报告模板

验收标准：

- 至少 5 个真实 target 查询
- 至少 1 个用户咨询人工增强版

---

## 14. 可能存在的bug和风险

## 14.1 Gene symbol 不规范

### 问题

用户输入别名、旧名、错拼。

### 解决

- 建立 alias 表
- 调用 mygene.info
- 返回匹配候选让用户确认

---

## 14.2 数据源不一致

### 问题

TCGA、DepMap、HPA、ChEMBL 使用不同 ID 和版本。

### 解决

- 统一到 HGNC symbol + Ensembl ID
- 记录数据版本
- 报告中展示数据来源日期

---

## 14.3 AI 幻觉

### 问题

LLM 可能编造药物、文献或机制。

### 解决

- LLM 只能基于结构化证据解释
- 禁止编造具体文献和药物
- 关键证据必须来自 evidence table
- 报告中明确标注“需要人工复核”

---

## 14.4 评分过度主观

### 问题

用户可能质疑分数依据。

### 解决

- 每个评分展示证据依据
- 支持查看详细规则
- 提供人工增强版复核

---

## 14.5 正常组织安全性误判

### 问题

RNA 高表达不等于蛋白高表达，也不等于一定毒性。

### 解决

- 安全性只作为风险提示
- 尽量结合 HPA 蛋白表达
- 明确写“潜在风险，需实验/临床验证”

---

## 14.6 药物研发结论过度承诺

### 问题

不能说“这个靶点一定成药”。

### 解决

- 使用“初筛”“建议”“潜力”“风险”语言
- 加免责声明
- 企业报告需人工核查

---

## 14.7 数据更新问题

### 问题

药物、临床试验、数据库持续更新。

### 解决

- 报告显示数据版本和查询日期
- 临床/药物模块优先实时 API
- 定期更新本地数据库

---

## 15. 第一批测试靶点建议

| 靶点 | 疾病场景 | 测试目的 |
|---|---|---|
| EGFR | NSCLC | 经典靶点，验证 druggability/clinical 模块 |
| ERBB2/HER2 | Breast/Gastric cancer | ADC/抗体/表达模块测试 |
| CLDN18 | Gastric cancer | ADC/抗体靶点场景 |
| MUC1 | Pan-cancer | 表达高但特异性/安全性复杂 |
| BRCA1 | Ovarian/Breast cancer | DNA repair机制和合成致死场景 |
| KRAS | Pancreatic/Lung cancer | 强遗传驱动但可药性复杂 |
| PRMT5 | MTAP-loss cancer | 合成致死和依赖性场景 |
| B7-H3/CD276 | Solid tumors | 免疫/ADC靶点场景 |

---

## 16. 小红书/公众号宣传切入点

## 16.1 小红书标题

1. 输入一个基因，怎么判断它值不值得做课题？
2. 一个靶点能不能做，不能只看差异表达
3. 候选基因太多？先做一次靶点体检
4. 靶点评估要看哪7类证据？
5. 为什么有些高表达基因不适合做药物靶点？
6. 我做了一个靶点价值评估器，免费开放5个测试名额
7. ADC靶点最怕什么？不是表达低，而是正常组织也高
8. 基金选题前，先看看你的靶点有没有证据链

## 16.2 行动号召

> 如果你有一个候选靶点，但不确定是否值得继续做，可以私信【靶点体检】，发送：靶点名 + 疾病方向 + 你最关心的问题。我可以帮你做一次简版评估。

---

## 17. 与“本子有光”的业务衔接

该工具可作为“本子有光”的第二个产品线。

### 第一产品线

> 课题体检：帮用户判断基金/SCI课题是否值得做。

### 第二产品线

> 靶点体检：帮用户判断一个基因/蛋白是否值得作为课题核心或药物靶点。

### 转化路径

```text
小红书内容
  ↓
免费靶点体检
  ↓
自动报告
  ↓
人工增强版
  ↓
基金前期基础 / SCI机制故事 / 企业靶点评估
```

---

## 18. 最小可执行版本总结

第一版只需要完成：

1. 输入 target + disease。
2. 标准化 gene symbol。
3. 查询或读取：Open Targets、DepMap、TCGA摘要、ChEMBL。
4. 生成 7 维评分。
5. 生成 Markdown/PDF 报告。
6. 加入人工增强版转化入口。
7. 用 5 个靶点做样品报告。
8. 发小红书测试真实需求。

不要一开始做复杂平台、登录、支付、实时全数据库、多用户系统。

核心目标是：

> 30 天内验证：是否有人愿意提交靶点，是否有人愿意为完整靶点评估报告付费。

---

## 19. 推荐下一步行动

### 你现在可以立即做的事

1. 选定产品名：**本子有光 · 靶点体检器**。
2. 准备 5 个样品靶点：EGFR、HER2、CLDN18、MUC1、BRCA1。
3. 写第一篇小红书：
   - 标题：输入一个基因，怎么判断它值不值得做课题？
4. 开发第一个 Streamlit 表单。
5. 先用手动/半自动方式生成第一份报告。
6. 根据报告体验再决定是否接入更多数据库。

---

## 20. 项目原则

1. **先闭环，再扩展。**
2. **先报告，再平台。**
3. **先人工增强，再全自动。**
4. **前台卖判断，后台用数据。**
5. **不要承诺靶点一定有效，只提供证据分层和决策建议。**
6. **所有结论必须可追溯到数据源。**
7. **AI 只负责解释和生成报告，不负责凭空创造证据。**

---

## 参考数据源与说明

- DepMap Portal：用于开放癌症依赖性数据、CRISPR/RNAi screens 和癌症脆弱性分析。
- Human Protein Atlas：用于正常组织、肿瘤组织和细胞系中的 RNA/蛋白表达证据。
- ChEMBL Web Services：用于靶点、化合物、生物活性、药物机制和药物研发相关数据。
- Open Targets Platform：用于 target-disease association 和遗传/药物/文献等多证据整合。
- TCGA/GTEx：用于肿瘤和正常组织表达、突变、CNV等公共组学证据。


