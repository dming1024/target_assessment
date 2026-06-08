# Target Assessment Tool · 靶点价值评估器

输入一个靶点基因和疾病/癌种，从多维度自动生成靶点价值评估报告，帮助判断：**这个靶点是否值得继续做、在哪个适应症中最有潜力、下一步应该补什么证据。**

---

## Table of Contents

- [Quick Start](#quick-start)
- [What This Tool Does](#what-this-tool-does)
- [Data Sources](#data-sources)
- [Scoring Model](#scoring-model)
- [Result Interpretation](#result-interpretation)
- [Web App Usage](#web-app-usage)
- [Project Architecture](#project-architecture)
- [Maintenance Guide](#maintenance-guide)
- [FAQ](#faq)

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Launch the web app
streamlit run app.py
```

Then open `http://localhost:8501`, enter a gene symbol (e.g., `EGFR`) and a disease (e.g., `NSCLC`), and click "Generate Report".

### Requirements

- Python 3.8+
- Internet access (for real-time API queries)
- Dependencies: `streamlit`, `pandas`, `numpy`, `httpx`, `plotly`, `openpyxl`, `markdown`, `weasyprint`

---

## What This Tool Does

This is a **multi-dimensional target assessment engine** for drug discovery and biomedical research. Given a gene symbol and a disease/cancer type, it:

1. **Resolves** the gene symbol to an official HGNC identifier (via local cache + mygene.info)
2. **Collects evidence** from 5 real data sources (APIs + local files)
3. **Scores** the target across 8 dimensions with scenario-based weighting
4. **Generates** a structured report (Markdown / HTML / Excel)

The tool is designed as a **decision-support system** — it helps researchers and drug developers quickly triage targets before investing in deep manual curation.

---

## Data Sources

### Real-time APIs

| Source | Method | What It Provides | Rate Limit |
|--------|--------|-----------------|------------|
| **Open Targets Platform** | GraphQL API | Target-disease association score (0–1), evidence breakdown by type (literature, genetic association, somatic mutation, known drugs, RNA expression, affected pathways) | No strict limit |
| **ChEMBL** | REST API | Counts of approved drugs, clinical candidates, and active compounds for a target; modality fit assessment | ~1 request/s |
| **ClinicalTrials.gov** | REST API v2 | Active clinical trial counts for gene + disease; differentiation opportunity | ~50 requests/min |

### Local Data Files

| Source | File | What It Provides |
|--------|------|-----------------|
| **DepMap** | `data/processed/depmap_crispr_summary.csv` | CRISPR gene effect scores (Chronos), cancer-type selectivity, pan-cancer percentile ranks |
| **TCGA** | `data/processed/tcga_expression_summary.csv` | Median TPM (tumor/normal), log2 fold change, overexpression category, tissue specificity |
| **TCGA** | `data/processed/tcga_mutation_summary.csv` | Mutation frequency, CNV amplification/deletion frequency, prognostic association |

### Sample Data (fallback)

Pre-curated evidence for 6 canonical targets (EGFR, ERBB2, CLDN18, MUC1, BRCA1, KRAS) in `modules/sample_data.py`. Used to fill gaps when real APIs return sparse data for well-known targets.

### Evidence Collection Priority

```
Real APIs + Local Data (primary)  →  Sample Data (enrichment)  →  Generic Template (fallback)
```

---

## Scoring Model

### Overview

The total score is a **weighted sum of 8 dimension scores**, normalized to 0–100.

### Formula

```
Total Score = Σ ( dimension_raw_score / dimension_max × dimension_weight ) × 100
```

Where:
- `dimension_raw_score` — raw score for each dimension (0 to dimension_max)
- `dimension_max` — maximum possible raw score for that dimension
- `dimension_weight` — scenario-dependent weight (sum of all weights = 1.0)

### Dimension Max Scores & Weights by Scenario

| Dimension | Max | general | research | drug_dev | adc | small_mol |
|-----------|-----|---------|----------|----------|-----|-----------|
| disease_relevance | 15 | 0.15 | **0.20** | 0.15 | 0.10 | 0.10 |
| expression | 15 | 0.15 | 0.15 | 0.15 | **0.25** | 0.10 |
| dependency | 15 | 0.15 | 0.10 | 0.15 | 0.10 | 0.15 |
| mechanism | 15 | 0.15 | **0.20** | 0.10 | 0.05 | 0.15 |
| druggability | 15 | 0.15 | 0.10 | 0.15 | 0.20 | **0.25** |
| safety | 10 | 0.10 | 0.10 | **0.15** | **0.20** | 0.15 |
| clinical_competition | 10 | 0.10 | 0.10 | 0.10 | 0.05 | 0.05 |
| scenario_fit | 5 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 |
| **Sum** | | **1.00** | **1.00** | **1.00** | **1.00** | **1.00** |

### Dimension Scoring Rules

#### 1. Disease Relevance (max: 15 points)

Assesses how strongly the target is linked to the disease through expression, mutation, literature, and database annotations.

| Evidence | Condition | Points |
|----------|-----------|--------|
| Target overexpression in cancer | `"high"` | +6.0 |
| | `"moderate"` | +3.75 |
| | `"low"` | +0.75 |
| Prognostic association | True | +3.0 |
| Mutation/CNV frequency | > 10% | +3.0 |
| | > 3% | +1.5 |
| Open Targets association | score > 0.01 | +1.5 |
| Literature evidence | `"high"` | +1.5 |
| | `"moderate"` | +0.75 |

**Data sources:** TCGA mutation/CNV frequencies, Open Targets association score & literature score.

#### 2. Expression Profile (max: 15 points)

Evaluates tumor expression level and tumor-vs-normal specificity — critical for ADC/antibody targets.

| Evidence | Condition | Points |
|----------|-----------|--------|
| Tumor expression level | `"high"` | +6.0 |
| | `"moderate"` | +3.75 |
| | `"low"` | +0.75 |
| Tumor-normal differential | `"significant"` (log2FC > 2) | +4.5 |
| | `"moderate"` (log2FC > 1) | +2.25 |
| Protein-level evidence | True | +2.25 |
| Tissue specificity | `"high"` | +2.25 |
| | `"moderate"` | +1.2 |

**Data sources:** TCGA expression summary (median TPM, log2FC), Open Targets RNA expression score.

#### 3. Functional Dependency (max: 15 points)

Based on DepMap CRISPR knockout screens. Stronger dependency = more points. **Common essential genes are penalized** (capped at 30% of max).

| Evidence | Condition | Points |
|----------|-----------|--------|
| Cancer dependency level | `"strong"` (Chronos < −0.5) | +7.5 |
| | `"moderate"` (Chronos < −0.3) | +4.5 |
| | `"weak"` (Chronos ≥ −0.3) | +1.5 |
| Pan-cancer selectivity | `"selective"` | +3.75 |
| | `"moderate_selective"` | +1.5 |
| **Common essential cap** | If true | **max 4.5 pts total** |
| Mutation-conditioned dependency | True | +3.75 |

**Data sources:** DepMap CRISPR Chronos scores, pan-cancer percentile rank, selectivity classification.

#### 4. Mechanism & Pathway Evidence (max: 15 points)

Evaluates biological rationale: how well-understood is the mechanism linking the target to the disease?

| Evidence | Condition | Points |
|----------|-----------|--------|
| Relevant pathway count | ≥ 3 pathways | +5.25 |
| | 1–2 pathways | +3.0 |
| Mechanism strength | `"well_established"` | +5.25 |
| | `"partially_established"` | +3.0 |
| Connects to disease hallmarks | True | +4.5 |

**Data sources:** Open Targets datatype scores (genetic_association, somatic_mutation, affected_pathway, known_drug). Each score > 0.01 counts as one relevant pathway.

#### 5. Druggability (max: 15 points)

Assesses the existing drug development landscape for the target.

| Evidence | Condition | Points |
|----------|-----------|--------|
| Approved drugs | ≥ 1 | +6.0 |
| Clinical candidates | ≥ 1 | +3.75 |
| Active compounds | ≥ 1 | +2.25 |
| Modality fit | `"strong"` | +3.0 |
| | `"moderate"` | +1.5 |

**Data sources:** ChEMBL API (counts of approved/clinical/active compounds by max_phase).

#### 6. Safety Risk (max: 10 points)

Starts at full score and deducts for safety concerns. **Higher score = safer.**

| Risk Factor | Condition | Penalty |
|-------------|-----------|---------|
| Normal tissue expression | `"high"` | −6.0 |
| | `"moderate"` | −3.0 |
| | `"low"` | −1.0 |
| Common essential gene | True | −5.0 |
| Critical organ expression | ≥ 2 organs | −3.0 |
| | 1 organ | −1.5 |

**Data sources:** TCGA tumor-normal differential, DepMap common essential classification.

#### 7. Clinical & Competitive Landscape (max: 10 points)

Higher score = more validated target (not necessarily less competitive).

| Evidence | Condition | Points |
|----------|-----------|--------|
| Approved drugs (competition) | ≥ 2 | +5.0 |
| | 1 | +3.5 |
| Active clinical trials | ≥ 10 | +3.0 |
| | 3–9 | +1.5 |
| Differentiation opportunity | `"high"` | +2.0 |
| | `"moderate"` | +1.0 |

**Data sources:** ChEMBL approved drug count, ClinicalTrials.gov active trial count.

#### 8. Scenario Fit (max: 5 points)

Bonus points for how well the target profile matches the chosen assessment scenario.

| Scenario | Scoring Criteria |
|----------|-----------------|
| **research** (基金/SCI) | Literature level (+40%), mechanism strength (+40%), tumor expression (+20%) |
| **drug_development** | Modality fit (+35%), dependency (+35%), safety window (+30%) |
| **adc** | Protein evidence (+40%), tumor-normal differential (+35%), safety window (+25%) |
| **small_molecule** | Modality fit (+40%), active compounds (+30%), mechanism (+30%) |
| **general** | Flat 50% baseline |

### Grade Assignment

| Score Range | Grade | Interpretation |
|-------------|-------|----------------|
| 80 – 100 | **A** | 强推荐 — 多维证据较强，适合深入验证/立项 |
| 65 – 80 | **B** | 有潜力 — 有一定证据，但需补关键缺口 |
| 50 – 65 | **C** | 谨慎推进 — 证据不完整或风险较明显 |
| 35 – 50 | **D** | 低优先级 — 当前证据不足，不建议作为核心靶点 |
| 0 – 35 | **E** | 不推荐 — 缺乏关键支持或风险较高 |

### Concrete Example: ERBB2 + Breast Cancer (drug_development)

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

(Note: with sample data enrichment providing higher druggability and
clinical numbers, the score can reach 92–95 → Grade A)
```

---

## Result Interpretation

### What a High Score (A) Means

- Multiple independent lines of evidence support the target
- The target has strong disease relevance, well-characterized mechanism, and established drugs
- **Action:** Proceed to in-depth validation, IND-enabling studies, or grant writing
- **Example:** EGFR in NSCLC, ERBB2 in Breast Cancer, KRAS in Pancreatic Cancer

### What a Moderate Score (B) Means

- Some evidence dimensions are strong, but others have gaps
- The target shows promise but needs additional validation
- **Action:** Identify and fill the specific evidence gaps shown in the report
- **Example:** CLDN18 in Gastric Cancer (emerging ADC target, limited drug history)

### What a Low Score (C/D/E) Means

- Limited or conflicting evidence across multiple dimensions
- May be a tumor suppressor (not directly druggable), a common essential gene (safety risk), or simply understudied
- **Action:** Re-evaluate target selection; if pursuing, plan significant foundational experiments
- **Example:** BRCA1 in Ovarian Cancer (tumor suppressor, PARP inhibitor context)

### How to Use the Radar Chart

The radar chart shows each dimension as a percentage of its maximum score. A balanced chart with broad coverage is better than one with a single spike. Gaps in the chart directly indicate where more evidence is needed.

---

## Web App Usage

### Input Fields

| Field | Description | Example |
|-------|-------------|---------|
| **Target Gene** | HGNC gene symbol or common alias | `EGFR`, `HER2`, `CLDN18`, `PD-L1` |
| **Disease / Cancer Type** | Disease name (English) | `NSCLC`, `Breast Cancer`, `Gastric Cancer` |
| **Scenario** | Assessment context that determines dimension weights | `research` (基金/SCI), `drug_development`, `adc`, `small_molecule`, `general` |
| **Modality** | Drug modality of interest (optional) | `small_molecule`, `antibody`, `adc`, `protac`, `rna` |

### Output

1. **Summary cards** — Gene info, total score, grade, scenario
2. **One-line recommendation** — Actionable guidance based on score
3. **Radar chart** — Visual comparison of all 8 dimensions
4. **Score table** — Per-dimension scores with percentages
5. **Strengths / Risks / Gaps** — Three-column evidence summary
6. **Downloadable reports** — Markdown (.md), HTML (.html), Excel (.xlsx)

---

## Project Architecture

```
target_assessment/
├── app.py                         # Streamlit web application
├── config.py                      # Weights, thresholds, API endpoints, gene aliases
├── requirements.txt               # Python dependencies
├── project.md                     # Full project plan (Chinese)
│
├── modules/                       # Core logic
│   ├── gene_resolver.py           # Gene symbol → HGNC via mygene.info + local cache
│   ├── data_manager.py            # Central orchestrator for evidence collection
│   ├── scoring_engine.py          # Multi-dimensional scoring & grading
│   ├── report_generator.py        # Markdown / HTML / Excel report generation
│   ├── sample_data.py             # Pre-curated evidence for 6 canonical targets
│   ├── opentargets_client.py      # Open Targets GraphQL client
│   ├── chembl_client.py           # ChEMBL REST client (with rate limiting)
│   ├── clinicaltrials_client.py   # ClinicalTrials.gov REST v2 client
│   ├── depmap_module.py           # DepMap CRISPR data (local CSV reader)
│   └── tcga_module.py             # TCGA expression & mutation (local CSV reader)
│
├── data/
│   ├── processed/                 # Preprocessed data files
│   │   ├── depmap_crispr_summary.csv
│   │   ├── tcga_expression_summary.csv
│   │   └── tcga_mutation_summary.csv
│   ├── raw/                       # Raw downloaded data (place DepMap/TCGA files here)
│   └── cache/                     # API response cache (auto-generated)
│
├── templates/
│   ├── report_template.md         # Markdown report template
│   └── prompt_target_summary.txt  # AI prompt template
│
├── tests/
│   ├── test_data_manager.py
│   ├── test_gene_resolver.py
│   ├── test_scoring.py
│   └── test_report.py
│
└── outputs/
    ├── reports/                   # Generated markdown reports
    └── tables/                    # Generated Excel evidence tables
```

### Data Flow

```
User Input (gene + disease + scenario)
       │
       ▼
GeneResolver ─── mygene.info API ───► Standardized gene symbol + Ensembl ID
       │
       ▼
DataManager ───┬── OpentargetsClient (GraphQL)  ──► disease_relevance, mechanism
               ├── ChemblClient (REST)           ──► druggability
               ├── ClinicaltrialsClient (REST)   ──► clinical_competition
               ├── DepMapModule (local CSV)      ──► dependency
               ├── TCGAModule (local CSV)        ──► expression, mutation
               └── Sample Data (fallback)        ──► enrichment for known targets
       │
       ▼
ScoringEngine ─── 8 dimensions × scenario weights ──► Total score + Grade
       │
       ▼
ReportGenerator ─── Markdown / HTML / Excel ──► Downloadable reports
```

---

## Maintenance Guide

### Adding a New Disease Mapping

Edit `EFO_DISEASE_MAP` in `config.py`:

```python
EFO_DISEASE_MAP = {
    # ... existing entries ...
    "new disease name": "EFO_XXXXXXXXX",
}
```

Find EFO IDs at: https://www.ebi.ac.uk/ols/ontologies/efo

### Updating DepMap Data

1. Download the latest CRISPR gene effect file from https://depmap.org/portal/download/
2. Preprocess it to match the schema in `data/processed/depmap_crispr_summary.csv`:

```csv
gene,primary_disease,mean_chronos_score,num_cell_lines,pan_cancer_mean_score,pan_cancer_percentile,selectivity_category
```

- `mean_chronos_score` — average Chronos dependency score for this gene in this cancer type
- `pan_cancer_mean_score` — average Chronos score across all cancer types
- `pan_cancer_percentile` — percentile rank (lower = more dependent)
- `selectivity_category` — `"selective"` (< 25th percentile), `"moderate_selective"` (25–75th), `"weak"` (> 75th)

3. Replace the file and restart the app

### Updating TCGA Data

1. Download expression and mutation data from cBioPortal, TCGA GDC, or similar
2. Preprocess into two files:

**Expression** (`tcga_expression_summary.csv`):
```csv
gene,cancer_type,median_tpm_tumor,median_tpm_normal,log2fc_tumor_normal,overexpression_category,tumor_normal_diff_category,tissue_specificity
```

- `overexpression_category` — `"high"` (TPM > 50 or log2FC > 2), `"moderate"`, `"low"`
- `tumor_normal_diff_category` — `"significant"` (log2FC > 2), `"moderate"` (log2FC > 1), `"none"`
- `tissue_specificity` — `"high"` (expressed in < 5 tissue types), `"moderate"`, `"low"`

**Mutation** (`tcga_mutation_summary.csv`):
```csv
gene,cancer_type,mutation_freq,cnv_amp_freq,cnv_del_freq,total_alteration_freq,prognostic_associated
```

3. Replace the files and restart the app

### Managing API Rate Limits

- **ChEMBL**: 1 request/second limit enforced by `chembl_client.py` (1.1s interval). If you receive 429 errors, increase `_min_interval`.
- **ClinicalTrials.gov**: 50 requests/minute. The client enforces 1.2s between requests. Adjust `_min_interval` if needed.
- **Open Targets**: No formal limit, but avoid rapid-fire queries.

### Clearing API Cache

```bash
rm data/cache/*.json
```

The cache stores API responses keyed by gene+disease. Clear it after updating local data or if you suspect stale results.

### Adding a New Data Source

1. Create a new client module in `modules/` (follow the pattern of existing clients)
2. Add the client initialization in `DataManager.__init__`
3. Call the client in `DataManager._build_from_real_sources`
4. Map the client's output to the evidence dict dimensions
5. Add tests in `tests/`

### Tuning Scoring Weights

Edit `SCENARIO_WEIGHTS` in `config.py`. Each weight dictionary must sum to 1.0. Dimension max scores are in `DIMENSION_MAX`. Individual scoring rules are in `ScoringEngine` methods (`_score_disease_relevance`, `_score_druggability`, etc.).

### Running Tests

```bash
python3.8 -m pytest tests/ -v
```

Note: Some tests make real API calls and require internet access. Tests may take 30–60 seconds.

---

## FAQ

### Q: Does this tool require API keys?

No. All data sources (Open Targets, ChEMBL, ClinicalTrials.gov, mygene.info) are free and open-access. No registration required.

### Q: Why do some targets show 0 for certain dimensions?

If the gene is not in DepMap/TCGA local data files or not found in the APIs, that dimension defaults to `"unknown"` and scores 0. This is expected for:
- Very new or poorly annotated genes
- Non-human genes
- Genes not studied in the specified disease context

### Q: How do I interpret "differentiation opportunity = high"?

It means few active clinical trials exist for this target in this disease — you have room to differentiate. But it also means the target is less clinically validated. Balance this with the overall score and your risk tolerance.

### Q: Why does BRCA1 score low despite being clinically important?

BRCA1 is a tumor suppressor — it is **lost** in cancer, not overexpressed. You can't "drug" a missing protein. The scoring model correctly identifies this as poor druggability. In practice, BRCA1 status is used for **patient stratification** (PARP inhibitor sensitivity), not as a direct drug target. The tool's output helps you recognize this distinction.

### Q: Can I use this for non-cancer diseases?

Yes. The scoring model is disease-agnostic. However, the current data sources (TCGA, DepMap) are cancer-focused. For non-cancer diseases, you may get sparse results. Add appropriate data sources for your disease area.

### Q: How do I cite this tool?

The tool aggregates data from public databases. Cite the underlying data sources:
- **Open Targets**: Ochoa et al. (2023), *Nucleic Acids Research*
- **ChEMBL**: Mendez et al. (2019), *Nucleic Acids Research*
- **DepMap**: Tsherniak et al. (2017), *Cell*
- **TCGA**: The Cancer Genome Atlas Research Network
- **ClinicalTrials.gov**: U.S. National Library of Medicine
