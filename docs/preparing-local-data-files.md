# Preparing Local Data Files — Step-by-Step Guide

This guide explains how to prepare the three local CSV files required by the Target Assessment Tool's offline database. Each section covers: what the file is, its exact schema, an example row, and the full procedure to create it from public upstream data.

---

## Table of Contents

- [Overview](#overview)
- [File 1: DepMap CRISPR Summary](#file-1-depmap-crispr-summary)
- [File 2: TCGA Expression Summary](#file-2-tcga-expression-summary)
- [File 3: TCGA Mutation Summary](#file-3-tcga-mutation-summary)
- [Verification Checklist](#verification-checklist)

---

## Overview

| File | Source | Rows (approx.) | Size | Key Metric |
|------|--------|---------------|------|------------|
| `depmap_crispr_summary.csv` | DepMap Portal | ~18,000 | ~2 MB | Chronos gene effect score |
| `tcga_expression_summary.csv` | cBioPortal / TCGA GDC | ~20,000 | ~3 MB | Median TPM, log2FC |
| `tcga_mutation_summary.csv` | cBioPortal / TCGA GDC | ~20,000 | ~2 MB | Mutation & CNV frequency |

All three files must be placed in `data/processed/` before running `python3.8 data/build_offline_db.py`.

---

## File 1: DepMap CRISPR Summary

### What it is

The [DepMap (Cancer Dependency Map)](https://depmap.org/) project performs genome-wide CRISPR knockout screens across ~1,000 cancer cell lines. Each gene gets a **Chronos score** — a numerical measure of how essential that gene is for cell survival. More negative = stronger dependency (the cell line dies when that gene is knocked out).

This file aggregates per-cell-line Chronos scores into **per-gene, per-cancer-type summary statistics**, so the scoring engine can answer: *"How strongly does this cancer type depend on this gene?"*

### Schema

```
gene,primary_disease,mean_chronos_score,num_cell_lines,pan_cancer_mean_score,pan_cancer_percentile,selectivity_category
```

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `gene` | string | HGNC gene symbol (uppercase) | `EGFR` |
| `primary_disease` | string | DepMap disease label — must match entries in `config.py` `DISEASE_CATEGORIES` | `Non-Small Cell Lung Cancer` |
| `mean_chronos_score` | float | Mean Chronos score for this (gene, disease) pair across all cell lines of that disease. Range: typically −1.5 (strong dependency) to +0.5 (no effect). | `-0.42` |
| `num_cell_lines` | int | Number of cell lines of this disease type in which the gene was screened | `85` |
| `pan_cancer_mean_score` | float | Mean Chronos score across ALL cancer types (pan-cancer). Used to assess selectivity. | `-0.31` |
| `pan_cancer_percentile` | float | Percentile rank of pan_cancer_mean_score (0 = strongest dependency genome-wide, 100 = no dependency). Lower = more essential. | `12.5` |
| `selectivity_category` | string | `"selective"` (perc < 20), `"moderate_selective"` (20–50), or `"non_selective"` (≥ 50) | `selective` |

### Example rows

```csv
gene,primary_disease,mean_chronos_score,num_cell_lines,pan_cancer_mean_score,pan_cancer_percentile,selectivity_category
EGFR,Non-Small Cell Lung Cancer,-0.42,85,-0.31,12.5,selective
EGFR,Breast Cancer,-0.15,52,-0.31,12.5,non_selective
ERBB2,Breast Cancer,-0.58,52,-0.45,5.2,selective
KRAS,Pancreatic Adenocarcinoma,-0.71,35,-0.38,8.1,selective
KRAS,Non-Small Cell Lung Cancer,-0.55,85,-0.38,8.1,selective
CLDN18,Gastric Cancer,0.12,28,0.05,65.3,non_selective
BRCA1,Ovarian Cancer,-0.33,22,-0.28,15.7,selective
DRD2,Brain Cancer,0.083,20,-0.05,91.2,non_selective
TP53,Non-Small Cell Lung Cancer,-0.08,85,-0.12,55.0,non_selective
PRMT5,Non-Small Cell Lung Cancer,-0.62,85,-0.55,2.3,selective
```

### How to prepare — step by step

**Step 1: Download the raw DepMap data**

Go to https://depmap.org/portal/download/ and download the latest **CRISPR Gene Effect** file. It is typically named `CRISPRGeneEffect.csv` and is ~100 MB.

The file format: rows are genes, columns are cell lines (identified by DepMap ID like `ACH-000001`). Each cell contains a Chronos score.

**Step 2: Download cell line metadata**

From the same page, download `Model.csv` (~5 MB). This maps each cell line ID to metadata including `OncotreeLineage` (the cancer type label).

**Step 3: Compute per-disease summary statistics (Python script)**

```python
import pandas as pd
import numpy as np

# ── Load raw data ──────────────────────────────────────────────────────
gene_effect = pd.read_csv("CRISPRGeneEffect.csv", index_col=0)   # genes × cell lines
model_info  = pd.read_csv("Model.csv")

# ── Map cell line ID → primary disease ─────────────────────────────────
# The Model.csv has columns: ModelID, OncotreeLineage, ...
id_to_disease = dict(zip(model_info["ModelID"], model_info["OncotreeLineage"]))

# ── Compute pan-cancer mean & percentile for each gene ─────────────────
pan_cancer_mean = gene_effect.mean(axis=1)
pan_cancer_pct  = pan_cancer_mean.rank(pct=True) * 100  # 0 = strongest dependency

# ── Build per-(gene, disease) summary ──────────────────────────────────
rows = []
for gene in gene_effect.index:
    row_data = gene_effect.loc[gene]

    # Group cell lines by disease
    for disease, disease_ids in row_data.groupby(
        row_data.index.map(lambda cid: id_to_disease.get(cid, "Unknown"))
    ):
        if pd.isna(disease) or disease == "Unknown":
            continue

        chronos_values = disease_ids.dropna()
        n_lines = len(chronos_values)
        if n_lines < 3:
            continue  # skip diseases with too few cell lines

        mean_chronos = chronos_values.mean()
        pc_mean = pan_cancer_mean[gene]
        pc_pct  = pan_cancer_pct[gene]

        # ── Classify selectivity ────────────────────────────────────
        if pc_pct < 20:
            selectivity = "selective"
        elif pc_pct < 50:
            selectivity = "moderate_selective"
        else:
            selectivity = "non_selective"

        rows.append({
            "gene": gene,
            "primary_disease": disease,
            "mean_chronos_score": round(mean_chronos, 6),
            "num_cell_lines": n_lines,
            "pan_cancer_mean_score": round(pc_mean, 6),
            "pan_cancer_percentile": round(pc_pct, 4),
            "selectivity_category": selectivity,
        })

# ── Save ───────────────────────────────────────────────────────────────
df = pd.DataFrame(rows)
df.to_csv("depmap_crispr_summary.csv", index=False)
print(f"Saved {len(df)} rows covering {df['gene'].nunique()} genes × "
      f"{df['primary_disease'].nunique()} diseases")
```

**Step 4: Place the output file**

```bash
mv depmap_crispr_summary.csv data/processed/
```

**Important note on disease labels**: The `primary_disease` values from DepMap (e.g., `"Non-Small Cell Lung Cancer"`) must match the labels in `config.py`'s `DISEASE_CATEGORIES` dictionary. If DepMap changes their disease naming, update `DISEASE_CATEGORIES` accordingly. The existing config maps each disease category key (e.g., `"lung_cancer"`) to multiple DepMap disease labels (e.g., `"Non-Small Cell Lung Cancer"`, `"Lung Neuroendocrine Tumor"`), so the system will find the right rows via IN-clause matching.

---

## File 2: TCGA Expression Summary

### What it is

The [TCGA (The Cancer Genome Atlas)](https://www.cancer.gov/ccg/research/genome-sequencing/tcga) project profiled ~11,000 tumors across 33 cancer types with RNA-seq. This file summarizes gene expression (TPM) per gene, per cancer type, alongside tumor-vs-normal comparisons and tissue specificity classifications.

### Schema

```
gene,cancer_type,median_tpm_tumor,median_tpm_normal,log2fc_tumor_normal,overexpression_category,tumor_normal_diff_category,tissue_specificity
```

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `gene` | string | HGNC gene symbol (uppercase) | `EGFR` |
| `cancer_type` | string | TCGA cancer type label — must match entries in `config.py` `DISEASE_CATEGORIES` | `Non-Small Cell Lung Cancer` |
| `median_tpm_tumor` | float | Median TPM across all tumor samples of this cancer type | `45.2` |
| `median_tpm_normal` | float | Median TPM across matched normal samples. Set to `0` if no normal samples available. | `12.1` |
| `log2fc_tumor_normal` | float | log2(median_tpm_tumor / median_tpm_normal). If normal = 0, use a pseudo-count of 0.1. | `1.91` |
| `overexpression_category` | string | `"high"` / `"moderate"` / `"low"` — how strongly overexpressed the gene is in this cancer | `high` |
| `tumor_normal_diff_category` | string | `"significant"` (log2FC > 2) / `"moderate"` (log2FC > 1) / `"none"` / `"unknown"` | `moderate` |
| `tissue_specificity` | string | `"high"` / `"moderate"` / `"low"` — how tissue-specific the gene's expression is (from GTEx or HPA reference) | `high` |

### Classification rules

**overexpression_category** (based on tumor TPM and log2FC):
- `"high"`: median_tpm_tumor > 50 AND log2fc > 1
- `"moderate"`: median_tpm_tumor > 10 OR log2fc > 0.5
- `"low"`: everything else

**tumor_normal_diff_category** (based on log2FC):
- `"significant"`: log2fc > 2
- `"moderate"`: log2fc > 1
- `"none"`: log2fc ≤ 1
- `"unknown"`: no normal samples available

**tissue_specificity** (requires GTEx or HPA reference data):
- `"high"`: gene is predominantly expressed in ≤ 2 tissues
- `"moderate"`: enriched in 3–5 tissues
- `"low"`: broadly expressed (> 5 tissues)

### Example rows

```csv
gene,cancer_type,median_tpm_tumor,median_tpm_normal,log2fc_tumor_normal,overexpression_category,tumor_normal_diff_category,tissue_specificity
EGFR,Non-Small Cell Lung Cancer,45.2,12.1,1.91,high,significant,high
ERBB2,Breast Cancer,78.3,8.2,3.26,high,significant,high
CLDN18,Gastric Cancer,156.9,85.4,0.88,high,significant,high
CLDN18,Pancreatic Adenocarcinoma,12.3,0.5,4.62,high,significant,high
KRAS,Non-Small Cell Lung Cancer,35.6,9.8,1.86,moderate,moderate,low
BRCA1,Ovarian Cancer,8.4,15.2,-0.85,low,none,low
DRD2,Brain Cancer,2.1,17.8,-3.07,low,significant,low
PRMT5,Non-Small Cell Lung Cancer,22.5,10.1,1.15,moderate,moderate,low
TP53,Non-Small Cell Lung Cancer,18.3,11.2,0.71,moderate,none,low
MUC1,Ovarian Cancer,95.6,12.3,2.96,high,significant,moderate
```

### How to prepare — step by step

**Option A: From cBioPortal (recommended — easiest)**

**Step 1**: Go to https://www.cbioportal.org/

**Step 2**: Select a TCGA study (e.g., "Lung Adenocarcinoma (TCGA, PanCancer Atlas)").

**Step 3**: Download:
- `data_mrna_seq_v2_rsem.txt` — RSEM-normalized expression per gene per sample
- `data_clinical_sample.txt` — sample metadata (tumor vs normal status)

**Step 4**: Process with Python:

```python
import pandas as pd
import numpy as np

# ── Load expression data ───────────────────────────────────────────────
# cBioPortal format: rows=genes, columns=samples, values=RSEM (log2)
expr = pd.read_csv("data_mrna_seq_v2_rsem.txt", sep="\t", index_col=0)

# Convert log2 RSEM → TPM (approximate: 2^rsem, then normalize)
# Many cBioPortal files already provide RSEM — convert to linear space
expr_linear = 2 ** expr  # RSEM is log2-transformed

# ── Load clinical data for tumor/normal labels ─────────────────────────
clinical = pd.read_csv("data_clinical_sample.txt", sep="\t",
                        skiprows=4, index_col=0)
# The SAMPLE_TYPE column typically has "Primary" / "Solid Tissue Normal" etc.
tumor_samples = clinical[clinical["SAMPLE_TYPE"].str.contains("Primary|Metastasis",
                          case=False, na=False)].index.tolist()
normal_samples = clinical[clinical["SAMPLE_TYPE"].str.contains("Normal",
                          case=False, na=False)].index.tolist()

# ── Compute per-gene medians ───────────────────────────────────────────
gene_stats = []
for gene in expr_linear.index:
    tumor_vals = expr_linear.loc[gene, expr_linear.columns.isin(tumor_samples)]
    normal_vals = expr_linear.loc[gene, expr_linear.columns.isin(normal_samples)]

    median_tumor = tumor_vals.median()
    median_normal = normal_vals.median() if len(normal_vals) > 0 else 0
    if median_normal <= 0:
        median_normal = 0.1  # pseudo-count

    log2fc = np.log2(median_tumor / median_normal)

    # ── Classify overexpression ─────────────────────────────────────
    if median_tumor > 50 and log2fc > 1:
        overexpr = "high"
    elif median_tumor > 10 or log2fc > 0.5:
        overexpr = "moderate"
    else:
        overexpr = "low"

    # ── Classify tumor-normal difference ────────────────────────────
    if log2fc > 2:
        tn_diff = "significant"
    elif log2fc > 1:
        tn_diff = "moderate"
    else:
        tn_diff = "none"

    # ── Tissue specificity (from GTEx — see separate section below) ──
    tissue_spec = lookup_tissue_specificity(gene)  # implement separately

    gene_stats.append({
        "gene": gene,
        "cancer_type": "Non-Small Cell Lung Cancer",  # adjust per study
        "median_tpm_tumor": round(median_tumor, 4),
        "median_tpm_normal": round(median_normal, 4),
        "log2fc_tumor_normal": round(log2fc, 4),
        "overexpression_category": overexpr,
        "tumor_normal_diff_category": tn_diff,
        "tissue_specificity": tissue_spec,
    })

df = pd.DataFrame(gene_stats)
df.to_csv("tcga_expression_summary.csv", index=False)
```

Repeat for each TCGA cancer type study and concatenate all results.

**Option B: From TCGA GDC Data Portal**

1. Go to https://portal.gdc.cancer.gov/
2. Select "TCGA" program, pick a cancer type (e.g., TCGA-LUAD for lung adenocarcinoma)
3. Download RNA-seq data — choose "HTSeq - FPKM-UQ" or "STAR - Counts"
4. Convert to TPM: sum all gene counts per sample, divide each gene by total, multiply by 1e6
5. Download clinical supplement to label tumor vs normal
6. Follow the same Python processing steps above

**Option C: From UCSC Xena (quickest for pre-computed data)**

1. Go to https://xenabrowser.net/datapages/
2. Select a TCGA cohort (e.g., "TCGA Lung Cancer (LUNG)")
3. Download "gene expression RNAseq — HTSeq — FPKM-UQ" — already in a clean matrix format
4. Convert FPKM-UQ → TPM: FPKM-UQ values are proportional to TPM, so use as-is or normalize
5. Download "phenotype" data for tumor/normal labels
6. Follow the same aggregation steps

### Tissue specificity — separate reference

Tissue specificity classification requires a reference expression atlas like GTEx (https://gtexportal.org/) or Human Protein Atlas (https://www.proteinatlas.org/). A simplified approach:

```python
def lookup_tissue_specificity(gene):
    """
    Simplified tissue specificity from GTEx median TPM data.
    You need to pre-download GTEx median TPM per tissue from:
    https://gtexportal.org/home/downloads/adult-gtex/bulk_tissue_expression
    """
    # Load GTEx reference: gene × tissue matrix of median TPM
    # gtex = pd.read_csv("GTEx_Analysis_median_tpm.csv", index_col=0)

    # Count tissues where gene TPM > 10
    # n_tissues = (gtex.loc[gene] > 10).sum()

    # if n_tissues <= 2: return "high"
    # elif n_tissues <= 5: return "moderate"
    # else: return "low"

    return "unknown"  # placeholder if GTEx data not loaded
```

---

## File 3: TCGA Mutation Summary

### What it is

Summarizes somatic mutation and copy-number alteration (CNA) frequencies per gene, per TCGA cancer type. Covers point mutations (SNVs, indels), amplifications, and deletions.

### Schema

```
gene,cancer_type,mutation_freq,cnv_amp_freq,cnv_del_freq,total_alteration_freq,prognostic_associated
```

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `gene` | string | HGNC gene symbol (uppercase) | `EGFR` |
| `cancer_type` | string | TCGA cancer type label | `Non-Small Cell Lung Cancer` |
| `mutation_freq` | float | Fraction of samples with a non-silent somatic mutation (0–1) | `0.15` |
| `cnv_amp_freq` | float | Fraction of samples with copy-number amplification (GISTIC value ≥ 2) (0–1) | `0.08` |
| `cnv_del_freq` | float | Fraction of samples with copy-number deletion (GISTIC value ≤ −2) (0–1) | `0.02` |
| `total_alteration_freq` | float | Combined alteration frequency = mutation_freq + cnv_amp_freq (approximate — subtract overlap if available) | `0.23` |
| `prognostic_associated` | int | `1` if gene alteration is associated with survival difference (log-rank p < 0.05), `0` otherwise | `1` |

### Example rows

```csv
gene,cancer_type,mutation_freq,cnv_amp_freq,cnv_del_freq,total_alteration_freq,prognostic_associated
EGFR,Non-Small Cell Lung Cancer,0.15,0.08,0.02,0.23,1
KRAS,Pancreatic Adenocarcinoma,0.90,0.02,0.01,0.92,0
KRAS,Non-Small Cell Lung Cancer,0.30,0.03,0.01,0.33,1
TP53,Non-Small Cell Lung Cancer,0.48,0.01,0.10,0.49,1
TP53,Breast Cancer,0.32,0.02,0.15,0.34,0
ERBB2,Breast Cancer,0.04,0.18,0.03,0.22,1
BRCA1,Ovarian Cancer,0.08,0.04,0.12,0.12,0
CLDN18,Gastric Cancer,0.01,0.02,0.01,0.03,0
DRD2,Brain Cancer,0.01,0.03,0.005,0.04,0
PRMT5,Non-Small Cell Lung Cancer,0.01,0.02,0.01,0.03,0
PTEN,Breast Cancer,0.05,0.02,0.08,0.07,1
```

### How to prepare — step by step

**From cBioPortal (recommended)**

**Step 1**: For a given TCGA study on cBioPortal, download:
- `data_mutations_extended.txt` — per-sample mutation calls (MAF format)
- `data_cna.txt` — GISTIC copy-number calls per gene per sample (values: −2, −1, 0, 1, 2)

**Step 2**: Process with Python:

```python
import pandas as pd

cancer_type = "Non-Small Cell Lung Cancer"
total_samples = 510  # number of samples in the TCGA study

# ── 1. Mutation frequency ──────────────────────────────────────────────
maf = pd.read_csv("data_mutations_extended.txt", sep="\t",
                   low_memory=False)

# Filter to non-silent mutations
non_silent = maf[~maf["Variant_Classification"].isin([
    "Silent", "Intron", "5'UTR", "3'UTR", "5'Flank", "3'Flank",
    "IGR", "RNA"
])]

# Count samples with ≥ 1 non-silent mutation per gene
mutated_samples = non_silent.groupby("Hugo_Symbol")["Tumor_Sample_Barcode"].nunique()
mutation_freq = mutated_samples / total_samples

# ── 2. CNA frequency ───────────────────────────────────────────────────
cna = pd.read_csv("data_cna.txt", sep="\t", index_col=0)
# cBioPortal CNA: -2=homozygous deletion, -1=hemizygous deletion,
#                  0=diploid, 1=gain, 2=amplification

n_samples_cna = cna.shape[1]
amp_freq  = (cna == 2).sum(axis=1) / n_samples_cna
del_freq  = (cna <= -1).sum(axis=1) / n_samples_cna  # deep + shallow deletion

# ── 3. Combine ─────────────────────────────────────────────────────────
all_genes = sorted(set(mutation_freq.index) | set(amp_freq.index))
rows = []
for gene in all_genes:
    mut_f = mutation_freq.get(gene, 0)
    amp_f = amp_freq.get(gene, 0)
    del_f = del_freq.get(gene, 0)
    total_f = mut_f + amp_f  # simple sum; subtract overlap if available

    # ── Prognostic association (simplified) ──────────────────────────
    # This requires survival analysis. A simple approximation:
    # set to 1 for well-known prognostic genes, 0 otherwise.
    # For a rigorous approach, download clinical survival data and
    # run log-rank test per gene.
    prognostic = 1 if gene in {
        "EGFR", "KRAS", "TP53", "ERBB2", "PTEN", "PIK3CA"
    } else 0

    rows.append({
        "gene": gene,
        "cancer_type": cancer_type,
        "mutation_freq": round(mut_f, 4),
        "cnv_amp_freq": round(amp_f, 4),
        "cnv_del_freq": round(del_f, 4),
        "total_alteration_freq": round(total_f, 4),
        "prognostic_associated": prognostic,
    })

df = pd.DataFrame(rows)
df.to_csv("tcga_mutation_summary.csv", index=False)
```

**Step 3**: Repeat for each TCGA cancer type and concatenate.

### Prognostic association — rigorous approach

For a data-driven (rather than curated) prognostic classification:

```python
from lifelines import KaplanMeierFitter
from lifelines.statistics import logrank_test

# Load clinical survival data (from cBioPortal data_clinical_patient.txt)
clinical = pd.read_csv("data_clinical_patient.txt", sep="\t",
                        skiprows=4, index_col=0)
# Columns needed: OS_MONTHS (overall survival months), OS_STATUS (1=deceased)

# For each gene, split patients into "altered" vs "unaltered"
# and run log-rank test. Set prognostic_associated = 1 if p < 0.05.
```

For most users, the curated gene list approach (well-known prognostic genes) is sufficient and much simpler to implement.

---

## Verification Checklist

After preparing all three files, verify them before building the database:

```bash
# 1. Check row counts
wc -l data/processed/depmap_crispr_summary.csv    # expect 5,000–20,000+
wc -l data/processed/tcga_expression_summary.csv  # expect 10,000–30,000+
wc -l data/processed/tcga_mutation_summary.csv    # expect 10,000–30,000+

# 2. Check headers
head -1 data/processed/depmap_crispr_summary.csv
# → gene,primary_disease,mean_chronos_score,num_cell_lines,...

head -1 data/processed/tcga_expression_summary.csv
# → gene,cancer_type,median_tpm_tumor,...

head -1 data/processed/tcga_mutation_summary.csv
# → gene,cancer_type,mutation_freq,...

# 3. Verify gene symbols are uppercase (not mixed-case)
cut -d',' -f1 data/processed/depmap_crispr_summary.csv | sort -u | head -20

# 4. Verify disease labels match config.py DISEASE_CATEGORIES
#    (spot-check a few entries)
grep "Non-Small Cell Lung Cancer" data/processed/depmap_crispr_summary.csv | head -3

# 5. Verify numeric ranges
#    Chronos scores: typically -1.5 to +0.5
#    Frequencies: 0.0 to 1.0
#    TPM: 0 to 10000+

# 6. All three files present before building DB
ls -lh data/processed/depmap_crispr_summary.csv \
      data/processed/tcga_expression_summary.csv \
      data/processed/tcga_mutation_summary.csv
```

Once verified, import into the offline database:

```bash
python3.8 data/build_offline_db.py
# or, if DB already exists:
python3.8 data/update_offline_db.py --table depmap_crispr
python3.8 data/update_offline_db.py --table tcga
```
