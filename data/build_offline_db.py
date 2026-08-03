#!/usr/bin/env python3
"""
Build the offline SQLite database for Target Assessment Tool.

Downloads public bulk datasets and imports them into a single SQLite file
(data/target_assessment.db) for sub-second queries.

Usage:
    python data/build_offline_db.py              # Full build (download + import)
    python data/build_offline_db.py --skip-download  # Import from cached files only
    python data/build_offline_db.py --force          # Overwrite existing DB
    python data/build_offline_db.py --only-genes     # Build only the genes table

Data sources:
    NCBI gene info      ~25 MB download → genes table
    DepMap CSV (local)  ~98 MB → depmap_crispr table
    TCGA CSVs (local)   ~191 MB → tcga_expression + tcga_mutation tables
    Open Targets Parquet ~500 MB → opentargets table (optional, if downloaded)
    ChEMBL SQLite       ~800 MB → chembl_drugs table (optional, if downloaded)
"""

import argparse
import csv
import gzip
import io
import logging
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlretrieve

import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import PROCESSED_DIR, OFFLINE_DB

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("build_offline_db")

# ── Constants ───────────────────────────────────────────────────────────

NCBI_GENE_URL = (
    "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/"
    "Homo_sapiens.gene_info.gz"
)

OPENTARGETS_URL = (
    "https://ftp.ebi.ac.uk/pub/databases/opentargets/platform/latest/output/"
    "association_overall_direct/"
)

# Latest ChEMBL version (auto-discovered; update when new releases appear)
CUSTOM_CHEMBL_VERSION = "37"

# ChEMBL latest release base (auto-discovered or pinned)
CHEMBL_FTP_BASE = "https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/latest/"

# ── Schema ──────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS genes (
    gene_symbol     TEXT PRIMARY KEY,
    ensembl_id      TEXT,
    entrez_id       TEXT,
    full_name       TEXT,
    synonyms        TEXT,
    aliases_lower   TEXT
);

