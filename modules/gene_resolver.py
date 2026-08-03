"""
Gene Symbol Resolver - 基因名标准化模块

Standardizes user-input gene symbols to official HGNC symbols using:
1. Offline SQLite DB (primary, no network)
2. mygene.info API (fallback, if DB unavailable)
3. Local alias cache (last resort)
"""

import logging
from typing import List, Optional

from config import MYGENE_API, GENE_ALIAS_CACHE
from modules.offline_provider import OfflineProvider

logger = logging.getLogger(__name__)


class GeneInfo:
    """Standardized gene information container."""

    def __init__(
        self,
        input_symbol: str,
        symbol: str,
        ensembl_id: str = "",
        entrez_id: str = "",
        full_name: str = "",
        synonyms: list = None,
        status: str = "unresolved",
    ):
        self.input = input_symbol
        self.symbol = symbol
        self.ensembl_id = ensembl_id or ""
        self.entrez_id = entrez_id or ""
        self.full_name = full_name or ""
        self.synonyms = synonyms or []
        self.status = status

    def to_dict(self) -> dict:
        return {
            "input": self.input,
            "symbol": self.symbol,
            "ensembl_id": self.ensembl_id,
            "entrez_id": str(self.entrez_id) if self.entrez_id else "",
            "full_name": self.full_name,
            "synonyms": self.synonyms,
            "status": self.status,
        }

    def __repr__(self):
        return f"GeneInfo({self.symbol}, status={self.status})"


class GeneResolver:
    """Resolve gene symbols to standardized HGNC identifiers."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self._http_client = None

    @property
    def http_client(self):
        if self._http_client is None:
            import httpx
            self._http_client = httpx.Client(timeout=self.timeout)
        return self._http_client

    def close(self):
        if self._http_client is not None:
            self._http_client.close()
            self._http_client = None

    def resolve(self, gene_input: str) -> GeneInfo:
        """
        Resolve a user-provided gene symbol to its official HGNC symbol.

        Resolution order:
        1. Local alias cache lookup
        2. Offline SQLite DB (if available)
        3. mygene.info API query (network)
        4. Return as-is with 'unresolved' status if all else fails
        """
        gene_input = gene_input.strip()

        if not gene_input:
            return GeneInfo(
                input_symbol=gene_input,
                symbol=gene_input,
                status="empty_input",
            )

        # Step 1: Check local alias cache for quick normalization
        upper_input = gene_input.upper()
        official_symbol = GENE_ALIAS_CACHE.get(upper_input, None)

        # Step 2: Try offline SQLite DB (fast, no network)
        try:
            provider = OfflineProvider()
            if provider.is_available():
                resolved = provider.resolve_gene(gene_input)
                if resolved:
                    sym, ensembl, full_name, synonyms_str = resolved
                    return GeneInfo(
                        input_symbol=gene_input,
                        symbol=sym,
                        ensembl_id=ensembl,
                        full_name=full_name,
                        synonyms=self._parse_synonyms(synonyms_str),
                        status="resolved_offline",
                    )
        except Exception as e:
            logger.debug(f"Offline gene resolution failed for '{gene_input}': {e}")

        # Step 3: Query mygene.info (network fallback)
        try:
            result = self._query_mygene(gene_input)
            if result:
                if official_symbol and official_symbol != result.symbol.upper():
                    result.symbol = official_symbol
                result.status = (
                    "resolved_api_and_cache" if official_symbol else "resolved_api"
                )
                return result
        except Exception as e:
            logger.warning(f"mygene.info query failed for '{gene_input}': {e}")

        # Step 4: Fall back to local cache only (no Ensembl ID available)
        if official_symbol:
            return GeneInfo(
                input_symbol=gene_input,
                symbol=official_symbol,
                synonyms=[gene_input] if official_symbol != upper_input else [],
                status="resolved_local",
            )

        # Step 5: Return as-is with unresolved status
        return GeneInfo(
            input_symbol=gene_input,
            symbol=upper_input,
            status="unresolved",
        )

    @staticmethod
    def _parse_synonyms(synonyms_json: str) -> list:
        """Parse synonyms from a JSON array string. Returns empty list on failure."""
        if not synonyms_json or synonyms_json in ("[]", ""):
            return []
        try:
            import json
            parsed = json.loads(synonyms_json)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return []

    def _query_mygene(self, gene_input: str) -> Optional[GeneInfo]:
        """Query mygene.info API for gene information."""
        import httpx
        url = f"{MYGENE_API}/query"
        params = {
            "q": gene_input,
            "species": "human",
            "fields": "symbol,name,ensembl.gene,entrezgene,alias",
            "size": 1,
        }
        response = self.http_client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        hits = data.get("hits", [])
        if not hits:
            return None

        hit = hits[0]
        symbol = hit.get("symbol", gene_input.upper())
        aliases = hit.get("alias", [])

        ensembl_raw = hit.get("ensembl")
        if isinstance(ensembl_raw, dict):
            ensembl_id = ensembl_raw.get("gene", "")
        elif isinstance(ensembl_raw, list) and ensembl_raw:
            ensembl_id = ensembl_raw[0].get("gene", "") if isinstance(ensembl_raw[0], dict) else str(ensembl_raw[0])
        else:
            ensembl_id = ""

        entrez = hit.get("entrezgene", "")

        return GeneInfo(
            input_symbol=gene_input,
            symbol=symbol,
            ensembl_id=ensembl_id,
            entrez_id=str(entrez) if entrez else "",
            full_name=hit.get("name", ""),
            synonyms=[a for a in aliases if a.lower() != symbol.lower()],
            status="resolved_api",
        )

    def resolve_batch(self, gene_list: List[str]) -> List[GeneInfo]:
        """Resolve multiple gene symbols at once."""
        return [self.resolve(g) for g in gene_list]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
