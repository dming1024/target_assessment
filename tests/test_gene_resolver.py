"""Tests for gene_resolver module."""

from modules.gene_resolver import GeneResolver, GeneInfo


def test_resolve_local_cache_her2():
    resolver = GeneResolver()
    result = resolver.resolve("HER2")
    assert result.symbol == "ERBB2"
    assert result.status in ("resolved_local", "resolved_api_and_cache")
    resolver.close()


def test_resolve_local_cache_egfr():
    resolver = GeneResolver()
    result = resolver.resolve("EGFR")
    assert result.symbol == "EGFR"
    assert result.status in ("resolved_local", "resolved_api_and_cache")
    resolver.close()


def test_resolve_empty_input():
    resolver = GeneResolver()
    result = resolver.resolve("")
    assert result.status == "empty_input"
    resolver.close()


def test_resolve_unknown_returns_upper():
    resolver = GeneResolver()
    result = resolver.resolve("ZZZ999")
    # If mygene is unreachable, should fall back to upper with unresolved
    assert result.status in ("resolved_api", "unresolved")
    resolver.close()


def test_resolve_batch():
    resolver = GeneResolver()
    results = resolver.resolve_batch(["HER2", "EGFR", "BRCA1"])
    assert len(results) == 3
    assert results[0].symbol == "ERBB2"
    assert results[1].symbol == "EGFR"
    assert results[2].symbol == "BRCA1"
    resolver.close()


def test_geneinfo_to_dict():
    info = GeneInfo(
        input_symbol="HER2",
        symbol="ERBB2",
        ensembl_id="ENSG00000141736",
        entrez_id="2064",
        full_name="erb-b2 receptor tyrosine kinase 2",
        synonyms=["HER-2", "NEU"],
        status="resolved_local",
    )
    d = info.to_dict()
    assert d["symbol"] == "ERBB2"
    assert d["status"] == "resolved_local"


if __name__ == "__main__":
    test_resolve_local_cache_her2()
    test_resolve_local_cache_egfr()
    test_resolve_empty_input()
    test_resolve_unknown_returns_upper()
    test_resolve_batch()
    test_geneinfo_to_dict()
    print("All gene_resolver tests passed!")
