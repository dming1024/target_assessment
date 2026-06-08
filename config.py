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

# Scoring weights by scenario
SCENARIO_WEIGHTS = {
    "research": {  # 基金/SCI scenario
        "disease_relevance": 0.20,
        "expression": 0.15,
        "dependency": 0.10,
        "mechanism": 0.20,
        "druggability": 0.10,
        "safety": 0.10,
        "clinical_competition": 0.10,
        "scenario_fit": 0.05,
    },
    "drug_development": {  # Enterprise drug R&D scenario
        "disease_relevance": 0.15,
        "expression": 0.15,
        "dependency": 0.15,
        "mechanism": 0.10,
        "druggability": 0.15,
        "safety": 0.15,
        "clinical_competition": 0.10,
        "scenario_fit": 0.05,
    },
    "adc": {  # ADC-focused scenario
        "disease_relevance": 0.10,
        "expression": 0.25,
        "dependency": 0.10,
        "mechanism": 0.05,
        "druggability": 0.20,
        "safety": 0.20,
        "clinical_competition": 0.05,
        "scenario_fit": 0.05,
    },
    "small_molecule": {  # Small molecule scenario
        "disease_relevance": 0.10,
        "expression": 0.10,
        "dependency": 0.15,
        "mechanism": 0.15,
        "druggability": 0.25,
        "safety": 0.15,
        "clinical_competition": 0.05,
        "scenario_fit": 0.05,
    },
    "general": {  # Default balanced
        "disease_relevance": 0.15,
        "expression": 0.15,
        "dependency": 0.15,
        "mechanism": 0.15,
        "druggability": 0.15,
        "safety": 0.10,
        "clinical_competition": 0.10,
        "scenario_fit": 0.05,
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
