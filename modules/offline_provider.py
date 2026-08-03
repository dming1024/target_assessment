"""
Offline Provider — SQLite-backed evidence queries.

Replaces all network API calls with local SQLite queries for sub-second
target assessment. Returns dicts compatible with existing API clients so
DataManager needs minimal changes.

Usage:
    provider = OfflineProvider()
    if provider.is_available():
        symbol, ensembl, name, synonyms = provider.resolve_gene("HER2")
        ot   = provider.query_ot(ensembl, "EFO_0000621")
        chem = provider.query_chembl(symbol)
        dep  = provider.query_depmap(symbol, "nsclc")
        expr = provider.query_tcga_expr(symbol, "nsclc")
        mut  = provider.query_tcga_mut(symbol, "nsclc")
"""

import logging
import sqlite3
from pathlib import Path
from typing import Optional, Tuple

from config import OFFLINE_DB, resolve_disease_categories

logger = logging.getLogger(__name__)

# ── Return shapes that mirror existing API clients ──────────────────────

def _empty_ot() -> dict:
    return {
        "opentargets_association": False,
        "opentargets_score": 0.0,
        "opentargets_evidence_count": 0,
        "genetic_association_score": 0.0,
        "somatic_mutation_score": 0.0,
        "known_drug_score": 0.0,
        "rna_expression_score": 0.0,
        "literature_score": 0.0,
        "affected_pathway_score": 0.0,
    }


def _empty_chembl() -> dict:
    return {
        "approved_drugs": 0,
        "clinical_candidates": 0,
        "active_compounds": 0,
        "modality_fit": "unknown",
        "chembl_target_id": None,
    }


def _empty_depmap() -> dict:
    return {
        "target_cancer_dependency": "unknown",
        "pan_cancer_rank": "unknown",
        "is_common_essential": False,
        "mutation_conditioned_dep": False,
        "depmap_mean_score": None,
        "depmap_percentile": None,
    }


def _empty_tcga_expr() -> dict:
    return {
        "tumor_expression": "unknown",
        "tumor_normal_diff": "unknown",
        "protein_evidence": False,
        "tissue_specificity": "unknown",
        "tcga_median_tpm": None,
        "tcga_log2fc": None,
    }


def _empty_tcga_mut() -> dict:
    return {
        "mutation_cnv_frequency": 0.0,
        "prognostic_associated": False,
        "tcga_mutation_freq": 0.0,
        "tcga_cnv_amp_freq": 0.0,
        "tcga_cnv_del_freq": 0.0,
    }


# ── Disease matching helpers ────────────────────────────────────────────

def _find_disease_row(
    conn: sqlite3.Connection,
    table: str,
    gene_col: str,
    disease_col: str,
    gene_symbol: str,
    disease: str,
    extra_cols: tuple = (),
    order_col: str = None,
    order_desc: bool = False,
) -> Optional[tuple]:
    """
    Match a (gene, disease) row in *table* replicating the priority logic:
      1. Category-based (resolve_disease_categories → IN clause)
         When order_col is given, fetch all matching rows and pick the best
         one (e.g. lowest chronos for DepMap, highest TPM for TCGA).
      2. Exact match
      3. Substring match
      4. Fallback: first row for the gene
    """
    cols = (gene_col, disease_col) + extra_cols
    col_list = ", ".join(cols)

    # 1. Category match
    category_diseases = resolve_disease_categories(disease)
    if category_diseases:
        placeholders = ",".join(["?"] * len(category_diseases))
        if order_col:
            # Fetch all candidate rows and pick best one
            direction = "DESC" if order_desc else "ASC"
            query = (
                f"SELECT {col_list} FROM {table} "
                f"WHERE {gene_col}=? AND {disease_col} IN ({placeholders}) "
                f"ORDER BY {order_col} {direction} "
                f"LIMIT 1"
            )
        else:
            query = (
                f"SELECT {col_list} FROM {table} "
                f"WHERE {gene_col}=? AND {disease_col} IN ({placeholders}) "
                f"LIMIT 1"
            )
        row = conn.execute(query, [gene_symbol] + category_diseases).fetchone()
        if row:
            return row

    # 2. Exact match (case-insensitive)
    row = conn.execute(
        f"SELECT {col_list} FROM {table} "
        f"WHERE {gene_col}=? AND LOWER({disease_col})=? "
        f"LIMIT 1",
        [gene_symbol, disease.lower()],
    ).fetchone()
    if row:
        return row

    # 3. Substring match
    like_pattern = f"%{disease.lower()}%"
    row = conn.execute(
        f"SELECT {col_list} FROM {table} "
        f"WHERE {gene_col}=? AND LOWER({disease_col}) LIKE ? "
        f"LIMIT 1",
        [gene_symbol, like_pattern],
    ).fetchone()
    if row:
        return row

    # 4. Fallback: any row for this gene
    return conn.execute(
        f"SELECT {col_list} FROM {table} WHERE {gene_col}=? LIMIT 1",
        [gene_symbol],
    ).fetchone()


