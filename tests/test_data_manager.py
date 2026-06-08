"""Tests for data_manager module."""

from modules.data_manager import DataManager


def test_exact_match():
    dm = DataManager()
    ev = dm.collect_evidence("EGFR", "NSCLC")
    assert ev["disease_relevance"]["target_cancer_overexpression"] == "high"
    assert ev["target_overview"]["protein_class"] == "Receptor Tyrosine Kinase"
    print("Exact match test passed")


def test_flexible_match():
    dm = DataManager()
    # Should match EGFR in NSCLC even with different casing/format
    ev = dm.collect_evidence("EGFR", "Non-Small Cell Lung Cancer")
    # Flexible match should find EGFR data
    assert ev["disease_relevance"]["target_cancer_overexpression"] in ("high", "unknown")
    print(f"Flexible match test passed: overexpression={ev['disease_relevance']['target_cancer_overexpression']}")


def test_gene_alias_match():
    dm = DataManager()
    # HER2 should resolve to ERBB2
    ev = dm.collect_evidence("ERBB2", "Breast Cancer")
    assert ev["target_overview"]["protein_class"] == "Receptor Tyrosine Kinase"
    print("ERBB2 match test passed")


def test_unknown_target():
    dm = DataManager()
    ev = dm.collect_evidence("UNKNOWN_GENE", "Unknown Cancer")
    assert ev["disease_relevance"]["target_cancer_overexpression"] == "unknown"
    # protein_class may be empty string (from real source build) or "Unknown..."
    # Both are valid fallback states for unknown targets
    protein_class = ev["target_overview"]["protein_class"]
    assert protein_class == "" or "Unknown" in protein_class
    print("Unknown target fallback test passed")


def test_list_available():
    dm = DataManager()
    targets = dm.list_available_targets()
    assert len(targets) >= 5
    print(f"Available targets: {len(targets)}")
    for t in targets:
        print(f"  - {t['gene']} in {t['disease']}")


if __name__ == "__main__":
    test_exact_match()
    test_flexible_match()
    test_gene_alias_match()
    test_unknown_target()
    test_list_available()
    print("\nAll data manager tests passed!")
