"""
TCGA Module - Expression and mutation data from local preprocessed files.

Reads preprocessed TCGA pan-cancer summaries and returns
expression and mutation evidence for scoring.
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from config import PROCESSED_DIR

logger = logging.getLogger(__name__)

# Expected columns in expression CSV:
#   gene, cancer_type, median_tpm_tumor, median_tpm_normal,
#   log2fc_tumor_normal, overexpression_category, tumor_normal_diff_category,
#   tissue_specificity
#
# Expected columns in mutation CSV:
#   gene, cancer_type, mutation_freq, cnv_amp_freq, cnv_del_freq,
#   total_alteration_freq, prognostic_associated


class TCGAModule:
    """Query preprocessed TCGA expression and mutation data."""

    def __init__(self, expr_path: str = None, mut_path: str = None):
        if expr_path:
            self._expr_path = Path(expr_path)
        else:
            self._expr_path = PROCESSED_DIR / "tcga_expression_summary.csv"

        if mut_path:
            self._mut_path = Path(mut_path)
        else:
            self._mut_path = PROCESSED_DIR / "tcga_mutation_summary.csv"

        self._expr_df: Optional[pd.DataFrame] = None
        self._mut_df: Optional[pd.DataFrame] = None

    @property
    def expr_df(self) -> pd.DataFrame:
        if self._expr_df is None:
            self._load_expression()
        return self._expr_df

    @property
    def mut_df(self) -> pd.DataFrame:
        if self._mut_df is None:
            self._load_mutation()
        return self._mut_df

    def _load_expression(self):
        if not self._expr_path.exists():
            logger.warning(f"TCGA expression file not found: {self._expr_path}")
            self._expr_df = pd.DataFrame()
            return
        self._expr_df = pd.read_csv(self._expr_path)
        self._expr_df["gene"] = self._expr_df["gene"].str.upper()
        logger.info(f"Loaded TCGA expression: {len(self._expr_df)} rows")

    def _load_mutation(self):
        if not self._mut_path.exists():
            logger.warning(f"TCGA mutation file not found: {self._mut_path}")
            self._mut_df = pd.DataFrame()
            return
        self._mut_df = pd.read_csv(self._mut_path)
        self._mut_df["gene"] = self._mut_df["gene"].str.upper()
        logger.info(f"Loaded TCGA mutation: {len(self._mut_df)} rows")

    def _find_match(self, df: pd.DataFrame, gene_symbol: str, disease: str):
        """Find best matching row for gene + disease."""
        gene_upper = gene_symbol.upper()
        disease_lower = disease.lower()

        gene_rows = df[df["gene"] == gene_upper]
        if gene_rows.empty:
            return None

        cancer_col = "cancer_type" if "cancer_type" in df.columns else "primary_disease"

        # Exact match
        for _, row in gene_rows.iterrows():
            if row[cancer_col].lower() == disease_lower:
                return row

        # Substring match
        for _, row in gene_rows.iterrows():
            rd = row[cancer_col].lower()
            if disease_lower in rd or rd in disease_lower:
                return row

        # Fallback: first row for this gene
        return gene_rows.iloc[0]

    def query_expression(self, gene_symbol: str, disease: str) -> dict:
        """
        Query TCGA expression data.

        Returns dict with:
            tumor_expression: "high" | "moderate" | "low" | "unknown"
            tumor_normal_diff: "significant" | "moderate" | "none" | "unknown"
            protein_evidence: bool
            tissue_specificity: "high" | "moderate" | "low" | "unknown"
        """
        if self.expr_df.empty:
            return self._empty_expression()

        row = self._find_match(self.expr_df, gene_symbol, disease)
        if row is None:
            logger.info(f"TCGA expr: no data for {gene_symbol}")
            return self._empty_expression()

        return {
            "tumor_expression": row.get("overexpression_category", "unknown"),
            "tumor_normal_diff": row.get("tumor_normal_diff_category", "unknown"),
            "protein_evidence": row.get("overexpression_category", "low") in ("high", "moderate"),
            "tissue_specificity": row.get("tissue_specificity", "unknown"),
            "tcga_median_tpm": round(row.get("median_tpm_tumor", 0), 1),
            "tcga_log2fc": round(row.get("log2fc_tumor_normal", 0), 2),
        }

    def query_mutation(self, gene_symbol: str, disease: str) -> dict:
        """
        Query TCGA mutation/CNV data.

        Returns dict with:
            target_cancer_overexpression: from expression context
            mutation_cnv_frequency: float
            prognostic_associated: bool
        """
        if self.mut_df.empty:
            return self._empty_mutation()

        row = self._find_match(self.mut_df, gene_symbol, disease)
        if row is None:
            logger.info(f"TCGA mut: no data for {gene_symbol}")
            return self._empty_mutation()

        return {
            "mutation_cnv_frequency": round(row.get("total_alteration_freq", 0), 3),
            "prognostic_associated": bool(row.get("prognostic_associated", False)),
            "tcga_mutation_freq": round(row.get("mutation_freq", 0), 3),
            "tcga_cnv_amp_freq": round(row.get("cnv_amp_freq", 0), 3),
            "tcga_cnv_del_freq": round(row.get("cnv_del_freq", 0), 3),
        }

    def _empty_expression(self) -> dict:
        return {
            "tumor_expression": "unknown",
            "tumor_normal_diff": "unknown",
            "protein_evidence": False,
            "tissue_specificity": "unknown",
            "tcga_median_tpm": None,
            "tcga_log2fc": None,
        }

    def _empty_mutation(self) -> dict:
        return {
            "mutation_cnv_frequency": 0.0,
            "prognostic_associated": False,
            "tcga_mutation_freq": 0.0,
            "tcga_cnv_amp_freq": 0.0,
            "tcga_cnv_del_freq": 0.0,
        }