# ── OfflineProvider ─────────────────────────────────────────────────────

class OfflineProvider:
    """SQLite-backed evidence provider for all 6 scoring dimensions."""

    def __init__(self, db_path: str = None):
        self._db_path = Path(db_path) if db_path else Path(OFFLINE_DB)
        self._conn: Optional[sqlite3.Connection] = None

    # ── Connection management ───────────────────────────────────────

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=OFF")
        return self._conn

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def is_available(self) -> bool:
        """Return True if the SQLite DB exists and has the expected tables."""
        if not self._db_path.exists():
            return False
        try:
            tables = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {r["name"] for r in tables}
            required = {"genes", "opentargets", "chembl_drugs",
                        "depmap_crispr", "tcga_expression", "tcga_mutation"}
            return required.issubset(table_names)
        except Exception:
            return False

    # ── Symbol normalization ────────────────────────────────────────

    def _normalize_symbol(self, symbol: str) -> str:
        """Resolve an alias to the official gene symbol, or return as-is."""
        resolved = self.resolve_gene(symbol)
        if resolved:
            return resolved[0]
        return symbol.upper()

    # ── Gene resolution ─────────────────────────────────────────────

    def resolve_gene(self, symbol: str) -> Optional[Tuple[str, str, str, str]]:
        """
        Look up a gene by symbol or alias.

        Returns:
            (official_symbol, ensembl_id, full_name, synonyms_json)
            or None if not found.
        """
        sym = symbol.upper()
        # Try primary key first
        row = self.conn.execute(
            "SELECT gene_symbol, ensembl_id, full_name, synonyms "
            "FROM genes WHERE gene_symbol=?",
            [sym],
        ).fetchone()
        if row:
            return (row["gene_symbol"], row["ensembl_id"] or "",
                    row["full_name"] or "", row["synonyms"] or "[]")

        # Try alias search
        row = self.conn.execute(
            "SELECT gene_symbol, ensembl_id, full_name, synonyms "
            "FROM genes WHERE aliases_lower LIKE ?",
            [f"%|{sym.lower()}|%"],
        ).fetchone()
        if row:
            return (row["gene_symbol"], row["ensembl_id"] or "",
                    row["full_name"] or "", row["synonyms"] or "[]")

        return None

    # ── Open Targets ────────────────────────────────────────────────

    def query_ot(self, ensembl_id: str, efo_id: str) -> dict:
        """Return OT association data (mirrors OpentargetsClient)."""
        if not ensembl_id or not efo_id:
            return _empty_ot()

        row = self.conn.execute(
            "SELECT * FROM opentargets WHERE ensembl_id=? AND efo_id=?",
            [ensembl_id, efo_id],
        ).fetchone()

        if not row:
            return _empty_ot()

        score = row["overall_score"] or 0.0
        return {
            "opentargets_association": score > 0.01,
            "opentargets_score": round(score, 4),
            "opentargets_evidence_count": row["evidence_count"] or 0,
            "genetic_association_score": round(row["genetic_association"] or 0.0, 4),
            "somatic_mutation_score": round(row["somatic_mutation"] or 0.0, 4),
            "known_drug_score": round(row["known_drug"] or 0.0, 4),
            "rna_expression_score": round(row["rna_expression"] or 0.0, 4),
            "literature_score": round(row["literature"] or 0.0, 4),
            "affected_pathway_score": round(row["affected_pathway"] or 0.0, 4),
        }

    # ── ChEMBL ──────────────────────────────────────────────────────

    def query_chembl(self, gene_symbol: str) -> dict:
        """Return ChEMBL drug counts (mirrors ChemblClient)."""
        row = self.conn.execute(
            "SELECT * FROM chembl_drugs WHERE gene_symbol=?",
            [gene_symbol.upper()],
        ).fetchone()

        if not row:
            return _empty_chembl()

        return {
            "approved_drugs": row["approved_drugs"] or 0,
            "clinical_candidates": row["clinical_candidates"] or 0,
            "active_compounds": row["active_compounds"] or 0,
            "modality_fit": row["modality_fit"] or "unknown",
            "chembl_target_id": row["chembl_target_id"] or None,
        }

    # ── DepMap ──────────────────────────────────────────────────────

    def query_depmap(self, gene_symbol: str, disease: str) -> dict:
        """Return DepMap dependency data (mirrors DepMapModule)."""
        gene = self._normalize_symbol(gene_symbol)
        row = _find_disease_row(
            self.conn, "depmap_crispr",
            gene_col="gene", disease_col="primary_disease",
            gene_symbol=gene, disease=disease,
            extra_cols=("mean_chronos_score", "pan_cancer_percentile",
                        "selectivity_category", "pan_cancer_mean_score"),
            order_col="mean_chronos_score",  # prefer strongest dependency (lowest)
            order_desc=False,
        )
        if not row:
            return _empty_depmap()

        chronos = row["mean_chronos_score"] or 0
        percentile = row["pan_cancer_percentile"] or 50
        selectivity = row["selectivity_category"] or "unknown"
        pan_mean = row["pan_cancer_mean_score"] or 0

        # Classify dependency strength
        if chronos < -0.5:
            dep_level = "strong"
        elif chronos < -0.3:
            dep_level = "moderate"
        elif chronos < -0.1:
            dep_level = "weak"
        else:
            dep_level = "weak"

        pan_cancer_rank = {
            "selective": "selective",
            "moderate_selective": "moderate_selective",
            "non_selective": "weak",
        }.get(selectivity, "unknown")
        is_common_essential = pan_mean < -0.8 and percentile < 5

        return {
            "target_cancer_dependency": dep_level,
            "pan_cancer_rank": pan_cancer_rank,
            "is_common_essential": is_common_essential,
            "mutation_conditioned_dep": False,
            "depmap_mean_score": round(chronos, 3),
            "depmap_percentile": round(percentile, 1),
        }

    # ── TCGA Expression ─────────────────────────────────────────────

    def query_tcga_expr(self, gene_symbol: str, disease: str) -> dict:
        """Return TCGA expression data (mirrors TCGAModule.query_expression)."""
        gene = self._normalize_symbol(gene_symbol)
        row = _find_disease_row(
            self.conn, "tcga_expression",
            gene_col="gene", disease_col="cancer_type",
            gene_symbol=gene, disease=disease,
            extra_cols=("median_tpm_tumor", "log2fc_tumor_normal",
                        "overexpression_category", "tumor_normal_diff_category",
                        "tissue_specificity"),
            order_col="median_tpm_tumor",  # prefer highest expression
            order_desc=True,
        )
        if not row:
            return _empty_tcga_expr()

        overexpr = row["overexpression_category"] or "unknown"
        return {
            "tumor_expression": overexpr,
            "tumor_normal_diff": row["tumor_normal_diff_category"] or "unknown",
            "protein_evidence": overexpr in ("high", "moderate"),
            "tissue_specificity": row["tissue_specificity"] or "unknown",
            "tcga_median_tpm": round(row["median_tpm_tumor"] or 0, 1),
            "tcga_log2fc": round(row["log2fc_tumor_normal"] or 0, 2),
        }

    # ── TCGA Mutation ───────────────────────────────────────────────

    def query_tcga_mut(self, gene_symbol: str, disease: str) -> dict:
        """Return TCGA mutation data (mirrors TCGAModule.query_mutation)."""
        gene = self._normalize_symbol(gene_symbol)
        row = _find_disease_row(
            self.conn, "tcga_mutation",
            gene_col="gene", disease_col="cancer_type",
            gene_symbol=gene, disease=disease,
            extra_cols=("total_alteration_freq", "mutation_freq",
                        "cnv_amp_freq", "cnv_del_freq", "prognostic_associated"),
            order_col="total_alteration_freq",  # prefer highest alteration
            order_desc=True,
        )
        if not row:
            return _empty_tcga_mut()

        return {
            "mutation_cnv_frequency": round(row["total_alteration_freq"] or 0, 3),
            "prognostic_associated": bool(row["prognostic_associated"] or 0),
            "tcga_mutation_freq": round(row["mutation_freq"] or 0, 3),
            "tcga_cnv_amp_freq": round(row["cnv_amp_freq"] or 0, 3),
            "tcga_cnv_del_freq": round(row["cnv_del_freq"] or 0, 3),
        }

    # ── Clinical competition (derived from ChEMBL + OT) ─────────────

    def query_clinical_competition(self, gene_symbol: str, ensembl_id: str,
                                   efo_id: str) -> dict:
        """
        Derive clinical-competition fields from ChEMBL + Open Targets.
        Replaces ClinicalTrials.gov API queries.
        """
        chembl = self.query_chembl(gene_symbol)
        approved = chembl.get("approved_drugs", 0)

        ot = _empty_ot()
        if ensembl_id and efo_id:
            ot = self.query_ot(ensembl_id, efo_id)

        # Differentiation opportunity:
        #   high  = no approved drugs targeting this gene in this disease
        #   moderate = some drugs, still room for differentiation
        #   low   = many approved drugs
        if approved == 0:
            diff_opp = "high"
        elif approved < 3:
            diff_opp = "moderate"
        else:
            diff_opp = "low"

        # Estimate active trials from known_drug score + approved drugs
        known_drug = ot.get("known_drug_score", 0)
        if known_drug > 0.5 and approved > 0:
            active_trials = max(approved * 3, 10)
        elif known_drug > 0.1 and approved > 0:
            active_trials = approved * 2
        else:
            active_trials = 0

        return {
            "approved_drugs_count": approved,
            "active_clinical_trials": active_trials,
            "differentiation_opportunity": diff_opp,
        }

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
