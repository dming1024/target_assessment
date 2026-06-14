# Offline Database Design

## Goal

Reduce target assessment response time from 2+ minutes to under 10 seconds by replacing all network API calls with local SQLite queries, while retaining the original API clients as fallback.

## Scope

- Build a SQLite database (`data/target_assessment.db`) from public bulk downloads
- Create `OfflineProvider` — a single class that answers all evidence queries via SQLite
- Wire `DataManager` to use `OfflineProvider` first, falling back to existing API clients on miss
- Provide a one-command build script (`data/build_offline_db.py`) for initial construction and periodic refresh
- Drop ClinicalTrials.gov as a live dependency; derive clinical-competition fields from ChEMBL + Open Targets instead
- Leave all existing modules untouched (they remain as fallback)

## Data Sources — Offline Replacements

| Live API | Offline Source | URL / Accession | Size (download) | Size (in SQLite) |
|----------|---------------|-----------------|-----------------|-------------------|
| mygene.info | NCBI `Homo_sapiens.gene_info.gz` | `https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz` | ~25 MB | ~5 MB |
| Open Targets | Monthly Parquet release — `associationByOverallDirect` | `https://platform.opentargets.org/downloads` | ~500 MB | ~50 MB (filtered) |
| ChEMBL | ChEMBL SQLite full database | `https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/latest/` (chembl_XX_sqlite.tar.gz) | ~800 MB compressed / ~2 GB expanded | ~10 MB (extracted) |
| DepMap CRISPR | Existing CSV → SQLite (no download needed) | — | — | ~90 MB |
| TCGA Expression | Existing CSV → SQLite (no download needed) | — | — | ~110 MB |
| TCGA Mutation | Existing CSV → SQLite (no download needed) | — | — | ~70 MB |

Total SQLite database: ~350 MB.

## SQLite Schema

```sql
-- Gene index: NCBI gene info (offline replacement for mygene.info)
CREATE TABLE genes (
    gene_symbol     TEXT PRIMARY KEY,
    ensembl_id      TEXT,        -- ENSG...
    entrez_id       TEXT,
    full_name       TEXT,
    synonyms        TEXT,        -- JSON array: ["alias1","alias2"]
    aliases_lower   TEXT         -- lowercase pipe-delimited for fast lookup: |her2|erb-b2|
);
CREATE INDEX idx_genes_aliases ON genes(aliases_lower);
CREATE INDEX idx_genes_ensembl ON genes(ensembl_id);

-- Open Targets: target-disease association scores
CREATE TABLE opentargets (
    ensembl_id              TEXT NOT NULL,
    efo_id                  TEXT NOT NULL,
    overall_score           REAL,
    genetic_association     REAL,
    somatic_mutation        REAL,
    known_drug              REAL,
    rna_expression          REAL,
    literature              REAL,
    affected_pathway        REAL,
    evidence_count          INTEGER,
    PRIMARY KEY (ensembl_id, efo_id)
);
CREATE INDEX idx_ot_ensembl ON opentargets(ensembl_id);

-- ChEMBL: drug counts per target gene
CREATE TABLE chembl_drugs (
    gene_symbol         TEXT PRIMARY KEY,
    chembl_target_id    TEXT,
    approved_drugs      INTEGER DEFAULT 0,
    clinical_candidates INTEGER DEFAULT 0,
    active_compounds    INTEGER DEFAULT 0,
    modality_fit        TEXT     -- "strong" / "moderate" / "weak" / "unknown"
);

-- DepMap CRISPR: gene dependency per cancer type
CREATE TABLE depmap_crispr (
    gene                TEXT NOT NULL,
    primary_disease     TEXT NOT NULL,
    mean_chronos_score  REAL,
    num_cell_lines      INTEGER,
    pan_cancer_mean_score REAL,
    pan_cancer_percentile REAL,
    selectivity_category TEXT,
    PRIMARY KEY (gene, primary_disease)
);
CREATE INDEX idx_depmap_gene ON depmap_crispr(gene);

-- TCGA expression: TPM + fold-change per gene per cancer type
CREATE TABLE tcga_expression (
    gene                    TEXT NOT NULL,
    cancer_type             TEXT NOT NULL,
    median_tpm_tumor        REAL,
    median_tpm_normal       REAL,
    log2fc_tumor_normal     REAL,
    overexpression_category TEXT,     -- "high" / "moderate" / "low"
    tumor_normal_diff_category TEXT,  -- "significant" / "moderate" / "none"
    tissue_specificity      TEXT,
    PRIMARY KEY (gene, cancer_type)
);
CREATE INDEX idx_tcga_expr_gene ON tcga_expression(gene);

-- TCGA mutation: alteration frequency per gene per cancer type
CREATE TABLE tcga_mutation (
    gene                    TEXT NOT NULL,
    cancer_type             TEXT NOT NULL,
    mutation_freq           REAL,
    cnv_amp_freq            REAL,
    cnv_del_freq            REAL,
    total_alteration_freq   REAL,
    prognostic_associated   INTEGER,   -- 0/1 boolean
    PRIMARY KEY (gene, cancer_type)
);
CREATE INDEX idx_tcga_mut_gene ON tcga_mutation(gene);
```

