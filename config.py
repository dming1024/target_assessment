"""
Target Assessment Tool - Configuration
靶点价值评估器 - 配置文件
"""

import os
from pathlib import Path

# Project paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OFFLINE_DB = PROCESSED_DIR / "target_assessment.db"
CACHE_DIR = DATA_DIR / "cache"
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUTS_DIR = BASE_DIR / "outputs"
REPORTS_DIR = OUTPUTS_DIR / "reports"
TABLES_DIR = OUTPUTS_DIR / "tables"

# Ensure directories exist
for d in [RAW_DIR, PROCESSED_DIR, CACHE_DIR, REPORTS_DIR, TABLES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# API endpoints
MYGENE_API = "https://mygene.info/v3"
OPENTARGETS_API = "https://api.platform.opentargets.org/api/v4/graphql"
CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"

# EFO disease name → EFO ID mappings (for Open Targets API)
# Users input free-text disease names; we map them to EFO IDs via substring match.
EFO_DISEASE_MAP = {
    "nsclc": "EFO_0000621",
    "non-small cell lung": "EFO_0000621",
    "non small cell lung": "EFO_0000621",
    "lung adenocarcinoma": "EFO_0000571",
    "lung cancer": "EFO_0001071",
    "breast cancer": "EFO_0000305",
    "breast carcinoma": "EFO_0000305",
    "gastric cancer": "EFO_0000503",
    "stomach cancer": "EFO_0000503",
    "ovarian cancer": "EFO_0001075",
    "ovarian carcinoma": "EFO_0001075",
    "pancreatic cancer": "EFO_0002617",
    "pancreatic adenocarcinoma": "EFO_0002617",
    "colorectal cancer": "EFO_0000363",
    "colon cancer": "EFO_0000363",
    "melanoma": "EFO_0000756",
    "skin melanoma": "EFO_0000756",
    "aml": "EFO_0000222",
    "acute myeloid leukemia": "EFO_0000222",
    "prostate cancer": "EFO_0000673",
    "hepatocellular carcinoma": "EFO_0000182",
    "liver cancer": "EFO_0000182",
    "glioblastoma": "EFO_0000519",
    "glioma": "EFO_0000327",
    "bladder cancer": "EFO_0000292",
    "renal cell carcinoma": "EFO_0000681",
    "kidney cancer": "EFO_0000681",
}

# Disease category mapping — maps specific DepMap/TCGA disease names to broad categories.
# Categories align with EFO_DISEASE_MAP where possible.
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
    "colorectal_cancer": [
        "Colorectal Adenocarcinoma",
    ],
    "gastric_cancer": [
        "Esophagogastric Adenocarcinoma",
        "Esophageal Squamous Cell Carcinoma",
    ],
    "ovarian_cancer": [
        "Ovarian Epithelial Tumor",
        "Ovarian Cancer, Other",
        "Ovarian Germ Cell Tumor",
        "Sex Cord Stromal Tumor",
    ],
    "pancreatic_cancer": [
        "Pancreatic Adenocarcinoma",
        "Adenosquamous Carcinoma of the Pancreas",
        "Pancreatic Neuroendocrine Tumor",
    ],
    "melanoma": [
        "Melanoma",
        "Ocular Melanoma",
        "Mucosal Melanoma of the Vulva/Vagina",
        "Cutaneous Squamous Cell Carcinoma",
        "Merkel Cell Carcinoma",
    ],
    "leukemia": [
        "Acute Myeloid Leukemia",
        "Acute Leukemias of Ambiguous Lineage",
        "B-Cell Acute Lymphoblastic Leukemia",
        "T-Lymphoblastic Leukemia/Lymphoma",
        "Myeloproliferative Neoplasms",
    ],
    "lymphoma": [
        "Non-Hodgkin Lymphoma",
        "Hodgkin Lymphoma",
        "Mature B-Cell Neoplasms",
        "Mature T and NK Neoplasms",
    ],
    "brain_cns": [
        "Diffuse Glioma",
        "Adult-Type Diffuse Glioma",
        "Neuroblastoma",
        "Embryonal Tumor",
        "Meningothelial Tumor",
        "Rhabdoid Cancer",
        "Retinoblastoma",
        "Chordoma",
    ],
    "head_neck": [
        "Head and Neck Squamous Cell Carcinoma",
        "Head and Neck Carcinoma, Other",
        "Salivary Carcinoma",
    ],
    "liver_cancer": [
        "Hepatocellular Carcinoma",
        "Hepatoblastoma",
        "Hepatocellular Carcinoma plus Intrahepatic Cholangiocarcinoma",
    ],
    "renal_cancer": [
        "Renal Cell Carcinoma",
        "Wilms' Tumor",
    ],
    "bladder_cancer": [
        "Bladder Urothelial Carcinoma",
        "Bladder Squamous Cell Carcinoma",
        "Urethral Cancer",
    ],
    "prostate_cancer": [
        "Prostate Adenocarcinoma",
        "Prostate Neuroendocrine Carcinoma",
        "Prostate Small Cell Carcinoma",
    ],
    "sarcoma": [
        "Ewing Sarcoma",
        "Osteosarcoma",
        "Rhabdomyosarcoma",
        "Liposarcoma",
        "Leiomyosarcoma",
        "Synovial Sarcoma",
        "Chondrosarcoma",
        "Fibrosarcoma",
        "Clear Cell Sarcoma",
        "Epithelioid Sarcoma",
        "Myxofibrosarcoma",
        "CIC-DUX4 Sarcoma",
        "Alveolar Soft Part Sarcoma",
        "Sarcoma, NOS",
        "Undifferentiated Pleomorphic Sarcoma/Malignant Fibrous Histiocytoma/High-Grade Spindle Cell Sarcoma",
        "Desmoid/Aggressive Fibromatosis",
        "Dermatofibrosarcoma Protuberans",
        "Nerve Sheath Tumor",
        "Giant Cell Tumor of Bone",
    ],
    "thyroid_cancer": [
        "Anaplastic Thyroid Cancer",
        "Well-Differentiated Thyroid Cancer",
        "Medullary Thyroid Cancer",
        "Poorly Differentiated Thyroid Cancer",
    ],
    "cervical_cancer": [
        "Cervical Squamous Cell Carcinoma",
        "Cervical Adenocarcinoma",
        "Mixed Cervical Carcinoma",
        "Glassy Cell Carcinoma of the Cervix",
        "Small Cell Carcinoma of the Cervix",
        "Small Cell Neuroendocrine Carcinoma of the Cervix",
        "Squamous Cell Carcinoma of the Vulva/Vagina",
    ],
    "endometrial_cancer": [
        "Endometrial Carcinoma",
        "Uterine Sarcoma/Mesenchymal",
    ],
    "mesothelioma": [
        "Pleural Mesothelioma",
    ],
    "adrenal_cancer": [
        "Adrenocortical Carcinoma",
    ],
    "germ_cell": [
        "Non-Seminomatous Germ Cell Tumor",
        "Extra Gonadal Germ Cell Tumor",
    ],
    "bile_duct": [
        "Intraductal Papillary Neoplasm of the Bile Duct",
        "Intracholecystic Papillary Neoplasm",
        "Ampullary Carcinoma",
    ],
    "other": [
        "Non-Cancerous",
        "Other",
        "Gestational Trophoblastic Disease",
        "SMARCA4-deficient undifferentiated tumor",
        "Hereditary Spherocytosis",
        "Gastrointestinal Neuroendocrine Tumors",
        "Gastrointestinal Stromal Tumor",
        "Small Bowel Cancer",
    ],
}

