"""
Data Manager - 数据管理模块

Coordinates evidence collection from all data sources:
- Real-time APIs: Open Targets, ChEMBL, ClinicalTrials.gov
- Local files: DepMap, TCGA
- Sample data: Fallback for known targets
- Generic template: Last-resort fallback
"""

import logging
from typing import Dict, Optional

from modules.sample_data import SAMPLE_EVIDENCE, SAMPLE_PAIRS
from modules.opentargets_client import OpentargetsClient
from modules.chembl_client import ChemblClient
from modules.clinicaltrials_client import ClinicaltrialsClient
from modules.depmap_module import DepMapModule
from modules.tcga_module import TCGAModule
from config import EFO_DISEASE_MAP

logger = logging.getLogger(__name__)


class DataManager:
    """
    Central data coordinator for target assessment.

    Evidence collection priority:
    1. Real APIs + local data (primary)
    2. Sample data enrichment (fills gaps for known targets)
    3. Generic template (last resort for unknown targets)
    """

    def __init__(self):
        self._sample_cache = SAMPLE_EVIDENCE
        # Lazy-init clients
        self._ot: Optional[OpentargetsClient] = None
        self._chembl: Optional[ChemblClient] = None
        self._ct: Optional[ClinicaltrialsClient] = None
        self._depmap: Optional[DepMapModule] = None
        self._tcga: Optional[TCGAModule] = None

    @property
    def ot(self) -> OpentargetsClient:
        if self._ot is None:
            self._ot = OpentargetsClient()
        return self._ot

    @property
    def chembl(self) -> ChemblClient:
        if self._chembl is None:
            self._chembl = ChemblClient()
        return self._chembl

    @property
    def ct(self) -> ClinicaltrialsClient:
        if self._ct is None:
            self._ct = ClinicaltrialsClient()
        return self._ct

    @property
    def depmap(self) -> DepMapModule:
        if self._depmap is None:
            self._depmap = DepMapModule()
        return self._depmap

    @property
    def tcga(self) -> TCGAModule:
        if self._tcga is None:
            self._tcga = TCGAModule()
        return self._tcga

    def collect_evidence(
        self,
        gene_symbol: str,
        disease: str,
        scenario: str = "general",
        ensembl_id: str = "",
    ) -> dict:
        """
        Collect all available evidence for a target gene in a specific disease.

        Args:
            gene_symbol: Official HGNC gene symbol
            disease: Disease or cancer type
            scenario: Assessment scenario
            ensembl_id: Ensembl gene ID (ENSG...) for API queries

        Returns:
            Structured evidence dictionary
        """
        gene_upper = gene_symbol.upper()

        # 1. Build evidence from real data sources
        evidence = self._build_from_real_sources(gene_upper, disease, ensembl_id)

        # 2. Enrich with sample data if available (fills manually curated fields)
        sample = self._get_sample_evidence(gene_upper, disease)
        if sample:
            evidence = self._merge_evidence(evidence, sample)
            logger.info(f"Enriched with sample data for {gene_upper} in {disease}")

        # 3. Apply fallback for any still-empty dimensions
        evidence = self._ensure_complete(evidence, gene_upper, disease)

        return evidence

    def _build_from_real_sources(
        self, gene_symbol: str, disease: str, ensembl_id: str
    ) -> dict:
        """Build evidence dict from real APIs and local data."""
        sources = []

        # --- Open Targets ---
        ot_result = {}
        efo_id = self._resolve_efo_id(disease)
        if ensembl_id and efo_id:
            try:
                ot_result = self.ot.query_association(
                    ensembl_id=ensembl_id,
                    disease_efo_id=efo_id,
                    gene_symbol=gene_symbol,
                    disease_name=disease,
                )
                sources.append(f"Open Targets ({ot_result.get('opentargets_score', 0):.3f})")
            except Exception as e:
                logger.warning(f"Open Targets query failed: {e}")
        else:
            logger.info(
                f"Skipping Open Targets: ensembl_id={ensembl_id}, efo_id={efo_id}"
            )

        # --- ChEMBL ---
        chembl_result = {}
        try:
            chembl_result = self.chembl.query_target(gene_symbol)
            sources.append(f"ChEMBL (approved={chembl_result.get('approved_drugs', 0)})")
        except Exception as e:
            logger.warning(f"ChEMBL query failed: {e}")

        # --- ClinicalTrials.gov ---
        ct_result = {}
        try:
            ct_result = self.ct.query_trial_count(gene_symbol, disease)
            sources.append(f"ClinicalTrials.gov ({ct_result.get('active_clinical_trials', 0)} trials)")
        except Exception as e:
            logger.warning(f"ClinicalTrials.gov query failed: {e}")

        # --- DepMap ---
        depmap_result = {}
        try:
            depmap_result = self.depmap.query(gene_symbol, disease)
            sources.append(f"DepMap (dep={depmap_result.get('target_cancer_dependency', 'N/A')})")
        except Exception as e:
            logger.warning(f"DepMap query failed: {e}")

        # --- TCGA ---
        tcga_expr = {}
        tcga_mut = {}
        try:
            tcga_expr = self.tcga.query_expression(gene_symbol, disease)
            tcga_mut = self.tcga.query_mutation(gene_symbol, disease)
            sources.append(f"TCGA (expr={tcga_expr.get('tumor_expression', 'N/A')})")
        except Exception as e:
            logger.warning(f"TCGA query failed: {e}")

        # --- Build evidence blocks ---

        # Disease relevance: combine Open Targets + TCGA mutation
        disease_relevance = {
            "target_cancer_overexpression": tcga_expr.get(
                "tumor_expression",
                self._infer_overexpression(ot_result, tcga_mut),
            ),
            "prognostic_associated": tcga_mut.get("prognostic_associated", False),
            "mutation_cnv_frequency": tcga_mut.get("mutation_cnv_frequency", 0.0),
            "opentargets_association": ot_result.get("opentargets_association", False),
            "literature_level": self._infer_literature_level(ot_result),
            # Additional fields for reporting
            "opentargets_score": ot_result.get("opentargets_score", 0.0),
            "tcga_mutation_freq": tcga_mut.get("tcga_mutation_freq", 0.0),
            "tcga_cnv_amp_freq": tcga_mut.get("tcga_cnv_amp_freq", 0.0),
        }

        # Expression: from TCGA expression data
        expression = {
            "tumor_expression": tcga_expr.get("tumor_expression", "unknown"),
            "tumor_normal_diff": tcga_expr.get("tumor_normal_diff", "unknown"),
            "protein_evidence": tcga_expr.get("protein_evidence", False),
            "tissue_specificity": tcga_expr.get("tissue_specificity", "unknown"),
            "tcga_median_tpm": tcga_expr.get("tcga_median_tpm"),
            "tcga_log2fc": tcga_expr.get("tcga_log2fc"),
        }

        # Dependency: from DepMap
        dependency = {
            "target_cancer_dependency": depmap_result.get("target_cancer_dependency", "unknown"),
            "pan_cancer_rank": depmap_result.get("pan_cancer_rank", "unknown"),
            "is_common_essential": depmap_result.get("is_common_essential", False),
            "mutation_conditioned_dep": depmap_result.get("mutation_conditioned_dep", False),
            "depmap_mean_score": depmap_result.get("depmap_mean_score"),
            "depmap_percentile": depmap_result.get("depmap_percentile"),
        }

        # Mechanism: from Open Targets pathway scores + literature
        mechanism = {
            "relevant_pathway_count": self._count_pathways(ot_result),
            "mechanism_strength": self._infer_mechanism_strength(ot_result),
            "connects_to_disease_hallmarks": ot_result.get("opentargets_score", 0) > 0.1,
            "genetic_association_score": ot_result.get("genetic_association_score", 0.0),
            "somatic_mutation_score": ot_result.get("somatic_mutation_score", 0.0),
        }

        # Druggability: from ChEMBL
        druggability = {
            "approved_drugs": chembl_result.get("approved_drugs", 0),
            "clinical_candidates": chembl_result.get("clinical_candidates", 0),
            "active_compounds": chembl_result.get("active_compounds", 0),
            "modality_fit": chembl_result.get("modality_fit", "unknown"),
            "chembl_target_id": chembl_result.get("chembl_target_id"),
        }

        # Safety: from TCGA expression + DepMap common essential
        safety = {
            "normal_tissue_risk": self._infer_normal_risk(tcga_expr, depmap_result),
            "is_common_essential": depmap_result.get("is_common_essential", False),
            "critical_organ_expression": [],
        }

        # Clinical competition: from ClinicalTrials.gov + ChEMBL
        clinical_competition = {
            "approved_drugs_count": chembl_result.get("approved_drugs", 0),
            "active_clinical_trials": ct_result.get("active_clinical_trials", 0),
            "differentiation_opportunity": ct_result.get(
                "differentiation_opportunity", "unknown"
            ),
        }

        # Target overview
        target_overview = {
            "protein_class": "",
            "subcellular_location": "",
            "function_summary": "",
        }

        return {
            "target_overview": target_overview,
            "disease_relevance": disease_relevance,
            "expression": expression,
            "dependency": dependency,
            "mechanism": mechanism,
            "druggability": druggability,
            "safety": safety,
            "clinical_competition": clinical_competition,
            "data_sources": {"real_sources": sources},
        }

    # ------------------------------------------------------------------
    # Helpers: infer qualitative fields from quantitative API results
    # ------------------------------------------------------------------

    def _infer_overexpression(self, ot_result: dict, tcga_mut: dict) -> str:
        """Infer overexpression category from Open Targets expression score."""
        score = ot_result.get("rna_expression_score", 0)
        if score > 0.3:
            return "high"
        elif score > 0.1:
            return "moderate"
        elif score > 0:
            return "low"
        return "unknown"

    def _infer_literature_level(self, ot_result: dict) -> str:
        """Infer literature evidence level from Open Targets."""
        score = ot_result.get("literature_score", 0)
        if score > 0.5:
            return "high"
        elif score > 0.1:
            return "moderate"
        elif score > 0:
            return "low"
        return "unknown"

    def _count_pathways(self, ot_result: dict) -> int:
        """Count pathways with evidence from Open Targets datatype scores."""
        pathway_count = 0
        if ot_result.get("genetic_association_score", 0) > 0.01:
            pathway_count += 1
        if ot_result.get("somatic_mutation_score", 0) > 0.01:
            pathway_count += 1
        if ot_result.get("affected_pathway_score", 0) > 0.01:
            pathway_count += 1
        if ot_result.get("known_drug_score", 0) > 0.01:
            pathway_count += 1
        return pathway_count

    def _infer_mechanism_strength(self, ot_result: dict) -> str:
        """Infer mechanism strength from overall Open Targets association."""
        score = ot_result.get("opentargets_score", 0)
        if score > 0.5:
            return "well_established"
        elif score > 0.2:
            return "partially_established"
        elif score > 0:
            return "limited"
        return "unknown"

    def _infer_normal_risk(self, tcga_expr: dict, depmap_result: dict) -> str:
        """Infer normal tissue safety risk."""
        # High tumor-normal difference suggests lower normal tissue expression
        tn_diff = tcga_expr.get("tumor_normal_diff", "unknown")
        is_common = depmap_result.get("is_common_essential", False)

        if is_common:
            return "high"
        if tn_diff == "significant":
            return "low"
        elif tn_diff == "moderate":
            return "moderate"
        elif tn_diff == "none":
            return "high"
        return "unknown"

    # ------------------------------------------------------------------
    # EFO disease ID resolution
    # ------------------------------------------------------------------

    def _resolve_efo_id(self, disease: str) -> str:
        """Resolve a disease name to an EFO ID via substring matching."""
        disease_lower = disease.lower()

        # Exact match
        if disease_lower in EFO_DISEASE_MAP:
            return EFO_DISEASE_MAP[disease_lower]

        # Substring match (longest match first)
        matches = []
        for name, efo_id in EFO_DISEASE_MAP.items():
            if name in disease_lower or disease_lower in name:
                matches.append((len(name), efo_id))

        if matches:
            matches.sort(reverse=True)
            efo_id = matches[0][1]
            logger.info(f"Resolved '{disease}' → {efo_id}")
            return efo_id

        logger.warning(f"Could not resolve EFO ID for disease: {disease}")
        return ""

    # ------------------------------------------------------------------
    # Sample data & generic fallback
    # ------------------------------------------------------------------

    def _get_sample_evidence(self, gene_symbol: str, disease: str) -> Optional[dict]:
        """Look up sample evidence with flexible matching."""
        key = (gene_symbol.upper(), disease)
        if key in self._sample_cache:
            return self._sample_cache[key]

        # Flexible matching
        disease_lower = disease.lower()
        gene_matches = []
        for (g, d), ev in self._sample_cache.items():
            if g == gene_symbol.upper():
                gene_matches.append((d, ev))

        for d, ev in gene_matches:
            if d.lower() == disease_lower:
                return ev
        for d, ev in gene_matches:
            if disease_lower in d.lower() or d.lower() in disease_lower:
                return ev

        return gene_matches[0][1] if gene_matches else None

    def _merge_evidence(self, real: dict, sample: dict) -> dict:
        """
        Merge sample data into real evidence.
        Sample data provides manually curated fields (target_overview, etc.)
        that APIs don't cover. Real data takes priority for quantitative fields.
        """
        merged = dict(real)

        # Use sample's target_overview (manually curated)
        if sample.get("target_overview"):
            merged["target_overview"] = sample["target_overview"]

        # For each dimension, fill gaps with sample data
        for dim in [
            "disease_relevance", "expression", "dependency", "mechanism",
            "druggability", "safety", "clinical_competition",
        ]:
            if dim in sample:
                for key, value in sample[dim].items():
                    # Fill gaps: real data takes priority if present and not unknown/empty
                    current = merged.get(dim, {}).get(key)
                    if current in (None, "", "unknown", 0, 0.0, False) or (isinstance(current, list) and len(current) == 0):
                        merged.setdefault(dim, {})[key] = value

        # Merge data_sources
        if "data_sources" in sample:
            existing_sources = merged.get("data_sources", {})
            merged["data_sources"] = {**sample["data_sources"], **existing_sources}

        return merged

    def _ensure_complete(self, evidence: dict, gene_symbol: str, disease: str) -> dict:
        """Ensure all required fields exist with at least a default value."""
        defaults = {
            "target_overview": {
                "protein_class": "",
                "subcellular_location": "",
                "function_summary": "",
            },
            "disease_relevance": {
                "target_cancer_overexpression": "unknown",
                "prognostic_associated": False,
                "mutation_cnv_frequency": 0.0,
                "opentargets_association": False,
                "literature_level": "unknown",
            },
            "expression": {
                "tumor_expression": "unknown",
                "tumor_normal_diff": "unknown",
                "protein_evidence": False,
                "tissue_specificity": "unknown",
            },
            "dependency": {
                "target_cancer_dependency": "unknown",
                "pan_cancer_rank": "unknown",
                "is_common_essential": False,
                "mutation_conditioned_dep": False,
            },
            "mechanism": {
                "relevant_pathway_count": 0,
                "mechanism_strength": "unknown",
                "connects_to_disease_hallmarks": False,
            },
            "druggability": {
                "approved_drugs": 0,
                "clinical_candidates": 0,
                "active_compounds": 0,
                "modality_fit": "unknown",
            },
            "safety": {
                "normal_tissue_risk": "unknown",
                "is_common_essential": False,
                "critical_organ_expression": [],
            },
            "clinical_competition": {
                "approved_drugs_count": 0,
                "active_clinical_trials": 0,
                "differentiation_opportunity": "unknown",
            },
        }

        for dim, dim_defaults in defaults.items():
            if dim not in evidence:
                evidence[dim] = dim_defaults
            else:
                for key, default_val in dim_defaults.items():
                    if key not in evidence[dim]:
                        evidence[dim][key] = default_val

        if "data_sources" not in evidence:
            evidence["data_sources"] = {}

        return evidence

    def list_available_targets(self) -> list:
        """Return list of (gene, disease) pairs with sample data available."""
        return [
            {"gene": g, "disease": d}
            for (g, d) in SAMPLE_PAIRS
        ]
