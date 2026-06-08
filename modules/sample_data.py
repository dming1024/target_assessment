"""
Sample target evidence data for MVP testing.

Contains pre-compiled evidence for 5 canonical targets across common cancer types.
This allows end-to-end testing without real API connections.
"""

# Sample evidence by (gene, cancer_type)
SAMPLE_EVIDENCE = {
    ("EGFR", "NSCLC"): {
        "target_overview": {
            "protein_class": "Receptor Tyrosine Kinase",
            "subcellular_location": "Cell membrane",
            "function_summary": (
                "EGFR is a transmembrane glycoprotein and member of the ErbB family of receptor "
                "tyrosine kinases. Upon ligand binding, EGFR activates downstream signaling cascades "
                "including RAS/RAF/MEK/ERK, PI3K/AKT, and JAK/STAT pathways, driving cell "
                "proliferation, survival, angiogenesis, and metastasis. EGFR mutations (e.g., L858R, "
                "exon 19 deletion) are common oncogenic drivers in NSCLC."
            ),
        },
        "disease_relevance": {
            "target_cancer_overexpression": "high",
            "prognostic_associated": True,
            "mutation_cnv_frequency": 0.15,
            "opentargets_association": True,
            "literature_level": "high",
        },
        "expression": {
            "tumor_expression": "high",
            "tumor_normal_diff": "significant",
            "protein_evidence": True,
            "tissue_specificity": "high",
        },
        "dependency": {
            "target_cancer_dependency": "strong",
            "pan_cancer_rank": "selective",
            "is_common_essential": False,
            "mutation_conditioned_dep": True,
        },
        "mechanism": {
            "relevant_pathway_count": 5,
            "mechanism_strength": "well_established",
            "connects_to_disease_hallmarks": True,
        },
        "druggability": {
            "approved_drugs": 8,
            "clinical_candidates": 20,
            "active_compounds": 200,
            "modality_fit": "strong",
        },
        "safety": {
            "normal_tissue_risk": "moderate",
            "is_common_essential": False,
            "critical_organ_expression": ["skin", "liver"],
        },
        "clinical_competition": {
            "approved_drugs_count": 8,
            "active_clinical_trials": 300,
            "differentiation_opportunity": "moderate",
        },
        "data_sources": {
            "TCGA": "Pan-Cancer Atlas, v36",
            "DepMap": "CRISPR Gene Effect, 24Q4",
            "Open Targets": "2024.12",
            "ChEMBL": "v34",
            "GTEx": "v10",
            "cBioPortal": "NSCLC cohort",
        },
    },

    ("ERBB2", "Breast Cancer"): {
        "target_overview": {
            "protein_class": "Receptor Tyrosine Kinase",
            "subcellular_location": "Cell membrane",
            "function_summary": (
                "ERBB2 (HER2) is a member of the EGFR family of receptor tyrosine kinases. "
                "It has no known direct ligand but is the preferred dimerization partner for other "
                "ErbB family members. ERBB2 amplification drives ~20% of breast cancers and is "
                "associated with aggressive disease. It is a validated therapeutic target with "
                "multiple approved antibody, ADC, and TKI drugs."
            ),
        },
        "disease_relevance": {
            "target_cancer_overexpression": "high",
            "prognostic_associated": True,
            "mutation_cnv_frequency": 0.20,
            "opentargets_association": True,
            "literature_level": "high",
        },
        "expression": {
            "tumor_expression": "high",
            "tumor_normal_diff": "significant",
            "protein_evidence": True,
            "tissue_specificity": "high",
        },
        "dependency": {
            "target_cancer_dependency": "strong",
            "pan_cancer_rank": "selective",
            "is_common_essential": False,
            "mutation_conditioned_dep": True,
        },
        "mechanism": {
            "relevant_pathway_count": 4,
            "mechanism_strength": "well_established",
            "connects_to_disease_hallmarks": True,
        },
        "druggability": {
            "approved_drugs": 5,
            "clinical_candidates": 15,
            "active_compounds": 100,
            "modality_fit": "strong",
        },
        "safety": {
            "normal_tissue_risk": "moderate",
            "is_common_essential": False,
            "critical_organ_expression": ["heart"],
        },
        "clinical_competition": {
            "approved_drugs_count": 5,
            "active_clinical_trials": 200,
            "differentiation_opportunity": "moderate",
        },
        "data_sources": {
            "TCGA": "Pan-Cancer Atlas, v36",
            "DepMap": "CRISPR Gene Effect, 24Q4",
            "Open Targets": "2024.12",
            "ChEMBL": "v34",
            "GTEx": "v10",
        },
    },

    ("CLDN18", "Gastric Cancer"): {
        "target_overview": {
            "protein_class": "Tight Junction Protein / Claudin Family",
            "subcellular_location": "Cell membrane (tight junctions)",
            "function_summary": (
                "CLDN18 (Claudin-18) is a tight junction protein with two splice variants: "
                "CLDN18.1 (lung-specific) and CLDN18.2 (stomach-specific). CLDN18.2 is highly "
                "expressed in gastric epithelium and ectopically expressed in gastric cancer, "
                "pancreatic cancer, and other solid tumors, making it a promising ADC and "
                "CAR-T target. Zolbetuximab (anti-CLDN18.2 antibody) has shown clinical benefit."
            ),
        },
        "disease_relevance": {
            "target_cancer_overexpression": "high",
            "prognostic_associated": True,
            "mutation_cnv_frequency": 0.02,
            "opentargets_association": True,
            "literature_level": "moderate",
        },
        "expression": {
            "tumor_expression": "high",
            "tumor_normal_diff": "significant",
            "protein_evidence": True,
            "tissue_specificity": "high",
        },
        "dependency": {
            "target_cancer_dependency": "moderate",
            "pan_cancer_rank": "selective",
            "is_common_essential": False,
            "mutation_conditioned_dep": False,
        },
        "mechanism": {
            "relevant_pathway_count": 2,
            "mechanism_strength": "partially_established",
            "connects_to_disease_hallmarks": True,
        },
        "druggability": {
            "approved_drugs": 0,
            "clinical_candidates": 5,
            "active_compounds": 15,
            "modality_fit": "strong",
        },
        "safety": {
            "normal_tissue_risk": "low",
            "is_common_essential": False,
            "critical_organ_expression": [],
        },
        "clinical_competition": {
            "approved_drugs_count": 0,
            "active_clinical_trials": 15,
            "differentiation_opportunity": "high",
        },
        "data_sources": {
            "TCGA": "Pan-Cancer Atlas, v36",
            "DepMap": "CRISPR Gene Effect, 24Q4",
            "Open Targets": "2024.12",
            "ChEMBL": "v34",
            "GTEx": "v10",
            "ClinicalTrials": "2025.01",
        },
    },

    ("MUC1", "Pan-cancer"): {
        "target_overview": {
            "protein_class": "Mucin / Transmembrane Glycoprotein",
            "subcellular_location": "Cell membrane (apical), secreted",
            "function_summary": (
                "MUC1 is a large transmembrane mucin glycoprotein expressed on the apical surface "
                "of epithelial cells. In cancer, MUC1 is overexpressed, aberrantly glycosylated, "
                "and loses its apical polarization, creating tumor-specific epitopes. It is a "
                "validated immunotherapy and ADC target, though ubiquitous epithelial expression "
                "complicates safety."
            ),
        },
        "disease_relevance": {
            "target_cancer_overexpression": "high",
            "prognostic_associated": True,
            "mutation_cnv_frequency": 0.03,
            "opentargets_association": True,
            "literature_level": "high",
        },
        "expression": {
            "tumor_expression": "high",
            "tumor_normal_diff": "moderate",
            "protein_evidence": True,
            "tissue_specificity": "moderate",
        },
        "dependency": {
            "target_cancer_dependency": "moderate",
            "pan_cancer_rank": "moderate_selective",
            "is_common_essential": False,
            "mutation_conditioned_dep": False,
        },
        "mechanism": {
            "relevant_pathway_count": 3,
            "mechanism_strength": "partially_established",
            "connects_to_disease_hallmarks": True,
        },
        "druggability": {
            "approved_drugs": 0,
            "clinical_candidates": 8,
            "active_compounds": 30,
            "modality_fit": "strong",
        },
        "safety": {
            "normal_tissue_risk": "moderate",
            "is_common_essential": False,
            "critical_organ_expression": ["pancreas", "lung"],
        },
        "clinical_competition": {
            "approved_drugs_count": 0,
            "active_clinical_trials": 20,
            "differentiation_opportunity": "moderate",
        },
        "data_sources": {
            "TCGA": "Pan-Cancer Atlas, v36",
            "DepMap": "CRISPR Gene Effect, 24Q4",
            "Open Targets": "2024.12",
            "ChEMBL": "v34",
            "GTEx": "v10",
            "ClinicalTrials": "2025.01",
        },
    },

    ("BRCA1", "Ovarian Cancer"): {
        "target_overview": {
            "protein_class": "Tumor Suppressor / DNA Repair Protein",
            "subcellular_location": "Nucleus (also cytoplasmic)",
            "function_summary": (
                "BRCA1 is a tumor suppressor gene that encodes a protein critical for homologous "
                "recombination DNA repair. Germline BRCA1 mutations confer high risk for breast "
                "and ovarian cancers. In BRCA1-mutant tumors, PARP inhibitors exploit synthetic "
                "lethality. Unlike oncogenes, BRCA1 itself is not a traditional drug target; "
                "its loss-of-function status is used for patient stratification and PARP inhibitor therapy."
            ),
        },
        "disease_relevance": {
            "target_cancer_overexpression": "low",
            "prognostic_associated": True,
            "mutation_cnv_frequency": 0.12,
            "opentargets_association": True,
            "literature_level": "high",
        },
        "expression": {
            "tumor_expression": "low",
            "tumor_normal_diff": "none",
            "protein_evidence": True,
            "tissue_specificity": "low",
        },
        "dependency": {
            "target_cancer_dependency": "moderate",
            "pan_cancer_rank": "selective",
            "is_common_essential": False,
            "mutation_conditioned_dep": True,
        },
        "mechanism": {
            "relevant_pathway_count": 3,
            "mechanism_strength": "well_established",
            "connects_to_disease_hallmarks": True,
        },
        "druggability": {
            "approved_drugs": 0,
            "clinical_candidates": 0,
            "active_compounds": 5,
            "modality_fit": "weak",
        },
        "safety": {
            "normal_tissue_risk": "high",
            "is_common_essential": False,
            "critical_organ_expression": ["breast", "ovary"],
        },
        "clinical_competition": {
            "approved_drugs_count": 0,
            "active_clinical_trials": 50,
            "differentiation_opportunity": "high",
        },
        "data_sources": {
            "TCGA": "Pan-Cancer Atlas, v36",
            "DepMap": "CRISPR Gene Effect, 24Q4",
            "Open Targets": "2024.12",
            "ChEMBL": "v34",
            "GTEx": "v10",
            "ClinicalTrials": "2025.01",
        },
    },

    ("KRAS", "Pancreatic Cancer"): {
        "target_overview": {
            "protein_class": "Small GTPase",
            "subcellular_location": "Cell membrane (inner leaflet)",
            "function_summary": (
                "KRAS is a small GTPase that acts as a molecular switch in the RAS/RAF/MEK/ERK "
                "signaling cascade. KRAS mutations (especially G12D, G12V, G12C) are the most "
                "common oncogenic drivers in pancreatic, colorectal, and lung cancers. KRAS was "
                "historically considered 'undruggable' until the recent development of covalent "
                "G12C inhibitors (sotorasib, adagrasib) and pan-KRAS approaches."
            ),
        },
        "disease_relevance": {
            "target_cancer_overexpression": "high",
            "prognostic_associated": True,
            "mutation_cnv_frequency": 0.90,
            "opentargets_association": True,
            "literature_level": "high",
        },
        "expression": {
            "tumor_expression": "high",
            "tumor_normal_diff": "moderate",
            "protein_evidence": True,
            "tissue_specificity": "low",
        },
        "dependency": {
            "target_cancer_dependency": "strong",
            "pan_cancer_rank": "selective",
            "is_common_essential": False,
            "mutation_conditioned_dep": True,
        },
        "mechanism": {
            "relevant_pathway_count": 5,
            "mechanism_strength": "well_established",
            "connects_to_disease_hallmarks": True,
        },
        "druggability": {
            "approved_drugs": 2,
            "clinical_candidates": 10,
            "active_compounds": 50,
            "modality_fit": "moderate",
        },
        "safety": {
            "normal_tissue_risk": "moderate",
            "is_common_essential": False,
            "critical_organ_expression": ["intestine", "lung"],
        },
        "clinical_competition": {
            "approved_drugs_count": 2,
            "active_clinical_trials": 100,
            "differentiation_opportunity": "high",
        },
        "data_sources": {
            "TCGA": "Pan-Cancer Atlas, v36",
            "DepMap": "CRISPR Gene Effect, 24Q4",
            "Open Targets": "2024.12",
            "ChEMBL": "v34",
            "GTEx": "v10",
            "ClinicalTrials": "2025.01",
        },
    },
}

# List of all available (gene, cancer) pairs in sample data
SAMPLE_PAIRS = list(SAMPLE_EVIDENCE.keys())