# Maps user-friendly disease name inputs to category keys above.
CATEGORY_ALIASES = {
    # Lung
    "lung cancer": "lung_cancer",
    "lung carcinoma": "lung_cancer",
    "lung": "lung_cancer",
    "nsclc": "lung_cancer",
    "non-small cell lung cancer": "lung_cancer",
    "non small cell lung cancer": "lung_cancer",
    "sclc": "lung_cancer",
    "small cell lung cancer": "lung_cancer",
    "lung adenocarcinoma": "lung_cancer",
    # Breast
    "breast cancer": "breast_cancer",
    "breast carcinoma": "breast_cancer",
    "breast": "breast_cancer",
    # Colorectal
    "colorectal cancer": "colorectal_cancer",
    "colorectal": "colorectal_cancer",
    "colon cancer": "colorectal_cancer",
    "colon": "colorectal_cancer",
    "rectal cancer": "colorectal_cancer",
    # Gastric / Esophageal
    "gastric cancer": "gastric_cancer",
    "gastric": "gastric_cancer",
    "stomach cancer": "gastric_cancer",
    "stomach": "gastric_cancer",
    "esophageal cancer": "gastric_cancer",
    "esophagus cancer": "gastric_cancer",
    "esophagogastric": "gastric_cancer",
    # Ovarian
    "ovarian cancer": "ovarian_cancer",
    "ovarian carcinoma": "ovarian_cancer",
    "ovarian": "ovarian_cancer",
    "ovary cancer": "ovarian_cancer",
    # Pancreatic
    "pancreatic cancer": "pancreatic_cancer",
    "pancreatic adenocarcinoma": "pancreatic_cancer",
    "pancreatic": "pancreatic_cancer",
    "pancreas cancer": "pancreatic_cancer",
    # Melanoma
    "melanoma": "melanoma",
    "skin melanoma": "melanoma",
    "skin cancer": "melanoma",
    "cutaneous melanoma": "melanoma",
    # Leukemia
    "leukemia": "leukemia",
    "aml": "leukemia",
    "acute myeloid leukemia": "leukemia",
    "all": "leukemia",
    "acute lymphoblastic leukemia": "leukemia",
    # Lymphoma
    "lymphoma": "lymphoma",
    "non-hodgkin lymphoma": "lymphoma",
    "hodgkin lymphoma": "lymphoma",
    # Brain / CNS
    "brain cancer": "brain_cns",
    "brain tumor": "brain_cns",
    "brain": "brain_cns",
    "cns cancer": "brain_cns",
    "glioma": "brain_cns",
    "glioblastoma": "brain_cns",
    "neuroblastoma": "brain_cns",
    # Head and Neck
    "head and neck cancer": "head_neck",
    "head neck cancer": "head_neck",
    "head and neck": "head_neck",
    # Liver
    "liver cancer": "liver_cancer",
    "liver": "liver_cancer",
    "hepatocellular carcinoma": "liver_cancer",
    "hcc": "liver_cancer",
    # Renal / Kidney
    "renal cancer": "renal_cancer",
    "renal cell carcinoma": "renal_cancer",
    "kidney cancer": "renal_cancer",
    "kidney": "renal_cancer",
    # Bladder
    "bladder cancer": "bladder_cancer",
    "bladder": "bladder_cancer",
    # Prostate
    "prostate cancer": "prostate_cancer",
    "prostate": "prostate_cancer",
    # Sarcoma
    "sarcoma": "sarcoma",
    "bone cancer": "sarcoma",
    "soft tissue sarcoma": "sarcoma",
    "osteosarcoma": "sarcoma",
    # Thyroid
    "thyroid cancer": "thyroid_cancer",
    "thyroid": "thyroid_cancer",
    # Cervical
    "cervical cancer": "cervical_cancer",
    "cervical": "cervical_cancer",
    "cervix cancer": "cervical_cancer",
    # Endometrial / Uterine
    "endometrial cancer": "endometrial_cancer",
    "endometrial": "endometrial_cancer",
    "uterine cancer": "endometrial_cancer",
    "uterine": "endometrial_cancer",
    "uterus cancer": "endometrial_cancer",
    # Mesothelioma
    "mesothelioma": "mesothelioma",
    # Adrenal
    "adrenal cancer": "adrenal_cancer",
    "adrenocortical carcinoma": "adrenal_cancer",
    "adrenal": "adrenal_cancer",
    # Germ cell / Testicular
    "germ cell tumor": "germ_cell",
    "germ cell": "germ_cell",
    "testicular cancer": "germ_cell",
    "testicular": "germ_cell",
    # Bile duct
    "bile duct cancer": "bile_duct",
    "bile duct": "bile_duct",
    "cholangiocarcinoma": "bile_duct",
}


