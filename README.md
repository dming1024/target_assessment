# Target Assessment Tool

Enter a target gene and disease/cancer type, and this tool automatically generates a multi-dimensional target assessment report to help answer: **is this target worth pursuing, which indication has the most potential, and what evidence gaps need to be filled next.**

---

## Table of Contents

- [Quick Start](#quick-start)
- [What This Tool Does](#what-this-tool-does)
- [Offline Database](#offline-database)
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
# Install dependencies
pip install -r requirements.txt

# Build offline database (first time only — do once, then run offline forever)
python3.8 data/build_offline_db.py

# CLI — quick assessment from command line
python3.8 run.py --gene EGFR --disease NSCLC

# Web app — interactive browser interface
streamlit run app.py
```

### CLI vs Web App

| | CLI (`run.py`) | Web App (`app.py`) |
|---|---|---|
| **Interface** | Terminal | Browser (Streamlit) |
| **Use case** | Batch evaluation, scripting, quick lookups | Interactive exploration, presentations |
| **Output** | Prints summary to stdout + saves files | Interactive charts + download buttons |
| **Best for** | Power users, automation | First-time users, demos |

---

### Requirements

- Python 3.8+
- Offline mode: **no internet required** (recommended)
- Online fallback: internet access required only when SQLite DB is absent
- Dependencies: `streamlit`, `pandas`, `numpy`, `httpx`, `plotly`, `openpyxl`, `markdown`, `weasyprint`

---

## What This Tool Does

This is a **multi-dimensional target assessment engine** for drug discovery and biomedical research. Given a gene symbol and a disease/cancer type, it:

1. **Resolves** the gene symbol to an official HGNC identifier (offline DB → mygene.info API fallback)
2. **Collects evidence** from the offline SQLite database (primary) or live APIs (fallback)
3. **Scores** the target across 8 dimensions with scenario-based weighting
4. **Generates** a structured report (Markdown / HTML / Excel)

The tool is designed as a **decision-support system** — it helps researchers and drug developers quickly triage targets before investing in deep manual curation.

---

## Offline Database

The offline SQLite database (`data/processed/target_assessment.db`) bundles all evidence data into a single ~1.2 GB file, enabling **sub-second queries without any network access**.

### Database Contents

| Table | Rows | Source | Description |
|-------------|-------------|---------------|---------------------|
| `genes` | ~194,000 | NCBI Gene | Gene symbols, Ensembl IDs, aliases |
| `opentargets` | ~500,000 | Open Targets Platform | Target-disease association scores |
| `chembl_drugs` | ~2,000 | ChEMBL | Approved/clinical/active drug counts per target |
| `depmap_crispr` | ~18,000 | DepMap | CRISPR dependency scores by cancer type |
| `tcga_expression` | ~20,000 | TCGA | Tumor expression (TPM, log2FC) by cancer type |
| `tcga_mutation` | ~20,000 | TCGA | Mutation & CNV frequencies by cancer type |

### Building the Database

**First-time build** (requires network):

```bash
# Full build — downloads all upstream data (~1.5 GB download)
python3.8 data/build_offline_db.py

# Build only with local CSV files (no external downloads)
python3.8 data/build_offline_db.py --only-local

# Build only the genes table
python3.8 data/build_offline_db.py --only-genes
```

### Updating the Database

When upstream data sources release new versions, you can update individual tables without rebuilding everything:

```bash
# Update specific tables
python3.8 data/update_offline_db.py --table depmap_crispr      # DepMap CRISPR data
python3.8 data/update_offline_db.py --table tcga                # Both TCGA tables
python3.8 data/update_offline_db.py --table genes               # NCBI gene info
python3.8 data/update_offline_db.py --table opentargets         # Open Targets associations
python3.8 data/update_offline_db.py --table chembl              # ChEMBL drug counts

# Dry-run — check what would be updated without making changes
python3.8 data/update_offline_db.py --table depmap_crispr --dry-run

# Full rebuild with backup
python3.8 data/update_offline_db.py --full
```

The update script:
- **Backs up** the existing database before making changes
- **Validates** the updated table after import (row count, schema check)
- **Supports rollback** if validation fails
- Updates **in-place** on the existing database (no full rebuild needed for single tables)

### Typical Update Cadence

| Data Source | Update Frequency | When to Update |
|----------------------|----------------------------|--------------------------|
| NCBI Gene | Quarterly | When new gene annotations are released |
| DepMap | Quarterly | When new CRISPR screen releases drop (e.g., 24Q4) |
| TCGA | Rarely | TCGA data is relatively stable; update if reprocessed |
| Open Targets | Monthly | Platform releases are monthly; significant changes quarterly |
| ChEMBL | Quarterly | New ChEMBL versions (e.g., 37 to 38) |

---

## Data Sources

### Primary: Offline SQLite Database

When `data/processed/target_assessment.db` exists, all evidence is queried from it directly with **sub-second latency and zero network calls**. See [Offline Database](#offline-database) above.

### Fallback: Live APIs

If the offline database is not available, the tool falls back to live API queries:

| Source | Method | What It Provides | Rate Limit |
|--------|--------|---------------------------|------------|
| **Open Targets Platform** | GraphQL API | Target-disease association score (0–1), evidence breakdown by type | No strict limit |
| **ChEMBL** | REST API | Drug counts by phase, modality fit assessment | ~1 request/s |
| **ClinicalTrials.gov** | REST API v2 | Active clinical trial counts, differentiation opportunity | ~50 requests/min |
| **mygene.info** | REST API | Gene symbol resolution, Ensembl ID lookup | No strict limit |

### Local Data Files

| Source | File | What It Provides |
|--------|------|---------------------------|
| **DepMap** | `data/processed/depmap_crispr_summary.csv` | CRISPR gene effect scores (Chronos), selectivity, percentile ranks |
| **TCGA** | `data/processed/tcga_expression_summary.csv` | Median TPM (tumor/normal), log2FC, overexpression category |
| **TCGA** | `data/processed/tcga_mutation_summary.csv` | Mutation frequency, CNV amp/del frequency, prognostic association |

### Sample Data (fallback)

Pre-curated evidence for canonical targets (EGFR, ERBB2, CLDN18, MUC1, BRCA1, KRAS) in `modules/sample_data.py`. Used to fill gaps when real data returns sparse results for well-known targets.

### Evidence Collection Priority

```
Offline SQLite DB (primary, <1s)  →  Sample Data (enrichment)  →  Generic Template (fallback)
     ↓ (if DB unavailable)
Live APIs (fallback, 5–15s)
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

#### 3. Functional Dependency (max: 15 points)

Based on DepMap CRISPR knockout screens. Stronger dependency = more points. **Common essential genes are penalized** (capped at 30% of max).

| Evidence | Condition | Points |
|----------|-----------|--------|
| Cancer dependency level | `"strong"` (Chronos < -0.5) | +7.5 |
| | `"moderate"` (Chronos < -0.3) | +4.5 |
| | `"weak"` (Chronos >= -0.3) | +1.5 |
| Pan-cancer selectivity | `"selective"` | +3.75 |
| | `"moderate_selective"` | +1.5 |
| **Common essential cap** | If true | **max 4.5 pts total** |
| Mutation-conditioned dependency | True | +3.75 |

#### 4. Mechanism & Pathway Evidence (max: 15 points)

Evaluates biological rationale: how well-understood is the mechanism linking the target to the disease?

| Evidence | Condition | Points |
|----------|-----------|--------|
| Relevant pathway count | >= 3 pathways | +5.25 |
| | 1–2 pathways | +3.0 |
| Mechanism strength | `"well_established"` | +5.25 |
| | `"partially_established"` | +3.0 |
| Connects to disease hallmarks | True | +4.5 |

#### 5. Druggability (max: 15 points)

Assesses the existing drug development landscape for the target.

| Evidence | Condition | Points |
|----------|-----------|--------|
| Approved drugs | >= 1 | +6.0 |
| Clinical candidates | >= 1 | +3.75 |
| Active compounds | >= 1 | +2.25 |
| Modality fit | `"strong"` | +3.0 |
| | `"moderate"` | +1.5 |

#### 6. Safety Risk (max: 10 points)

Starts at full score and deducts for safety concerns. **Higher score = safer.**

| Risk Factor | Condition | Penalty |
|-------------|-----------|---------|
| Normal tissue expression | `"high"` | -6.0 |
| | `"moderate"` | -3.0 |
| | `"low"` | -1.0 |
| Common essential gene | True | -5.0 |
| Critical organ expression | >= 2 organs | -3.0 |
| | 1 organ | -1.5 |

#### 7. Clinical & Competitive Landscape (max: 10 points)

Higher score = more validated target (not necessarily less competitive).

| Evidence | Condition | Points |
|----------|-----------|--------|
| Approved drugs (competition) | >= 2 | +5.0 |
| | 1 | +3.5 |
| Active clinical trials | >= 10 | +3.0 |
| | 3–9 | +1.5 |
| Differentiation opportunity | `"high"` | +2.0 |
| | `"moderate"` | +1.0 |

#### 8. Scenario Fit (max: 5 points)

Bonus points for how well the target profile matches the chosen assessment scenario.

| Scenario | Scoring Criteria |
|----------|-----------------|
| **research** | Literature level (+40%), mechanism strength (+40%), tumor expression (+20%) |
| **drug_development** | Modality fit (+35%), dependency (+35%), safety window (+30%) |
| **adc** | Protein evidence (+40%), tumor-normal differential (+35%), safety window (+25%) |
| **small_molecule** | Modality fit (+40%), active compounds (+30%), mechanism (+30%) |
| **general** | Flat 50% baseline |

### Grade Assignment

| Score Range | Grade | Interpretation |
|-------------|-------|----------------|
| 80 – 100 | **A** | Strong recommendation — strong multi-dimensional evidence, suitable for in-depth validation / project initiation |
| 65 – 80 | **B** | Promising — has evidence but needs key gaps filled |
| 50 – 65 | **C** | Proceed cautiously — incomplete evidence or notable risk |
| 35 – 50 | **D** | Low priority — insufficient evidence, not recommended as a core target |
| 0 – 35 | **E** | Not recommended — lacks critical support or high risk |

### Concrete Example: ERBB2 + Breast Cancer (drug_development)

```
disease_relevance:  13.8 / 15  x 0.15 = 0.138
expression:          13.8 / 15  x 0.15 = 0.138
dependency:          11.2 / 15  x 0.15 = 0.112
mechanism:           10.5 / 15  x 0.10 = 0.070
druggability:        12.8 / 15  x 0.15 = 0.128
safety:               7.0 / 10  x 0.15 = 0.105
clinical_competition: 5.0 / 10  x 0.10 = 0.050
scenario_fit:         2.0 /  5  x 0.05 = 0.020
                                  --------
Weighted sum:                            0.761
Total Score: 0.761 x 100 = 76.1 -> Grade B
```

---

## Result Interpretation

### What a High Score (A) Means

- Multiple independent lines of evidence support the target
- Strong disease relevance, well-characterized mechanism, established drugs
- **Action:** Proceed to in-depth validation, IND-enabling studies, or grant writing
- **Example:** EGFR in NSCLC, ERBB2 in Breast Cancer, KRAS in Pancreatic Cancer

### What a Moderate Score (B) Means

- Some evidence dimensions are strong, but others have gaps
- The target shows promise but needs additional validation
- **Action:** Identify and fill the specific evidence gaps shown in the report
- **Example:** CLDN18 in Gastric Cancer (emerging ADC target, limited drug history)

### What a Low Score (C/D/E) Means

- Limited or conflicting evidence across multiple dimensions
- May be a tumor suppressor, common essential gene, or understudied target
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
| **Scenario** | Assessment context that determines dimension weights | `research`, `drug_development`, `adc`, `small_molecule`, `general` |
| **Modality** | Drug modality of interest (optional) | `small_molecule`, `antibody`, `adc`, `protac`, `rna` |

### Output

1. **Summary cards** — Gene info, total score, grade, scenario
2. **One-line recommendation** — Actionable guidance based on score
3. **Radar chart** — Visual comparison of all 8 dimensions
4. **Score table** — Per-dimension scores with percentages
5. **Strengths / Risks / Gaps** — Three-column evidence summary
6. **Downloadable reports** — Markdown (.md), HTML (.html), Excel (.xlsx)

---

## CLI Usage

The CLI tool (`run.py`) runs a complete target assessment from the command line and saves the report files locally.

### Basic Syntax

```bash
python3.8 run.py --gene <GENE> --disease <DISEASE> [OPTIONS]
```

### Arguments

| Argument | Short | Required | Description | Default |
|----------|-------|----------|-------------|---------|
| `--gene` | `-g` | Yes | HGNC gene symbol or common alias | — |
| `--disease` | `-d` | Yes | Disease or cancer type name | — |
| `--scenario` | `-s` | No | Assessment scenario | `general` |
| `--modality` | `-m` | No | Drug modality of interest | `any` |
| `--output-dir` | `-o` | No | Custom output root directory | `outputs/` |
| `--weights` | `-w` | No | Custom dimension weights (JSON file or string) | scenario defaults |
| `--quiet` | `-q` | No | Minimal output (scripting mode) | off |

### Scenario Options

| Value | Label | Use Case |
|-------|-------|----------|
| `general` | General Assessment | Default, balanced weights |
| `research` | Research Grant / SCI | Emphasizes literature & mechanism |
| `drug_development` | Drug Development | Emphasizes safety & modality fit |
| `adc` | ADC / Antibody Target | Emphasizes expression & tumor-normal differential |
| `small_molecule` | Small Molecule Target | Emphasizes druggability & active compounds |

### Modality Options

`any`, `small_molecule`, `antibody`, `adc`, `protac`, `rna`

### Output Files

Each run generates three files in the output directory:

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

### Examples

```bash
# Quick evaluation with minimal typing
python3.8 run.py -g EGFR -d NSCLC

# Evaluate an ADC target with the ADC-specific scenario
python3.8 run.py --gene CLDN18 --disease "Gastric Cancer" --scenario adc

# Save results to a custom directory
python3.8 run.py -g BRCA1 -d "Ovarian Cancer" -s research -o ./my_results

# Custom dimension weights via JSON string
python3.8 run.py -g KRAS -d NSCLC -w '{"disease_relevance": 0.25, "dependency": 0.20}'

# Custom weights via JSON file
python3.8 run.py -g EGFR -d NSCLC -w ./my_weights.json

# Scripting mode — quiet output, just the file paths
python3.8 run.py -g KRAS -d "Pancreatic Cancer" -q
```

### Terminal Output

The CLI prints a summary to stdout including:
- Gene info (symbol, full name, Ensembl ID)
- Total score and grade
- One-line recommendation
- Target archetype (mutation-driven / expression-driven / dependency-driven / drug-validated / balanced)
- Per-dimension score bars (text-based)

### Using in Shell Scripts

```bash
#!/bin/bash
# Batch evaluate multiple targets
for gene in EGFR ERBB2 CLDN18 KRAS BRCA1; do
    python3.8 run.py -g "$gene" -d "NSCLC" -q
    echo "---"
done
```

---

## Project Architecture

```
target_assessment/
├── app.py                         # Streamlit web application
├── run.py                         # CLI tool (batch/scripting)
├── config.py                      # Weights, thresholds, API endpoints, gene aliases
├── requirements.txt               # Python dependencies
├── project.md                     # Full project plan
│
├── modules/                       # Core logic
│   ├── gene_resolver.py           # Gene symbol to HGNC (offline DB to mygene.info fallback)
│   ├── data_manager.py            # Central orchestrator (offline-first, API fallback)
│   ├── offline_provider.py        # SQLite-backed evidence provider (all 6 dimensions)
│   ├── scoring_engine.py          # Multi-dimensional scoring & grading
│   ├── report_generator.py        # Markdown / HTML / Excel report generation
│   ├── sample_data.py             # Pre-curated evidence for canonical targets
│   ├── opentargets_client.py      # Open Targets GraphQL client (fallback)
│   ├── chembl_client.py           # ChEMBL REST client (fallback)
│   ├── clinicaltrials_client.py   # ClinicalTrials.gov REST v2 client (fallback)
│   ├── depmap_module.py           # DepMap CRISPR data (local CSV reader)
│   └── tcga_module.py             # TCGA expression & mutation (local CSV reader)
│
├── data/
│   ├── build_offline_db.py        # Full offline DB builder
│   ├── update_offline_db.py       # Incremental DB updater
│   ├── processed/                 # Preprocessed data files
│   │   ├── target_assessment.db   # Offline SQLite database (~1.2 GB)
│   │   ├── depmap_crispr_summary.csv
│   │   ├── tcga_expression_summary.csv
│   │   ├── tcga_mutation_summary.csv
│   │   └── Homo_sapiens.gene_info.gz
│   ├── raw/                       # Raw downloaded data
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
    ├── reports/                   # Generated markdown & HTML reports
    └── tables/                    # Generated Excel evidence tables
```

### Data Flow

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
ScoringEngine ─── 8 dimensions x scenario weights ──► Total score + Grade + Archetype
       │
       ▼
ReportGenerator ─── Markdown / HTML / Excel ──► Downloadable reports
```

---

## Maintenance Guide

### Updating the Offline Database

See [Offline Database](#offline-database) above for build and update commands.

Typical workflow:

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

### Adding a New Disease Mapping

Edit `EFO_DISEASE_MAP` and `DISEASE_CATEGORIES` in `config.py`:

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

3. Replace the CSV file
4. Run: `python3.8 data/update_offline_db.py --table depmap_crispr`

### Updating TCGA Data

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
5. Add the corresponding table to `build_offline_db.py` and `offline_provider.py`
6. Add tests in `tests/`

### Tuning Scoring Weights

Edit `SCENARIO_WEIGHTS` in `config.py`. Each weight dictionary must sum to 1.0. Dimension max scores are in `DIMENSION_MAX`. Individual scoring rules are in `ScoringEngine` methods.

### Running Tests

```bash
python3.8 -m pytest tests/ -v
```

Note: Tests use the offline DB when available, so most tests now run without internet. API-dependent tests skip automatically when the DB is present.

---

## FAQ

### Q: Does this tool require API keys?

No. All data sources (Open Targets, ChEMBL, ClinicalTrials.gov, mygene.info) are free and open-access. No registration required.

### Q: Can I run this completely offline?

Yes. Build the offline SQLite database once with `python3.8 data/build_offline_db.py` (requires ~1.5 GB download, ~10–30 minutes), and all subsequent runs use only local data with sub-second queries. No internet needed.

### Q: How do I update the offline database when new data is released?

Use `python3.8 data/update_offline_db.py --table <name>` for single-table updates, or `--full` for a complete rebuild. The script backs up your existing database before making changes. See the [Offline Database](#offline-database) section for details.

### Q: Why do some targets show 0 for certain dimensions?

If the gene is not in DepMap/TCGA local data files or not found in the APIs, that dimension defaults to `"unknown"` and scores 0. This is expected for:
- Very new or poorly annotated genes
- Non-human genes
- Genes not studied in the specified disease context

### Q: How do I interpret "differentiation opportunity = high"?

It means few active clinical trials exist for this target in this disease — you have room to differentiate. But it also means the target is less clinically validated. Balance this with the overall score and your risk tolerance.

### Q: Why does BRCA1 score low despite being clinically important?

BRCA1 is a tumor suppressor — it is **lost** in cancer, not overexpressed. You can't "drug" a missing protein. The scoring model correctly identifies this as poor druggability. In practice, BRCA1 status is used for **patient stratification** (PARP inhibitor sensitivity), not as a direct drug target.

### Q: Can I use this for non-cancer diseases?

Yes. The scoring model is disease-agnostic. However, the current data sources (TCGA, DepMap) are cancer-focused. For non-cancer diseases, you may get sparse results. Add appropriate data sources for your disease area.

### Q: How do I cite this tool?

The tool aggregates data from public databases. Cite the underlying data sources:

- **Open Targets**: Ochoa et al. (2023), *Nucleic Acids Research*
- **ChEMBL**: Mendez et al. (2019), *Nucleic Acids Research*
- **DepMap**: Tsherniak et al. (2017), *Cell*
- **TCGA**: The Cancer Genome Atlas Research Network
- **ClinicalTrials.gov**: U.S. National Library of Medicine
- **NCBI Gene**: Brown et al. (2015), *Nucleic Acids Research*