## Component Design

### `modules/offline_provider.py` (new)

Single class `OfflineProvider` that wraps all SQLite access:

```
class OfflineProvider:
    __init__(db_path)          → open SQLite connection (read-only, WAL mode)
    resolve_gene(symbol)       → (official_symbol, ensembl_id, full_name, synonyms)
    query_ot(ensembl_id, efo)  → dict of OT scores
    query_chembl(gene_symbol)  → dict of drug counts
    query_depmap(gene, disease) → dict of dependency data
    query_tcga_expr(gene, disease) → dict of expression data
    query_tcga_mut(gene, disease)  → dict of mutation data
    is_available()             → bool (db exists and has tables)
```

Key behaviors:
- Connection opened once at init, reused for all queries
- Disease name matching: same fuzzy logic as current code (exact → substring → first row)
- Alias resolution via `aliases_lower` LIKE search
- All heavy filtering done in SQL with parameterized queries
- Returns the same dict shapes that existing clients return (API-compatible)

### `modules/data_manager.py` (modified)

In `_build_from_real_sources()`:

```
if self.offline.is_available():
    evidence = self._build_from_offline(gene, disease, ensembl_id)
else:
    evidence = self._build_from_live_apis(gene, disease, ensembl_id)  # existing code
```

New method `_build_from_offline()` calls `OfflineProvider` for all 6 dimensions, then constructs evidence dicts in exactly the same structure as the current API path. Clinical-competition fields (`active_clinical_trials`, `differentiation_opportunity`) are derived from `chembl_drugs.approved_drugs` + `opentargets.known_drug`.

### `config.py` (modified)

Add: `OFFLINE_DB = PROCESSED_DIR / "target_assessment.db"`

### `data/build_offline_db.py` (new)

One-command build script. Sections:

1. **Download phase** (with progress bars via `tqdm`):
   - `download_ncbi_genes()` — fetch `Homo_sapiens.gene_info.gz`, parse gene records
   - `download_opentargets()` — fetch latest Parquet from OT downloads page, filter to human targets
   - `download_chembl()` — fetch latest ChEMBL SQLite, extract drug-mechanism data

2. **Import phase**:
   - `import_genes(conn)` — parse gene_info.gz into `genes` table
   - `import_opentargets(conn)` — read Parquet, write `opentargets` table
   - `import_chembl(conn)` — query ChEMBL SQLite, write `chembl_drugs` table
   - `import_depmap(conn)` — read existing CSV, write `depmap_crispr` table
   - `import_tcga(conn)` — read existing CSVs, write `tcga_expression` + `tcga_mutation` tables

3. **Index creation** (after bulk insert for speed)

4. **Cleanup**: remove downloaded temp files (keep only the SQLite DB)

```bash
# Usage:
python data/build_offline_db.py              # full build (download + import)
python data/build_offline_db.py --skip-download  # import from cached downloads
python data/build_offline_db.py --force          # overwrite existing DB
```

## Disease Matching Strategy

The current regex/substring matching in `data_manager._resolve_efo_id()` stays. For offline mode, the `EFO_DISEASE_MAP` dict in `config.py` maps user disease names → EFO IDs, and `opentargets` table stores EFO IDs directly. For TCGA/DepMap, the string matching logic moves into SQL `LIKE` queries inside `OfflineProvider`.

## Fallback Behavior

```
OfflineProvider.is_available()?
  ├── Yes → use SQLite (fast path, <1s)
  └── No  → use existing API clients (slow path, existing behavior)
             + log warning recommending `python data/build_offline_db.py`
```

The old API code in `opentargets_client.py`, `chembl_client.py`, `clinicaltrials_client.py`, `gene_resolver.py`, `depmap_module.py`, `tcga_module.py` remains completely untouched.

## Performance Targets

| Operation | Current (API) | After (SQLite) |
|-----------|--------------|----------------|
| Gene resolution | 1–3s (mygene.info) | <10ms (indexed lookup) |
| Open Targets | 2–5s (GraphQL) | <50ms (composite PK) |
| ChEMBL | 3–8s (2 REST calls + rate limit) | <10ms (PK lookup) |
| DepMap | 2–5s (98MB CSV load) | <50ms (indexed query) |
| TCGA expr + mut | 3–8s (191MB CSV load) | <100ms (indexed query) |
| **Total data collection** | **12–30s** | **<300ms** |
| Scoring + report | ~2s | ~2s |
| **End-to-end** | **15–35s (up to 120s+)** | **<5s** |

## Things NOT in Scope

- Incremental updates (full rebuild is fast enough — ~5 min monthly)
- Web UI / API server (CLI stays as-is)
- Removing existing API client code
- Changing the scoring engine or report format
- Adding new data sources

## Open Questions

- None remaining — answered during brainstorming:
  1. Storage: SQLite ✅
  2. Update strategy: periodic full rebuild ✅
  3. Old API code: retained as fallback ✅
  4. ClinicalTrials.gov: replaced by ChEMBL + OT ✅