def resolve_disease_categories(disease: str) -> list:
    """Resolve a user-supplied disease name to a list of specific DepMap/TCGA disease names.

    Uses CATEGORY_ALIASES for substring matching against the user input.
    Returns an empty list if no category match is found (caller should fall back
    to legacy substring matching).
    """
    if not disease or not disease.strip():
        return []
    disease_lower = disease.strip().lower()

    # 1. Exact match in aliases
    if disease_lower in CATEGORY_ALIASES:
        category_key = CATEGORY_ALIASES[disease_lower]
        return DISEASE_CATEGORIES.get(category_key, [])

    # 2. Substring match: user input contains alias key, or alias key contains user input
    best_match = None
    best_len = 0
    for alias, category_key in CATEGORY_ALIASES.items():
        if disease_lower in alias or alias in disease_lower:
            if len(alias) > best_len:
                best_match = category_key
                best_len = len(alias)

    if best_match:
        return DISEASE_CATEGORIES.get(best_match, [])

    return []


# Scoring weights by scenario
SCENARIO_WEIGHTS = {
    "research": {  # 基金/SCI scenario
        "disease_relevance": 0.24,
        "expression": 0.05,
        "dependency": 0.12,
        "mechanism": 0.24,
        "druggability": 0.12,
        "safety": 0.05,
        "clinical_competition": 0.12,
        "scenario_fit": 0.06,
    },
    "drug_development": {  # Enterprise drug R&D scenario
        "disease_relevance": 0.19,
        "expression": 0.05,
        "dependency": 0.19,
        "mechanism": 0.13,
        "druggability": 0.19,
        "safety": 0.05,
        "clinical_competition": 0.13,
        "scenario_fit": 0.07,
    },
    "adc": {  # ADC-focused scenario
        "disease_relevance": 0.16,
        "expression": 0.05,
        "dependency": 0.16,
        "mechanism": 0.08,
        "druggability": 0.33,
        "safety": 0.05,
        "clinical_competition": 0.08,
        "scenario_fit": 0.09,
    },
    "small_molecule": {  # Small molecule scenario
        "disease_relevance": 0.12,
        "expression": 0.05,
        "dependency": 0.18,
        "mechanism": 0.18,
        "druggability": 0.30,
        "safety": 0.05,
        "clinical_competition": 0.06,
        "scenario_fit": 0.06,
    },
    "general": {  # Default balanced
        "disease_relevance": 0.18,
        "expression": 0.05,
        "dependency": 0.18,
        "mechanism": 0.18,
        "druggability": 0.18,
        "safety": 0.05,
        "clinical_competition": 0.12,
        "scenario_fit": 0.06,
    },
}

