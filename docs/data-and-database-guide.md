# Target Assessment Tool — Data & Database Guide

## Table of Contents

- [1. Data Architecture Overview](#1-data-architecture-overview)
- [2. Offline SQLite Database](#2-offline-sqlite-database)
  - [2.1 Schema](#21-schema)
  - [2.2 Building from Scratch](#22-building-from-scratch)
  - [2.3 Incremental Updates](#23-incremental-updates)
  - [2.4 Build/Update Reference](#24-buildupdate-reference)
- [3. Data Sources — Upstream Preparation](#3-data-sources--upstream-preparation)
  - [3.1 NCBI Gene Info](#31-ncbi-gene-info)
  - [3.2 DepMap CRISPR Data](#32-depmap-crispr-data)
  - [3.3 TCGA Expression Data](#33-tcga-expression-data)
  - [3.4 TCGA Mutation Data](#34-tcga-mutation-data)
  - [3.5 Open Targets Platform](#35-open-targets-platform)
  - [3.6 ChEMBL Drug Data](#36-chembl-drug-data)
- [4. Disease/Cancer Type Configuration](#4-diseasecancer-type-configuration)
  - [4.1 EFO_DISEASE_MAP](#41-efo_disease_map)
  - [4.2 DISEASE_CATEGORIES + CATEGORY_ALIASES](#42-disease_categories--category_aliases)
  - [4.3 Disease Resolution Logic](#43-disease-resolution-logic)
- [5. Gene Resolution](#5-gene-resolution)
- [6. Evidence Collection & Inference](#6-evidence-collection--inference)
- [7. API Fallback Path](#7-api-fallback-path)
- [8. Sample Data (Pre-Curated Evidence)](#8-sample-data-pre-curated-evidence)
- [9. Maintenance Procedures](#9-maintenance-procedures)
  - [9.1 Updating CRISPR/TGA Data](#91-updating-crisprtcga-data)
  - [9.2 Adding a New Disease](#92-adding-a-new-disease)
  - [9.3 Adding a New Gene Alias](#93-adding-a-new-gene-alias)
  - [9.4 Database Backup & Rollback](#94-database-backup--rollback)
  - [9.5 Scrubbing the API Cache](#95-scrubbing-the-api-cache)
- [10. Troubleshooting](#10-troubleshooting)

---

## 1. Data Architecture Overview

```
                       ┌─────────────────────────┐
                       │   User Input             │
                       │   gene + disease         │
                       └───────────┬─────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    ▼                    │
              │           GeneResolver                  │
              │   offline DB (genes) ──► mygene.info     │
              │                    │                    │
              │                    ▼                    │
              │           DataManager                   │
              │                    │                    │
              │     ┌──────────────┼──────────────┐     │
              │     │  OfflineProvider (SQLite)    │     │
              │     │  • genes         • depmap    │     │
              │     │  • opentargets   • tcga_expr  │     │
              │     │  • chembl_drugs  • tcga_mut  │     │
              │     │                              │     │
              │     │  ✓ <1s response              │     │
              │     │  ✓ zero network calls         │     │
              │     └──────────────┬──────────────┘     │
              │                    │                    │
              │         ┌─────────┴──────────┐         │
              │         │  IF DB unavailable: │         │
              │         │  Live API fallback  │         │
              │         │  (5-15s, network)   │         │
              │         └─────────┬──────────┘         │
              │                   │                    │
              │                   ▼                    │
              │          ScoringEngine                 │
              │   8 dimensions × scenario weights      │
              │        × archetype modifiers           │
              │                   │                    │
              │                   ▼                    │
              │          ReportGenerator               │
              │     Markdown / HTML / Excel            │
              └────────────────────────────────────────┘
```

**Core design principle**: Offline-first. The SQLite database (`data/processed/target_assessment.db`) is the single source of truth for all evidence data. Live APIs exist only as a fallback for when the database hasn't been built yet, or to enrich sparse results.

The offline database is a single ~1.1 GB file containing 6 tables that cover all 8 scoring dimensions. Once built, the tool can run entirely offline with sub-second query latency.

---

## 2. Offline SQLite Database

**File**: `data/processed/target_assessment.db` (~1.1 GB when fully built)

### 2.1 Schema

#### `genes` — Gene annotations (~194,000 rows)

| Column | Type | Description |
|--------|------|-------------|
| `gene_symbol` | TEXT PK | Official HGNC symbol (uppercase) |
| `ensembl_id` | TEXT | Ensembl gene ID (ENSG...) |
| `entrez_id` | TEXT | NCBI Entrez Gene ID |
| `full_name` | TEXT | Full gene name |
| `synonyms` | TEXT | JSON array of known synonyms |
| `aliases_lower` | TEXT | Pipe-delimited lowercase aliases for fast search |

Source: NCBI Gene FTP (`Homo_sapiens.gene_info.gz`, ~25 MB download)

#### `opentargets` — Target-disease associations (~4.5 million rows)

| Column | Type | Description |
|--------|------|-------------|
| `ensembl_id` | TEXT | Ensembl gene ID |
| `efo_id` | TEXT | Experimental Factor Ontology disease ID |
| `overall_score` | REAL | Overall association score (0–1) |
| `genetic_association` | REAL | Genetic evidence score |
| `somatic_mutation` | REAL | Somatic mutation evidence score |
| `known_drug` | REAL | Known drug evidence score |
| `rna_expression` | REAL | RNA expression evidence score |
| `literature` | REAL | Literature evidence score |
| `affected_pathway` | REAL | Affected pathway evidence score |
| `evidence_count` | INTEGER | Total evidence items backing this association |

Source: Open Targets Platform (Parquet, ~500 MB download). Primary key: `(ensembl_id, efo_id)`.

#### `chembl_drugs` — Drug counts per target (~5,900 rows)

| Column | Type | Description |
|--------|------|-------------|
| `gene_symbol` | TEXT PK | HGNC gene symbol |
| `chembl_target_id` | TEXT | ChEMBL target ID |
| `approved_drugs` | INTEGER | Number of approved (max_phase ≥ 4) drugs |
| `clinical_candidates` | INTEGER | Number of clinical-stage (max_phase 2–3) drugs |
| `active_compounds` | INTEGER | Number of active compounds (max_phase ≤ 1) |
| `modality_fit` | TEXT | "strong" / "moderate" / "weak" / "unknown" |

Source: ChEMBL SQLite database (~800 MB download). Modality fit is inferred: ≥3 approved+clinical → strong, ≥1 approved+clinical or ≥5 active → moderate, >0 active → weak.

#### `depmap_crispr` — CRISPR dependency scores (~1.4 million rows)

| Column | Type | Description |
|--------|------|-------------|
| `gene` | TEXT | HGNC gene symbol |
| `primary_disease` | TEXT | DepMap disease/cancer type label |
| `mean_chronos_score` | REAL | Mean Chronos gene effect score (more negative = stronger dependency) |
| `num_cell_lines` | INTEGER | Number of cell lines tested |
| `pan_cancer_mean_score` | REAL | Pan-cancer mean Chronos score |
| `pan_cancer_percentile` | REAL | Pan-cancer percentile rank (0 = strongest dependency) |
| `selectivity_category` | TEXT | "selective" / "moderate_selective" / "non_selective" |

Source: Preprocessed CSV (`data/processed/depmap_crispr_summary.csv`). Primary key: `(gene, primary_disease)`.

Dependency classification:
- Chronos < −0.5 → "strong"
- Chronos < −0.3 → "moderate"
- Chronos ≥ −0.3 → "weak"

Common essential genes (pan_cancer_mean < −0.8 AND percentile < 5) get their dependency score capped at 30% of maximum.

#### `tcga_expression` — Tumor expression profiles (~1.8 million rows)

| Column | Type | Description |
|--------|------|-------------|
| `gene` | TEXT | HGNC gene symbol |
| `cancer_type` | TEXT | TCGA cancer type label |
| `median_tpm_tumor` | REAL | Median TPM in tumor samples |
| `median_tpm_normal` | REAL | Median TPM in normal samples |
| `log2fc_tumor_normal` | REAL | log2 fold change (tumor / normal) |
| `overexpression_category` | TEXT | "high" / "moderate" / "low" / "unknown" |
| `tumor_normal_diff_category` | TEXT | "significant" (log2FC > 2) / "moderate" (log2FC > 1) / "none" / "unknown" |
| `tissue_specificity` | TEXT | "high" / "moderate" / "low" / "unknown" |

Source: Preprocessed CSV (`data/processed/tcga_expression_summary.csv`). Primary key: `(gene, cancer_type)`.

#### `tcga_mutation` — Mutation & CNV frequencies (~1.5 million rows)

| Column | Type | Description |
|--------|------|-------------|
| `gene` | TEXT | HGNC gene symbol |
| `cancer_type` | TEXT | TCGA cancer type label |
| `mutation_freq` | REAL | Point mutation frequency (0–1) |
| `cnv_amp_freq` | REAL | Copy number amplification frequency (0–1) |
| `cnv_del_freq` | REAL | Copy number deletion frequency (0–1) |
| `total_alteration_freq` | REAL | Total alteration frequency (mutation + CNV) |
| `prognostic_associated` | INTEGER | 1 if prognostically associated, 0 otherwise |

Source: Preprocessed CSV (`data/processed/tcga_mutation_summary.csv`). Primary key: `(gene, cancer_type)`.

### 2.2 Building from Scratch

**Prerequisites**: Python 3.8+, ~1.5 GB free disk (for downloads), ~10-30 minutes

```bash
# Full build — downloads all upstream data and imports everything
python3.8 data/build_offline_db.py

# Build only using local CSV files (DepMap + TCGA + NCBI Gene)
# Skips Open Targets and ChEMBL downloads
python3.8 data/build_offline_db.py --only-local

# Build only the genes table
python3.8 data/build_offline_db.py --only-genes

# Build using previously downloaded cache files (no network needed)
python3.8 data/build_offline_db.py --skip-download

# Overwrite an existing database
python3.8 data/build_offline_db.py --force
```

**What each stage does**:

| Stage | What happens | Network | Time | Output |
|-------|-------------|---------|------|--------|
| 1. NCBI Genes | Downloads `Homo_sapiens.gene_info.gz`, parses Ensembl IDs and aliases | Yes (~25 MB) | ~1 min | `genes` table |
| 2. DepMap | Reads `depmap_crispr_summary.csv` from `data/processed/` | No | ~30 sec | `depmap_crispr` table |
| 3a. TCGA Expression | Reads `tcga_expression_summary.csv` from `data/processed/` | No | ~30 sec | `tcga_expression` table |
| 3b. TCGA Mutation | Reads `tcga_mutation_summary.csv` from `data/processed/` | No | ~30 sec | `tcga_mutation` table |
| 4. Open Targets | Downloads Parquet part files (~500 MB) and imports | Yes (~500 MB) | 5–15 min | `opentargets` table |
| 5. ChEMBL | Downloads ChEMBL SQLite tarball (~800 MB), extracts, queries | Yes (~800 MB) | 5–10 min | `chembl_drugs` table |
| 6. Indexes | Creates indexes on frequently-queried columns | No | ~1 min | — |

### 2.3 Incremental Updates

The `update_offline_db.py` script updates individual tables without requiring a full rebuild.

```bash
# Update a single table
python3.8 data/update_offline_db.py --table depmap_crispr
python3.8 data/update_offline_db.py --table tcga           # Both TCGA tables
python3.8 data/update_offline_db.py --table genes
python3.8 data/update_offline_db.py --table opentargets
python3.8 data/update_offline_db.py --table chembl

# Dry-run — check what would be updated without changing anything
python3.8 data/update_offline_db.py --table depmap_crispr --dry-run

# Full rebuild (all tables, with backup)
python3.8 data/update_offline_db.py --full
python3.8 data/update_offline_db.py --full --yes   # Skip confirmation prompt
```

**Safety guarantees**:
- Creates a timestamped backup before any modification
- Validates each updated table (row count, schema)
- Automatically rolls back to backup on failure
- Rebuilds indexes after each update

### 2.4 Build/Update Reference

| Flag | `build_offline_db.py` | `update_offline_db.py` |
|------|----------------------|------------------------|
| `--force` | Overwrite existing DB | — |
| `--skip-download` | Skip OT + ChEMBL download | — |
| `--only-local` | Import CSVs only | — |
| `--only-genes` | Build genes table only | — |
| `--table <name>` | — | Update specific table |
| `--full` | — | Rebuild all tables |
| `--dry-run` | — | Preview without modifying |
| `--yes` / `-y` | — | Skip confirmation for `--full` |

---

## 3. Data Sources — Upstream Preparation

### 3.1 NCBI Gene Info

**What it provides**: Gene symbols, full names, Ensembl IDs, synonyms

**Source URL**: `https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz`

**How it's processed** (in `import_genes()`):
1. Download the gzipped file
2. Parse tab-delimited rows, skipping comment lines
3. Extract: symbol, GeneID, Synonyms (pipe-delimited), dbXrefs (parse out Ensembl ID), full name
4. Build an `aliases_lower` field for fast substring alias lookup: `|symbol|synonym1|synonym2|`

**How to update**:
```bash
python3.8 data/update_offline_db.py --table genes
```
The script re-downloads `Homo_sapiens.gene_info.gz` from NCBI and re-imports. NCBI updates quarterly.

### 3.2 DepMap CRISPR Data

**What it provides**: CRISPR knockout dependency scores per gene, per cancer type

**Expected CSV schema** (`data/processed/depmap_crispr_summary.csv`):
```csv
gene,primary_disease,mean_chronos_score,num_cell_lines,pan_cancer_mean_score,pan_cancer_percentile,selectivity_category
EGFR,Non-Small Cell Lung Cancer,-0.42,85,-0.31,12.5,selective
DRD2,Brain Cancer,0.083,20,-0.05,91.2,non_selective
```

| Column | Required | Type | Notes |
|--------|----------|------|-------|
| `gene` | Yes | string | HGNC symbol, will be uppercased |
| `primary_disease` | Yes | string | Must match entries in `DISEASE_CATEGORIES` or DepMap disease names |
| `mean_chronos_score` | Yes | float | Chronos gene effect score |
| `num_cell_lines` | Optional | int | Defaults to 1 if missing |
| `pan_cancer_mean_score` | Yes | float | Mean across all cancer types |
| `pan_cancer_percentile` | Yes | float | 0–100, lower = stronger dependency |
| `selectivity_category` | Yes | string | "selective" / "moderate_selective" / "non_selective" |

**Preparation workflow**:
1. Go to https://depmap.org/portal/download/
2. Download the latest CRISPR gene effect file (e.g., `CRISPRGeneEffect.csv`)
3. Process it to compute per-disease mean Chronos scores, pan-cancer percentiles, and selectivity categories
4. Save as `data/processed/depmap_crispr_summary.csv`
5. Import: `python3.8 data/update_offline_db.py --table depmap_crispr`

**Recommended update cadence**: Quarterly (each DepMap release, typically 24Q2, 24Q4, etc.)

### 3.3 TCGA Expression Data

**What it provides**: Tumor expression levels (TPM, log2FC) per gene, per cancer type

**Expected CSV schema** (`data/processed/tcga_expression_summary.csv`):
```csv
gene,cancer_type,median_tpm_tumor,median_tpm_normal,log2fc_tumor_normal,overexpression_category,tumor_normal_diff_category,tissue_specificity
EGFR,Non-Small Cell Lung Cancer,45.2,12.1,1.91,high,significant,high
DRD2,Brain Cancer,2.1,17.8,-3.07,low,significant,low
```

| Column | Required | Type | Notes |
|--------|----------|------|-------|
| `gene` | Yes | string | HGNC symbol |
| `cancer_type` | Yes | string | Must match TCGA/DISEASE_CATEGORIES labels |
| `median_tpm_tumor` | Yes | float | Median TPM in tumor |
| `median_tpm_normal` | Yes | float | Median TPM in matched normal |
| `log2fc_tumor_normal` | Yes | float | log2 fold change |
| `overexpression_category` | Yes | string | "high" / "moderate" / "low" / "unknown" |
| `tumor_normal_diff_category` | Yes | string | "significant" / "moderate" / "none" / "unknown" |
| `tissue_specificity` | Yes | string | "high" / "moderate" / "low" / "unknown" |

**Preparation workflow**:
1. Download expression data from cBioPortal, TCGA GDC, or UCSC Xena
2. For each `(gene, cancer_type)` pair, compute:
   - Median TPM (tumor and normal)
   - log2FC (tumor / normal)
   - Classify overexpression: TPM_tumor > 50 TPM and log2FC > 1 → "high", TPM_tumor > 10 or log2FC > 0.5 → "moderate", else "low"
   - Classify tumor-normal diff: log2FC > 2 → "significant", log2FC > 1 → "moderate", else "none"
   - Classify tissue specificity based on GTEx or HPA data
3. Save as `data/processed/tcga_expression_summary.csv`
4. Import: `python3.8 data/update_offline_db.py --table tcga_expression`

### 3.4 TCGA Mutation Data

**What it provides**: Mutation and CNV frequencies per gene, per cancer type

**Expected CSV schema** (`data/processed/tcga_mutation_summary.csv`):
```csv
gene,cancer_type,mutation_freq,cnv_amp_freq,cnv_del_freq,total_alteration_freq,prognostic_associated
EGFR,Non-Small Cell Lung Cancer,0.15,0.08,0.02,0.25,1
DRD2,Brain Cancer,0.01,0.03,0.005,0.045,0
```

| Column | Required | Type | Notes |
|--------|----------|------|-------|
| `gene` | Yes | string | HGNC symbol |
| `cancer_type` | Yes | string | Must match TCGA labels |
| `mutation_freq` | Yes | float | Point mutation frequency (0–1) |
| `cnv_amp_freq` | Yes | float | Amplification frequency (0–1) |
| `cnv_del_freq` | Yes | float | Deletion frequency (0–1) |
| `total_alteration_freq` | Yes | float | Combined alteration freq |
| `prognostic_associated` | Yes | int | 1 if prognostic, 0 otherwise |

**Preparation workflow**:
1. Download mutation data from cBioPortal or TCGA GDC
2. For each `(gene, cancer_type)` pair, compute frequencies
3. Save as `data/processed/tcga_mutation_summary.csv`
4. Import: `python3.8 data/update_offline_db.py --table tcga_mutation`

### 3.5 Open Targets Platform

**What it provides**: Target-disease association scores with evidence breakdown by datatype

**Source URL**: `https://ftp.ebi.ac.uk/pub/databases/opentargets/platform/latest/output/association_overall_direct/`

**How it's processed** (in `import_opentargets()`):
1. Lists all `part-*.parquet` files from the FTP directory
2. Downloads missing parts (~500 MB total)
3. Combines all parts into a single DataFrame
4. Filters to human targets only (`targetId` starts with "ENSG")
5. Maps columns: `targetId` → `ensembl_id`, `diseaseId` → `efo_id`, `score` → `overall_score`
6. Extracts datatype sub-scores: genetic_association, somatic_mutation, known_drug, rna_expression, literature, affected_pathway
7. Deduplicates on `(ensembl_id, efo_id)`, keeping the highest score
8. Inserts into `opentargets` table

**How to update**:
```bash
python3.8 data/update_offline_db.py --table opentargets
```

**Recommended update cadence**: Monthly (Open Targets releases monthly; significant changes quarterly)

### 3.6 ChEMBL Drug Data

**What it provides**: Drug counts (approved, clinical, active) per target gene

**Source URL**: `https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/latest/`

**How it's processed** (in `import_chembl()`):
1. Downloads the ChEMBL SQLite tarball (`chembl_XX_sqlite.tar.gz`, ~800 MB)
2. Extracts and opens the ChEMBL SQLite database
3. Runs a query joining `target_dictionary` → `target_components` → `component_synonyms` → `drug_mechanism` → `molecule_dictionary`
4. Groups by gene symbol, counting drugs at each phase level
5. Infers modality fit from drug counts
6. Inserts into `chembl_drugs` table

**How to update**:
```bash
# Update ChEMBL version via environment variable if needed
CHEMBL_VERSION=38 python3.8 data/update_offline_db.py --table chembl
```

**Recommended update cadence**: Quarterly (new ChEMBL versions)

---

## 4. Disease/Cancer Type Configuration

All disease configuration lives in `config.py`. There are three layers that work together to map user-input disease names to database disease labels.

### 4.1 EFO_DISEASE_MAP

Maps user-facing disease names to EFO (Experimental Factor Ontology) IDs for the Open Targets API.

```python
EFO_DISEASE_MAP = {
    "nsclc": "EFO_0000621",
    "breast cancer": "EFO_0000305",
    "gastric cancer": "EFO_0000503",
    # ... ~18 entries ...
}
```

**How it's used**: When querying the `opentargets` table, the system looks up the EFO ID for the user's disease. Substring matching is used (e.g., "Non-Small Cell Lung Cancer" matches "nsclc" → EFO_0000621).

**How to add a new disease mapping**:
```python
EFO_DISEASE_MAP = {
    # ... existing entries ...
    "schizophrenia": "EFO_0000692",       # Add here
    "parkinson disease": "EFO_0002508",   # Add here
}
```

Find EFO IDs at: https://www.ebi.ac.uk/ols/ontologies/efo

### 4.2 DISEASE_CATEGORIES + CATEGORY_ALIASES

This two-layer mapping system matches user disease names to the specific disease labels used inside DepMap and TCGA data tables.

**`DISEASE_CATEGORIES`**: Maps internal category keys to lists of DepMap/TCGA disease names:
```python
DISEASE_CATEGORIES = {
    "lung_cancer": [
        "Non-Small Cell Lung Cancer",
        "Lung Neuroendocrine Tumor",
    ],
    "breast_cancer": [
        "Invasive Breast Carcinoma",
        "Breast Ductal Carcinoma In Situ",
        "Breast Neoplasm, NOS",
    ],
    # ... ~20 categories ...
}
```

**`CATEGORY_ALIASES`**: Maps user-friendly disease name strings to category keys:
```python
CATEGORY_ALIASES = {
    "lung cancer": "lung_cancer",
    "nsclc": "lung_cancer",
    "non-small cell lung cancer": "lung_cancer",
    "breast cancer": "breast_cancer",
    # ... ~80+ aliases ...
}
```

### 4.3 Disease Resolution Logic

The `resolve_disease_categories()` function in `config.py` implements the matching algorithm:

```
User input → lowercase → exact match in CATEGORY_ALIASES
                        → longest substring match in CATEGORY_ALIASES
                        → return list of DepMap/TCGA disease names from DISEASE_CATEGORIES
                        → empty list if no match (caller falls back to legacy string matching)
```

This list is then used by `_find_disease_row()` in `offline_provider.py` to query DepMap and TCGA tables with an `IN (...)` clause, picking the best row (e.g., strongest dependency for DepMap, highest TPM for TCGA expression).

---

## 5. Gene Resolution

The `GeneResolver` (`modules/gene_resolver.py`) normalizes user-input gene symbols through a multi-tier fallback:

```
User input (e.g., "HER2", "HER-2", "ERBB2")
    │
    ▼
1. Local alias cache (GENE_ALIAS_CACHE in config.py)
   │  Maps common aliases to official symbols
   │  HER2 → ERBB2, PDL1 → CD274, etc.
   │
   ├─ Found → Return cached symbol
   │
   ▼
2. Offline SQLite DB (genes table)
   │  Exact match on gene_symbol, then LIKE search on aliases_lower
   │  Returns: (official_symbol, ensembl_id, full_name, synonyms)
   │  Status: "resolved_offline"
   │
   ├─ Found → Return with Ensembl ID
   │
   ▼
3. mygene.info API (network fallback)
   │  GET /v3/query?q=HER2&species=human
   │  Returns standardized symbol + Ensembl ID
   │  Status: "resolved_api" or "resolved_api_and_cache"
   │
   ├─ Found → Return with API data
   │
   ▼
4. Local cache only (no Ensembl ID)
   │  Status: "resolved_local"
   │
   ▼
5. Return as-is, uppercase
      Status: "unresolved"
```

**Adding new gene aliases**: Edit `GENE_ALIAS_CACHE` in `config.py`:
```python
GENE_ALIAS_CACHE = {
    # ... existing ...
    "NEW_ALIAS": "OFFICIAL_SYMBOL",
}
```

---

## 6. Evidence Collection & Inference

The `DataManager` (`modules/data_manager.py`) orchestrates evidence collection:

```
DataManager.collect_evidence(gene, disease, scenario, ensembl_id)
    │
    ├─ Check: Is offline DB available? (cached, checked once per session)
    │
    ├─ YES → _build_from_offline()       <1s, zero network
    │   │
    │   ├─ resolve_gene()         → official symbol + Ensembl ID
    │   ├─ resolve_efo_id()       → EFO ID for disease
    │   ├─ query_ot()             → Open Targets association data
    │   ├─ query_chembl()         → ChEMBL drug counts
    │   ├─ query_clinical_competition() → derived from ChEMBL + OT
    │   ├─ query_depmap()         → DepMap CRISPR dependency
    │   ├─ query_tcga_expr()      → TCGA expression
    │   ├─ query_tcga_mut()       → TCGA mutation
    │   │
    │   └─ Post-processing (drug-based inference boosts):
    │       • mechanism_strength: approved drugs → "well_established"
    │       • pathway_count: approved + clinical each count as 1 pathway
    │       • opentargets_association: True if approved_drugs > 0
    │       • literature_level: "high" if ≥5 approved, "moderate" if ≥1
    │       • active_clinical_trials: estimated from approved count if 0
    │
    └─ NO → _build_from_live_apis()   5-15s, requires network
        │
        ├─ Open Targets GraphQL
        ├─ ChEMBL REST
        ├─ ClinicalTrials.gov REST
        ├─ DepMap (local CSV)
        └─ TCGA (local CSV)
```

### Evidence priority for each dimension

| Dimension | Primary data source | Fallback inference |
|-----------|-------------------|--------------------|
| disease_relevance | TCGA expression + mutation + OT | Drug data (approved drugs → OT association True) |
| expression | TCGA expression | OT `rna_expression` score |
| dependency | DepMap CRISPR | — |
| mechanism | ChEMBL drug data → OT pathway scores | Approved drugs → "well_established" |
| druggability | ChEMBL | — |
| safety | TCGA expression (tumor-normal diff) + DepMap (common essential) | — |
| clinical_competition | ChEMBL (approved count) + OT (known_drug score) | Drug count estimate |
| scenario_fit | Derived from other evidence dimensions | — |

---

## 7. API Fallback Path

When the offline database is unavailable, the system falls back to live API queries. This path is **slower** (5-15 seconds) and **requires internet access**.

### API Endpoints (configured in `config.py`)

| API | Endpoint | What it provides | Rate limit |
|-----|----------|-----------------|------------|
| **mygene.info** | `GET /v3/query` | Gene symbol resolution, Ensembl ID | No strict limit |
| **Open Targets Platform** | GraphQL `POST /api/v4/graphql` | Target-disease association scores | No strict limit |
| **ChEMBL** | `GET /chembl/api/data` | Drug counts by target | ~1 request/s |
| **ClinicalTrials.gov** | REST API v2 | Active clinical trial counts | ~50 requests/min |

### API Client Modules

| Module | Purpose |
|--------|---------|
| `modules/opentargets_client.py` | Open Targets GraphQL queries |
| `modules/chembl_client.py` | ChEMBL REST queries |
| `modules/clinicaltrials_client.py` | ClinicalTrials.gov REST v2 queries |
| `modules/depmap_module.py` | DepMap local CSV reader (no API needed) |
| `modules/tcga_module.py` | TCGA local CSV reader (no API needed) |

### API Response Caching

API responses are cached in `data/cache/` as JSON files keyed by `gene + disease`. To clear the cache:
```bash
rm data/cache/*.json
```

Clear the cache after updating local data or if you suspect stale results.

---

## 8. Sample Data (Pre-Curated Evidence)

File: `modules/sample_data.py`

Pre-curated evidence for 6 canonical targets used as enrichment when real data is sparse:

| Gene | Disease | Archetype |
|------|---------|-----------|
| EGFR | NSCLC | mutation_driven |
| ERBB2 | Breast Cancer | expression_driven |
| CLDN18 | Gastric Cancer | expression_driven |
| MUC1 | Pan-cancer | expression_driven |
| BRCA1 | Ovarian Cancer | mutation_driven (tumor suppressor) |
| KRAS | Pancreatic Cancer | mutation_driven |

Each sample entry contains complete evidence for all 8 dimensions plus target overview and data source provenance. The sample data is only used as enrichment — it supplements real data when specific fields are sparse for well-known targets. It does NOT replace real data.

To add a new sample entry:
```python
SAMPLE_EVIDENCE[("GENE", "Disease")] = {
    "target_overview": { ... },
    "disease_relevance": { ... },
    "expression": { ... },
    # ... all 8 dimensions + target_overview + data_sources
}
```

---

## 9. Maintenance Procedures

### 9.1 Updating CRISPR/TCGA Data

This is the most common maintenance task. The DepMap and TCGA preprocessed CSV files should be updated when new versions are released.

```bash
# 1. Replace the CSV files with new versions
#    data/processed/depmap_crispr_summary.csv
#    data/processed/tcga_expression_summary.csv
#    data/processed/tcga_mutation_summary.csv

# 2. Update the database
python3.8 data/update_offline_db.py --table depmap_crispr
python3.8 data/update_offline_db.py --table tcga

# 3. Clear API cache to prevent stale cached results
rm data/cache/*.json
```

### 9.2 Adding a New Disease

**Step 1**: Add EFO ID mapping (for Open Targets):

In `config.py`, add to `EFO_DISEASE_MAP`:
```python
EFO_DISEASE_MAP = {
    # ... existing ...
    "new disease name": "EFO_XXXXXXXXX",
}
```

Find the EFO ID at https://www.ebi.ac.uk/ols/ontologies/efo

**Step 2**: Add disease category (for DepMap/TCGA data matching):

In `config.py`, add to `CATEGORY_ALIASES`:
```python
CATEGORY_ALIASES = {
    # ... existing ...
    "new disease name": "new_disease_key",
}
```

If the disease has corresponding DepMap/TCGA disease labels, add to `DISEASE_CATEGORIES`:
```python
DISEASE_CATEGORIES = {
    # ... existing ...
    "new_disease_key": [
        "DepMap disease label 1",
        "DepMap disease label 2",
    ],
}
```

**Step 3** (if applicable): Add sample data for a canonical target in this disease in `modules/sample_data.py`.

### 9.3 Adding a New Gene Alias

In `config.py`, add to `GENE_ALIAS_CACHE`:
```python
GENE_ALIAS_CACHE = {
    # ... existing ...
    "NEW_ALIAS": "OFFICIAL_SYMBOL",
}
```

The offline DB's `genes` table also handles aliases automatically — the alias cache is just a faster first-pass lookup.

### 9.4 Database Backup & Rollback

The update script automatically creates backups with timestamps:
```
data/processed/target_assessment_backup_20260803_140000.db
```

**Manual backup**:
```bash
cp data/processed/target_assessment.db data/processed/target_assessment_backup_$(date +%Y%m%d).db
```

**Rollback from backup**:
```bash
cp data/processed/target_assessment_backup_20260803_140000.db data/processed/target_assessment.db
```

### 9.5 Scrubbing the API Cache

The API response cache is in `data/cache/` as JSON files. Clear it when:
- You've updated the offline database and suspect stale cached responses
- You've changed API configuration
- You've updated local data files

```bash
rm data/cache/*.json
```

---

## 10. Troubleshooting

### "Could not resolve EFO ID for disease: X"

The disease name isn't in `EFO_DISEASE_MAP` or `CATEGORY_ALIASES`. The system will still work — it falls back to substring matching against DepMap/TCGA disease labels. But OT data won't be available for this disease.

**Fix**: Add the disease to `EFO_DISEASE_MAP` and/or `CATEGORY_ALIASES` in `config.py`. See [§9.2](#92-adding-a-new-disease).

### "Database not found" when running update

The offline database hasn't been built yet.

**Fix**: `python3.8 data/build_offline_db.py`

### Mechanism scores = 0 for well-known drug targets

If a target has approved drugs but mechanism shows 0, check:
1. Is the offline DB available? `ls -lh data/processed/target_assessment.db`
2. Is the target in the `chembl_drugs` table? `sqlite3 data/processed/target_assessment.db "SELECT * FROM chembl_drugs WHERE gene_symbol='DRD2'"`
3. If the target IS in chembl_drugs but mechanism is still 0, the drug-based inference fix (approved_drugs → mechanism_strength = "well_established") may not be active. Verify the fix from `data_manager.py`.

### Some genes resolve slowly

The gene resolver tries offline DB first (fast), then falls back to mygene.info API (network latency). If the offline DB is available but gene resolution is still slow:
1. Check that the `genes` table has indexes: `sqlite3 data/processed/target_assessment.db ".indices genes"`
2. If indexes are missing, rebuild: `python3.8 data/update_offline_db.py --table genes`

### Score seems wrong for a specific target

1. Check what archetype the target was classified as
2. Check each dimension's raw evidence: `python3.8 -c "from assessment_core import run_assessment; import json; r = run_assessment('GENE', 'DISEASE'); print(json.dumps(r['evidence'], indent=2, default=str))"`
3. Check if the target has approved drugs but mechanism/disease_relevance isn't benefiting from drug-based inference
4. Verify the disease name maps correctly to a disease category