CREATE TABLE IF NOT EXISTS opentargets (
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

CREATE TABLE IF NOT EXISTS chembl_drugs (
    gene_symbol         TEXT PRIMARY KEY,
    chembl_target_id    TEXT,
    approved_drugs      INTEGER DEFAULT 0,
    clinical_candidates INTEGER DEFAULT 0,
    active_compounds    INTEGER DEFAULT 0,
    modality_fit        TEXT
);

CREATE TABLE IF NOT EXISTS depmap_crispr (
    gene                    TEXT NOT NULL,
    primary_disease         TEXT NOT NULL,
    mean_chronos_score      REAL,
    num_cell_lines          INTEGER,
    pan_cancer_mean_score   REAL,
    pan_cancer_percentile   REAL,
    selectivity_category    TEXT,
    PRIMARY KEY (gene, primary_disease)
);

CREATE TABLE IF NOT EXISTS tcga_expression (
    gene                        TEXT NOT NULL,
    cancer_type                 TEXT NOT NULL,
    median_tpm_tumor            REAL,
    median_tpm_normal           REAL,
    log2fc_tumor_normal         REAL,
    overexpression_category     TEXT,
    tumor_normal_diff_category  TEXT,
    tissue_specificity          TEXT,
    PRIMARY KEY (gene, cancer_type)
);

CREATE TABLE IF NOT EXISTS tcga_mutation (
    gene                    TEXT NOT NULL,
    cancer_type             TEXT NOT NULL,
    mutation_freq           REAL,
    cnv_amp_freq            REAL,
    cnv_del_freq            REAL,
    total_alteration_freq   REAL,
    prognostic_associated   INTEGER DEFAULT 0,
    PRIMARY KEY (gene, cancer_type)
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_genes_aliases ON genes(aliases_lower);",
    "CREATE INDEX IF NOT EXISTS idx_genes_ensembl ON genes(ensembl_id);",
    "CREATE INDEX IF NOT EXISTS idx_ot_ensembl ON opentargets(ensembl_id);",
    "CREATE INDEX IF NOT EXISTS idx_depmap_gene ON depmap_crispr(gene);",
    "CREATE INDEX IF NOT EXISTS idx_tcga_expr_gene ON tcga_expression(gene);",
    "CREATE INDEX IF NOT EXISTS idx_tcga_mut_gene ON tcga_mutation(gene);",
]


# ── Helpers ─────────────────────────────────────────────────────────────

def _report_stage(msg: str):
    logger.info("=" * 60)
    logger.info(msg)


def _report_done(start: float, rows: int):
    elapsed = time.time() - start
    logger.info(f"  → {rows:,} rows in {elapsed:.1f}s")


# ── Stage 1: NCBI gene info ─────────────────────────────────────────────

def download_ncbi_genes(data_dir: Path) -> Path:
    """Download Homo_sapiens.gene_info.gz, return path to the .gz file."""
    dst = data_dir / "Homo_sapiens.gene_info.gz"
    if dst.exists():
        logger.info(f"NCBI gene info already cached: {dst}")
        return dst
    logger.info(f"Downloading NCBI gene info → {dst}")
    urlretrieve(NCBI_GENE_URL, dst)
    logger.info(f"  done ({dst.stat().st_size / 1024 / 1024:.1f} MB)")
    return dst


def import_genes(conn: sqlite3.Connection, data_dir: Path):
    """Parse NCBI gene_info.gz → genes table."""
    _report_stage("Stage 1: Importing NCBI gene info")
    t0 = time.time()

    gz_path = download_ncbi_genes(data_dir)
    rows = []
    with gzip.open(gz_path, "rt") as f:
        for line in f:
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 10:
                continue
            # Columns: tax_id, GeneID, Symbol, LocusTag, Synonyms, dbXrefs,
            #          chromosome, map_location, description, type_of_gene, ...
            gene_id = fields[1]
            symbol = fields[2]
            synonyms_str = fields[4]  # pipe-delimited
            dbxrefs = fields[5]       # includes Ensembl:ENSG...
            full_name = fields[8] if len(fields) > 8 else ""

            # Extract Ensembl ID from dbxrefs
            ensembl_id = ""
            for ref in dbxrefs.split("|"):
                if ref.startswith("Ensembl:"):
                    ensembl_id = ref.split(":", 1)[1]
                    break

            synonyms = [s for s in synonyms_str.split("|") if s and s != "-"]
            aliases_lower = "|" + "|".join(
                [symbol.lower()] + [s.lower() for s in synonyms]
            ) + "|"

            rows.append((symbol, ensembl_id, gene_id, full_name,
                        str(synonyms), aliases_lower))

    conn.executemany(
        "INSERT OR REPLACE INTO genes VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    _report_done(t0, len(rows))


# ── Stage 2: DepMap CSV ─────────────────────────────────────────────────

def import_depmap(conn: sqlite3.Connection):
    """Import preprocessed DepMap CSV → depmap_crispr table."""
    _report_stage("Stage 2: Importing DepMap CRISPR data")
    t0 = time.time()

    csv_path = PROCESSED_DIR / "depmap_crispr_summary.csv"
    if not csv_path.exists():
        logger.warning(f"DepMap CSV not found: {csv_path} — skipping")
        return

    df = pd.read_csv(csv_path)
    df["gene"] = df["gene"].str.upper()
    df["num_cell_lines"] = df.get("num_cell_lines", 1).fillna(0).astype(int)

    rows = []
    for _, r in df.iterrows():
        rows.append((
            r["gene"],
            r["primary_disease"],
            round(r.get("mean_chronos_score", 0) or 0, 6),
            int(r.get("num_cell_lines", 0) or 0),
            round(r.get("pan_cancer_mean_score", 0) or 0, 6),
            round(r.get("pan_cancer_percentile", 50) or 50, 4),
            r.get("selectivity_category", "unknown") or "unknown",
        ))

    conn.executemany(
        "INSERT OR REPLACE INTO depmap_crispr VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    _report_done(t0, len(rows))


# ── Stage 3: TCGA CSVs ──────────────────────────────────────────────────

def import_tcga_expression(conn: sqlite3.Connection):
    """Import preprocessed TCGA expression CSV → tcga_expression table."""
    _report_stage("Stage 3a: Importing TCGA expression data")
    t0 = time.time()

    csv_path = PROCESSED_DIR / "tcga_expression_summary.csv"
    if not csv_path.exists():
        logger.warning(f"TCGA expression CSV not found: {csv_path} — skipping")
        return

    df = pd.read_csv(csv_path)
    df["gene"] = df["gene"].str.upper()

    rows = []
    for _, r in df.iterrows():
        rows.append((
            r["gene"],
            r["cancer_type"],
            round(r.get("median_tpm_tumor", 0) or 0, 4),
            round(r.get("median_tpm_normal", 0) or 0, 4),
            round(r.get("log2fc_tumor_normal", 0) or 0, 4),
            r.get("overexpression_category", "unknown") or "unknown",
            r.get("tumor_normal_diff_category", "unknown") or "unknown",
            r.get("tissue_specificity", "unknown") or "unknown",
        ))

    conn.executemany(
        "INSERT OR REPLACE INTO tcga_expression VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    _report_done(t0, len(rows))


def import_tcga_mutation(conn: sqlite3.Connection):
    """Import preprocessed TCGA mutation CSV → tcga_mutation table."""
    _report_stage("Stage 3b: Importing TCGA mutation data")
    t0 = time.time()

    csv_path = PROCESSED_DIR / "tcga_mutation_summary.csv"
    if not csv_path.exists():
        logger.warning(f"TCGA mutation CSV not found: {csv_path} — skipping")
        return

    df = pd.read_csv(csv_path)
    if "gene" in df.columns:
        df["gene"] = df["gene"].str.upper()

    rows = []
    for _, r in df.iterrows():
        rows.append((
            r["gene"],
            r["cancer_type"],
            round(r.get("mutation_freq", 0) or 0, 4),
            round(r.get("cnv_amp_freq", 0) or 0, 4),
            round(r.get("cnv_del_freq", 0) or 0, 4),
            round(r.get("total_alteration_freq", 0) or 0, 4),
            int(r.get("prognostic_associated", 0) or 0),
        ))

    conn.executemany(
        "INSERT OR REPLACE INTO tcga_mutation VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    _report_done(t0, len(rows))


# ── Stage 4: Open Targets Parquet ───────────────────────────────────────

def _find_ot_parquet_dir(data_dir: Path) -> Path:
    """Check for an Open Targets parquet parts directory."""
    ot_dir = data_dir / "ot_parts"
    if ot_dir.is_dir() and list(ot_dir.glob("*.parquet")):
        return ot_dir
    return None


def download_opentargets(data_dir: Path) -> Path:
    """Download Open Targets association Parquet parts and combine into one file."""
    dst = data_dir / "opentargets_associations.parquet"
    if dst.exists():
        logger.info(f"Open Targets Parquet already cached: {dst}")
        return dst

    ot_dir = data_dir / "ot_parts"
    ot_dir.mkdir(parents=True, exist_ok=True)

    # List all part files from the FTP directory
    import re
    import urllib.request

    logger.info(f"Listing Open Targets parts from: {OPENTARGETS_URL}")
    try:
        resp = urllib.request.urlopen(OPENTARGETS_URL)
        content = resp.read().decode()
        part_files = re.findall(r'href="(part-[^\"]+\.parquet)"', content)
    except Exception as e:
        logger.warning(f"Failed to list Open Targets parts: {e}")
        existing = _find_ot_parquet_dir(data_dir)
        if existing:
            return _combine_ot_parts(existing, dst)
        return None

    if not part_files:
        logger.warning("No parquet part files found in Open Targets directory")
        return None

    logger.info(f"Found {len(part_files)} part files")

    # Download missing parts
    downloaded = 0
    for fname in sorted(part_files):
        part_path = ot_dir / fname
        if part_path.exists():
            continue
        url = OPENTARGETS_URL + fname
        try:
            urlretrieve(url, part_path)
            downloaded += 1
        except Exception as e:
            logger.warning(f"Failed to download {fname}: {e}")

    if downloaded > 0:
        logger.info(f"  downloaded {downloaded} new part(s)")

    return _combine_ot_parts(ot_dir, dst)


def _combine_ot_parts(ot_dir: Path, dst: Path) -> Path:
    """Combine multiple parquet part files into a single parquet file."""
    import glob as glob_mod
    parts = sorted(ot_dir.glob("part-*.parquet"))
    if not parts:
        logger.warning("No parquet part files found")
        return None

    logger.info(f"Combining {len(parts)} part files → {dst}")
    try:
        # Read all parts as a single dataset and write as one file
        df = pd.read_parquet(str(ot_dir))
        df.to_parquet(dst, index=False)
        sz = dst.stat().st_size / 1024 / 1024
        logger.info(f"  combined parquet: {len(df):,} rows, {sz:.1f} MB")
        return dst
    except Exception as e:
        logger.warning(f"Failed to combine parquet parts: {e}")
        # Fall back to reading from directory
        logger.info("Will read from parts directory directly")
        return ot_dir


def import_opentargets(conn: sqlite3.Connection, data_dir: Path):
    """Import Open Targets Parquet → opentargets table."""
    _report_stage("Stage 4: Importing Open Targets data")
    t0 = time.time()

    parquet_path = download_opentargets(data_dir)
    if parquet_path is None:
        logger.warning("Open Targets Parquet not available — skipping "
                       "(run with --skip-ot if no OT data needed)")
        return

    logger.info(f"Reading Parquet: {parquet_path}")
    try:
        if parquet_path.is_dir():
            df = pd.read_parquet(str(parquet_path))
        else:
            df = pd.read_parquet(parquet_path)
    except Exception as e:
        logger.warning(f"Failed to read Open Targets Parquet: {e} — skipping")
        return

    logger.info(f"  raw rows: {len(df):,}")

    # Filter to human targets (ENSG prefix)
    if "targetId" in df.columns:
        df = df[df["targetId"].str.startswith("ENSG", na=False)]
        logger.info(f"  human targets: {len(df):,}")

    # Map columns to our schema
    col_map = {
        "targetId": "ensembl_id",
        "diseaseId": "efo_id",
        "score": "overall_score",
    }
    # Datatype score columns
    datatype_cols = {
        "datatypeScores.genetic_association": "genetic_association",
        "datatypeScores.somatic_mutation": "somatic_mutation",
        "datatypeScores.known_drug": "known_drug",
        "datatypeScores.rna_expression": "rna_expression",
        "datatypeScores.literature": "literature",
        "datatypeScores.affected_pathway": "affected_pathway",
    }
    evidence_col = "evidenceCount"

    # Rename known columns
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    required_cols = ["ensembl_id", "efo_id", "overall_score"]
    if not all(c in df.columns for c in required_cols):
        logger.warning(
            f"Open Targets Parquet missing expected columns. "
            f"Found: {list(df.columns)[:20]}"
        )
        return

    # Select and fill columns
    output_cols = required_cols.copy()
    for src, dst in datatype_cols.items():
        if src in df.columns:
            df[dst] = df[src].fillna(0.0)
        else:
            df[dst] = 0.0
        output_cols.append(dst)

    if evidence_col in df.columns:
        df["evidence_count"] = df[evidence_col].fillna(0).astype(int)
    else:
        df["evidence_count"] = 0
    output_cols.append("evidence_count")

    # De-duplicate on the composite key (keep highest score)
    key_cols = ["ensembl_id", "efo_id"]
    df = df.sort_values("overall_score", ascending=False).drop_duplicates(
        subset=key_cols, keep="first"
    )
    logger.info(f"  after dedup: {len(df):,}")

    # Write to SQLite
    rows = []
    for _, r in df[output_cols].iterrows():
        rows.append(tuple(
            round(r[c], 6) if isinstance(r[c], float) else r[c]
            for c in output_cols
        ))

    conn.executemany(
        f"INSERT OR REPLACE INTO opentargets ({', '.join(output_cols)}) "
        f"VALUES ({', '.join(['?'] * len(output_cols))})",
        rows,
    )
    conn.commit()
    _report_done(t0, len(rows))


# ── Stage 5: ChEMBL SQLite ──────────────────────────────────────────────

def _find_chembl_sqlite(data_dir: Path) -> Path:
    """Find a ChEMBL SQLite file in the data directory (searches recursively)."""
    # Check for chembl_XX_sqlite directory (top-level or one level deep)
    candidates = list(data_dir.iterdir())
    for d in candidates:
        if d.is_dir() and d.name.startswith("chembl") and d.name.endswith("sqlite"):
            db_file = d / f"{d.name}.db"
            if db_file.exists():
                return db_file
            for fname in ["chembl.db", f"{d.name.split('_sqlite')[0]}.db"]:
                candidate = d / fname
                if candidate.exists():
                    return candidate
        # Check one level deeper (e.g. chembl_37/chembl_37_sqlite/)
        if d.is_dir() and d.name.startswith("chembl"):
            for sub in d.iterdir():
                if sub.is_dir() and sub.name.startswith("chembl") and sub.name.endswith("sqlite"):
                    db_file = sub / f"{sub.name}.db"
                    if db_file.exists():
                        return db_file
                    for fname in ["chembl.db", f"{sub.name.split('_sqlite')[0]}.db"]:
                        candidate = sub / fname
                        if candidate.exists():
                            return candidate

    # Recursive glob fallback
    for f in sorted(data_dir.rglob("chembl*.db"), reverse=True):
        return f

    return None


def download_chembl(data_dir: Path) -> Path:
    """Download ChEMBL SQLite tarball and extract it."""
    # First check if already available
    existing = _find_chembl_sqlite(data_dir)
    if existing is not None:
        logger.info(f"ChEMBL SQLite already available: {existing}")
        return existing

    # Try to discover the latest release version and filename
    # The tarball is named like: chembl_34_sqlite.tar.gz
    chembl_ver = os.environ.get("CHEMBL_VERSION", CUSTOM_CHEMBL_VERSION)
    tarball = f"chembl_{chembl_ver}_sqlite.tar.gz"
    url = CHEMBL_FTP_BASE + tarball
    dst = data_dir / tarball

    if not dst.exists():
        logger.info(f"Downloading ChEMBL SQLite → {dst}")
        logger.info(f"  URL: {url}")
        try:
            urlretrieve(url, dst)
            sz = dst.stat().st_size / 1024 / 1024
            logger.info(f"  done ({sz:.1f} MB)")
        except Exception as e:
            logger.warning(f"ChEMBL download failed: {e}")
            return None

    # Extract
    import tarfile
    extract_dir = data_dir / f"chembl_{chembl_ver}_sqlite"
    if not extract_dir.exists():
        logger.info(f"Extracting ChEMBL tarball → {extract_dir}")
        with tarfile.open(dst, "r:gz") as tar:
            tar.extractall(data_dir)

    # Find the SQLite file
    db_file = extract_dir / f"chembl_{chembl_ver}.db"
    if db_file.exists():
        return db_file
    db_file = extract_dir / "chembl.db"
    if db_file.exists():
        return db_file

    logger.warning("Could not find chembl.db in extracted tarball")
    return None


def import_chembl(conn: sqlite3.Connection, data_dir: Path):
    """Import ChEMBL drug-mechanism data → chembl_drugs table."""
    _report_stage("Stage 5: Importing ChEMBL drug data")
    t0 = time.time()

    chembl_db = download_chembl(data_dir)
    if chembl_db is None:
        logger.warning("ChEMBL SQLite not available — skipping "
                       "(drug count data will be empty)")
        return

    logger.info(f"Querying ChEMBL SQLite: {chembl_db}")
    chembl_conn = sqlite3.connect(str(chembl_db))
    chembl_conn.row_factory = sqlite3.Row

    # Query: gene → drug counts by phase
    # Join: target_dictionary → drug_mechanism (via tid) → molecule_dictionary
    # Gene symbol comes from component_synonyms (syn_type='GENE_SYMBOL')
    query = """
    SELECT
        csyn.component_synonym AS gene_symbol,
        td.chembl_id AS target_chembl_id,
        td.pref_name AS target_pref_name,
        COUNT(DISTINCT CASE WHEN m.max_phase >= 4 THEN m.molregno END) AS approved_drugs,
        COUNT(DISTINCT CASE WHEN m.max_phase >= 2 AND m.max_phase < 4 THEN m.molregno END) AS clinical_candidates,
        COUNT(DISTINCT CASE WHEN m.max_phase <= 1 OR m.max_phase IS NULL THEN m.molregno END) AS active_compounds
    FROM target_dictionary td
    JOIN target_components tc ON tc.tid = td.tid
    JOIN component_synonyms csyn ON csyn.component_id = tc.component_id
    LEFT JOIN drug_mechanism dm ON dm.tid = td.tid
    LEFT JOIN molecule_dictionary m ON m.molregno = dm.molregno
    WHERE td.organism = 'Homo sapiens'
      AND td.target_type = 'SINGLE PROTEIN'
      AND csyn.syn_type = 'GENE_SYMBOL'
    GROUP BY csyn.component_synonym
    ORDER BY approved_drugs DESC
    """

    try:
        rows = chembl_conn.execute(query).fetchall()
    except Exception as e:
        logger.warning(f"ChEMBL query failed: {e} — trying simpler query")
        try:
            rows = chembl_conn.execute("""
                SELECT csyn.component_synonym AS gene_symbol,
                       td.chembl_id AS target_chembl_id,
                       td.pref_name AS target_pref_name,
                       0 AS approved_drugs, 0 AS clinical_candidates, 0 AS active_compounds
                FROM target_dictionary td
                JOIN target_components tc ON tc.tid = td.tid
                JOIN component_synonyms csyn ON csyn.component_id = tc.component_id
                WHERE td.organism = 'Homo sapiens'
                  AND td.target_type = 'SINGLE PROTEIN'
                  AND csyn.syn_type = 'GENE_SYMBOL'
            """).fetchall()
        except Exception as e2:
            logger.warning(f"Fallback query also failed: {e2} — skipping ChEMBL")
            chembl_conn.close()
            return

    inserted = 0
    for row in rows:
        gene = row["gene_symbol"] or ""
        if not gene:
            continue
        approved = row["approved_drugs"] or 0
        clinical = row["clinical_candidates"] or 0
        active = row["active_compounds"] or 0

        # Modality fit
        if approved + clinical >= 3:
            modality_fit = "strong"
        elif approved + clinical >= 1 or active >= 5:
            modality_fit = "moderate"
        elif active > 0:
            modality_fit = "weak"
        else:
            modality_fit = "unknown"

        conn.execute(
            "INSERT OR REPLACE INTO chembl_drugs VALUES (?, ?, ?, ?, ?, ?)",
            (gene, row["target_chembl_id"], approved, clinical, active, modality_fit),
        )
        inserted += 1

    conn.commit()
    chembl_conn.close()
    _report_done(t0, inserted)


# ── Main ────────────────────────────────────────────────────────────────

def build_db(
    skip_download: bool = False,
    force: bool = False,
    only_genes: bool = False,
    only_local: bool = False,
):
    """Build the offline SQLite database."""
    db_path = Path(OFFLINE_DB)

    if db_path.exists() and not force:
        logger.info(f"Database exists: {db_path}")
        logger.info("Use --force to overwrite.")
        return

    if db_path.exists() and force:
        db_path.unlink()
        logger.info(f"Removed existing database: {db_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    data_dir = db_path.parent

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=OFF")  # Faster bulk import
    conn.execute("PRAGMA synchronous=OFF")

    try:
        # Create schema
        conn.executescript(SCHEMA)

        # Stage 1: Genes (from NCBI)
        import_genes(conn, data_dir)

        if only_genes:
            logger.info("--only-genes flag set; stopping after genes table.")
            return

        # Stage 2-3: Local CSV imports (always available, no download needed)
        import_depmap(conn)
        import_tcga_expression(conn)
        import_tcga_mutation(conn)

        # Stage 4-5: External downloads (optional)
        if not only_local:
            if not skip_download:
                import_opentargets(conn, data_dir)
                import_chembl(conn, data_dir)
            else:
                logger.info("--skip-download: skipping Open Targets and ChEMBL")
        else:
            logger.info("--only-local: skipping Open Targets and ChEMBL")

        # Create indexes
        _report_stage("Creating indexes")
        t0 = time.time()
        for idx_sql in INDEXES:
            conn.execute(idx_sql)
        conn.commit()
        logger.info(f"  indexes created in {time.time() - t0:.1f}s")

        # Summary
        _report_stage("Build complete")
        for table in ["genes", "opentargets", "chembl_drugs",
                       "depmap_crispr", "tcga_expression", "tcga_mutation"]:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            logger.info(f"  {table:25s}: {count:>10,} rows")

        db_size = db_path.stat().st_size / 1024 / 1024
        logger.info(f"  database size: {db_size:.0f} MB")

    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build offline SQLite database for Target Assessment Tool"
    )
    parser.add_argument(
        "--skip-download", action="store_true",
        help="Skip Open Targets and ChEMBL downloads (import local files only)"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing database"
    )
    parser.add_argument(
        "--only-genes", action="store_true",
        help="Build only the genes table"
    )
    parser.add_argument(
        "--only-local", action="store_true",
        help="Import local CSV files only (DepMap + TCGA + genes)"
    )
    args = parser.parse_args()

    build_db(
        skip_download=args.skip_download,
        force=args.force,
        only_genes=args.only_genes,
        only_local=args.only_local,
    )