# Score labels
SCORE_GRADES = {
    (80, 101): ("A", "强推荐 — 多维证据较强，适合深入验证/立项"),
    (65, 80): ("B", "有潜力 — 有一定证据，但需补关键缺口"),
    (50, 65): ("C", "谨慎推进 — 证据不完整或风险较明显"),
    (35, 50): ("D", "低优先级 — 当前证据不足，不建议作为核心靶点"),
    (0, 35): ("E", "不推荐 — 缺乏关键支持或风险较高"),
}

# Dimension max scores
DIMENSION_MAX = {
    "disease_relevance": 15,
    "expression": 15,
    "dependency": 15,
    "mechanism": 15,
    "druggability": 15,
    "safety": 10,
    "clinical_competition": 10,
    "scenario_fit": 5,
}

# ── Target archetype classification ─────────────────────────────────────
# Some targets are validated by mutation rather than expression (e.g. EGFR, KRAS),
# others by overexpression (e.g. CLDN18, ERBB2), others by dependency (e.g. PRMT5).
# The archetype system adjusts dimension weights so that a target isn't penalised
# for being weak in a dimension that doesn't matter for its biology.

# Archetype weight modifiers: deltas applied on top of SCENARIO_WEIGHTS.
# Each archetype's deltas sum to 0 so total weight stays 1.0.
ARCHETYPE_MODIFIERS = {
    # Validated primarily by high mutation / CNV frequency; expression is secondary
    "mutation_driven": {
        "disease_relevance": +0.07,
        "expression":         -0.08,
        "dependency":         +0.02,
        "safety":             -0.01,
    },
    # Validated primarily by tumor-selective overexpression; mutation is secondary
    "expression_driven": {
        "expression":         +0.07,
        "disease_relevance":  -0.03,
        "dependency":         -0.02,
        "safety":             -0.02,
    },
    # Validated primarily by CRISPR / RNAi dependency; expression not required
    "dependency_driven": {
        "dependency":         +0.07,
        "expression":         -0.05,
        "mechanism":          -0.02,
    },
    # Already has approved drugs; clinical / druggability dimensions are proven
    "drug_target": {
        "druggability":       +0.05,
        "clinical_competition": +0.02,
        "expression":         -0.04,
        "mechanism":          -0.03,
    },
    # No single signal dominates; use scenario weights unchanged
    "balanced": {},
}

# Gene alias cache (common aliases - will be supplemented by mygene.info)
GENE_ALIAS_CACHE = {
    "ERBB2": "ERBB2",
    "HER2": "ERBB2",
    "HER-2": "ERBB2",
    "EGFR": "EGFR",
    "ERBB1": "EGFR",
    "HER1": "EGFR",
    "BRCA1": "BRCA1",
    "MUC1": "MUC1",
    "CLDN18": "CLDN18",
    "CLDN18.1": "CLDN18",
    "CLDN18.2": "CLDN18",
    "KRAS": "KRAS",
    "TP53": "TP53",
    "PRMT5": "PRMT5",
    "CD276": "CD276",
    "B7-H3": "CD276",
    "B7H3": "CD276",
    "TNF": "TNF",
    "VEGFA": "VEGFA",
    "VEGF": "VEGFA",
    "PDL1": "CD274",
    "PD-L1": "CD274",
    "CD274": "CD274",
    "MTOR": "MTOR",
    "PIK3CA": "PIK3CA",
    "ALK": "ALK",
    "ROS1": "ROS1",
    "MET": "MET",
    "RET": "RET",
    "BRAF": "BRAF",
    "IDH1": "IDH1",
    "FGFR2": "FGFR2",
    "FGFR3": "FGFR3",
    "NTRK1": "NTRK1",
}
