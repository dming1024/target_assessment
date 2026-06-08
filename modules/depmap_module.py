"""
DepMap Module - CRISPR dependency data from local preprocessed files.

Reads preprocessed DepMap CRISPR gene effect scores and returns
gene-level dependency summaries for scoring.
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from config import PROCESSED_DIR

logger = logging.getLogger(__name__)

# Expected columns in the preprocessed CSV:
#   gene, primary_disease, mean_chronos_score, num_cell_lines,
#   pan_cancer_mean_score, pan_cancer_percentile, selectivity_category
#
# Chronos scores: more negative = stronger dependency (typical cutoff: < -0.5 = strong)
# selectivity_category: "selective", "moderate_selective", "weak", "pan_essential"


class DepMapModule:
    """Query preprocessed DepMap CRISPR dependency data."""

    def __init__(self, data_path: str = None):
        if data_path:
            self._path = Path(data_path)
        else:
            self._path = PROCESSED_DIR / "depmap_crispr_summary.csv"
        self._df: Optional[pd.DataFrame] = None

    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            self._load()
        return self._df

    def _load(self):
        if not self._path.exists():
            logger.warning(f"DepMap data file not found: {self._path}")
            self._df = pd.DataFrame()
            return
        self._df = pd.read_csv(self._path)
        self._df["gene"] = self._df["gene"].str.upper()
        logger.info(f"Loaded DepMap data: {len(self._df)} rows, {self._df['gene'].nunique()} genes")

    def query(self, gene_symbol: str, disease: str) -> dict:
        """
        Query DepMap dependency data for a gene in a specific disease context.

        Returns a dict with:
            target_cancer_dependency: "strong" | "moderate" | "weak" | "unknown"
            pan_cancer_rank: "selective" | "moderate_selective" | "pan_essential" | "unknown"
            is_common_essential: bool
            mutation_conditioned_dep: bool (from context, DepMap alone can't determine this)
            depmap_mean_score: float | None
            depmap_percentile: float | None
        """
        if self.df.empty:
            return self._empty_result()

        gene_upper = gene_symbol.upper()
        disease_lower = disease.lower()

        gene_rows = self.df[self.df["gene"] == gene_upper]
        if gene_rows.empty:
            logger.info(f"DepMap: no data for {gene_symbol}")
            return self._empty_result()

        # Try exact disease match
        match = None
        for _, row in gene_rows.iterrows():
            if row["primary_disease"].lower() == disease_lower:
                match = row
                break

        # Try substring match
        if match is None:
            for _, row in gene_rows.iterrows():
                rd = row["primary_disease"].lower()
                if disease_lower in rd or rd in disease_lower:
                    match = row
                    break

        # Fall back to pan-cancer summary
        if match is None:
            match = gene_rows.iloc[0]
            logger.info(f"DepMap: using pan-cancer data for {gene_symbol} (no {disease} match)")

        chronos = match["mean_chronos_score"]
        percentile = match.get("pan_cancer_percentile", 50)
        selectivity = match.get("selectivity_category", "unknown")

        # Classify dependency strength from Chronos score
        if chronos < -0.5:
            dep_level = "strong"
        elif chronos < -0.3:
            dep_level = "moderate"
        elif chronos < -0.1:
            dep_level = "weak"
        else:
            dep_level = "weak"

        # Map selectivity
        pan_cancer_rank = selectivity if selectivity in ("selective", "moderate_selective", "weak") else "unknown"

        # Common essential check: very strong pan-cancer dependency
        pan_mean = match.get("pan_cancer_mean_score", 0)
        is_common_essential = pan_mean < -0.8 and percentile < 5

        return {
            "target_cancer_dependency": dep_level,
            "pan_cancer_rank": pan_cancer_rank,
            "is_common_essential": is_common_essential,
            "mutation_conditioned_dep": False,  # requires mutation context
            "depmap_mean_score": round(chronos, 3),
            "depmap_percentile": round(percentile, 1),
        }

    def _empty_result(self) -> dict:
        return {
            "target_cancer_dependency": "unknown",
            "pan_cancer_rank": "unknown",
            "is_common_essential": False,
            "mutation_conditioned_dep": False,
            "depmap_mean_score": None,
            "depmap_percentile": None,
        }
