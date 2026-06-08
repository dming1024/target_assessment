"""
Open Targets Platform GraphQL Client.

Queries target-disease association data including:
- Overall association score
- Evidence counts by type (genetic, literature, expression, known drug, etc.)
- Target-disease links from the Open Targets Platform API (v4 GraphQL).

API: https://api.platform.opentargets.org/api/v4/graphql
Free, no API key required, no strict rate limit.
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

import httpx

from config import OPENTARGETS_API, CACHE_DIR

logger = logging.getLogger(__name__)

# GraphQL query: get target-disease association with evidence breakdown
#
# Requires Ensembl gene ID (ENSG...) and disease EFO ID (e.g., EFO_0000621 for NSCLC).
# We use the "search" field to find the best match by gene symbol and disease name,
# or we query by Ensembl ID directly.
#
# The association query returns:
#   - score: overall association score (0–1)
#   - evidenceCounts: breakdown by datasource/datatype

ASSOCIATION_QUERY = """
query TargetDiseaseEvidence($ensemblId: String!, $efoId: String!) {
  disease(efoId: $efoId) {
    id
    name
    associatedTargets(rows: 1) {
      rows {
        target {
          id
          approvedSymbol
        }
        score
        datatypeScores {
          id
          score
        }
        count
      }
    }
  }
  target(ensemblId: $ensemblId) {
    id
    approvedSymbol
    associatedDiseases(rows: 1) {
      rows {
        disease {
          id
          name
        }
        score
        datatypeScores {
          id
          score
        }
        count
      }
    }
  }
}
"""

# Simplified query: get association by searching with gene symbol directly
# This is more robust for MVP since users input gene symbols, not Ensembl IDs.
SEARCH_AND_ASSOC_QUERY = """
query AssociationQuery($ensemblId: String!, $efoId: String!) {
  target(ensemblId: $ensemblId) {
    id
    approvedSymbol
    biotype
    associatedDiseases(rows: 5) {
      rows {
        disease {
          id
          name
        }
        score
        datatypeScores {
          id
          score
        }
      }
    }
  }
}
"""

# EFO disease label → EFO ID mapping
# We'll do substring matching on disease names to find the right EFO ID.
# For MVP, we hardcode some common disease mappings and also try the OT search API.


class OpentargetsClient:
    """Query Open Targets Platform for target-disease associations."""

    def __init__(self, cache: bool = True):
        self._http_client: Optional[httpx.Client] = None
        self._cache = cache
        # In-memory cache: (ensembl_id, efo_id) → response
        self._mem_cache: dict = {}

    @property
    def http_client(self) -> httpx.Client:
        if self._http_client is None:
            self._http_client = httpx.Client(timeout=30.0)
        return self._http_client

    def close(self):
        if self._http_client is not None:
            self._http_client.close()
            self._http_client = None

    def query_association(
        self,
        ensembl_id: str,
        disease_efo_id: str,
        gene_symbol: str = "",
        disease_name: str = "",
    ) -> dict:
        """
        Query Open Targets for target-disease association.

        Args:
            ensembl_id: Ensembl gene ID (ENSG...)
            disease_efo_id: EFO disease ID (e.g., EFO_0000621)
            gene_symbol: Gene symbol (for cache key)
            disease_name: Disease name (for cache key)

        Returns dict with:
            opentargets_association: bool
            opentargets_score: float (0–1)
            opentargets_evidence_count: int
            genetic_association_score: float
            somatic_mutation_score: float
            known_drug_score: float
            rna_expression_score: float
            literature_score: float
            affected_pathway_score: float
        """
        cache_key = f"{ensembl_id}:{disease_efo_id}"

        # Check memory cache
        if cache_key in self._mem_cache:
            return self._mem_cache[cache_key]

        # Check file cache
        if self._cache:
            cached = self._load_cache(cache_key)
            if cached is not None:
                self._mem_cache[cache_key] = cached
                return cached

        # Query API
        try:
            result = self._query_api(ensembl_id, disease_efo_id)
        except Exception as e:
            logger.warning(f"Open Targets API error for {ensembl_id}/{disease_efo_id}: {e}")
            result = self._empty_result()

        # Cache and return
        self._mem_cache[cache_key] = result
        if self._cache:
            self._save_cache(cache_key, result)

        return result

    def _query_api(self, ensembl_id: str, efo_id: str) -> dict:
        """Execute the GraphQL query."""
        # Try using the "target" endpoint with associatedDiseases
        query = """
        query($ensemblId: String!) {
          target(ensemblId: $ensemblId) {
            id
            approvedSymbol
            associatedDiseases(page: {index: 0, size: 10}) {
              rows {
                disease {
                  id
                  name
                }
                score
                datatypeScores {
                  id
                  score
                }
              }
            }
          }
        }
        """

        variables = {"ensemblId": ensembl_id}
        payload = {"query": query, "variables": variables}

        response = self.http_client.post(
            OPENTARGETS_API,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            logger.warning(f"GraphQL errors: {data['errors']}")
            return self._empty_result()

        target_data = data.get("data", {}).get("target")
        if not target_data:
            return self._empty_result()

        # Find the matching disease in associated diseases
        diseases = target_data.get("associatedDiseases", {}).get("rows", [])
        matched = None
        for d in diseases:
            if d["disease"]["id"] == efo_id:
                matched = d
                break

        # If no exact EFO match, take the first disease (closest match)
        if matched is None and diseases:
            matched = diseases[0]

        if matched is None:
            return self._empty_result()

        return self._parse_association(matched)

    def _parse_association(self, assoc: dict) -> dict:
        """Parse an association row into our evidence dict."""
        score = assoc.get("score", 0)

        # Parse datatype scores into named fields
        datatype_map = {}
        for ds in assoc.get("datatypeScores", []):
            datatype_map[ds["id"]] = ds.get("score", 0)

        return {
            "opentargets_association": score > 0.01,
            "opentargets_score": round(score, 4),
            "opentargets_evidence_count": assoc.get("count", 0),
            "genetic_association_score": round(datatype_map.get("genetic_association", 0), 4),
            "somatic_mutation_score": round(datatype_map.get("somatic_mutation", 0), 4),
            "known_drug_score": round(datatype_map.get("known_drug", 0), 4),
            "rna_expression_score": round(datatype_map.get("rna_expression", 0), 4),
            "literature_score": round(datatype_map.get("literature", 0), 4),
            "affected_pathway_score": round(datatype_map.get("affected_pathway", 0), 4),
        }

    def _empty_result(self) -> dict:
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

    # ------------------------------------------------------------------
    # Caching
    # ------------------------------------------------------------------

    def _cache_path(self, key: str) -> Path:
        return CACHE_DIR / f"opentargets_{key}.json"

    def _load_cache(self, key: str) -> Optional[dict]:
        path = self._cache_path(key)
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return None

    def _save_cache(self, key: str, data: dict):
        path = self._cache_path(key)
        try:
            with open(path, "w") as f:
                json.dump(data, f)
        except IOError as e:
            logger.warning(f"Failed to cache Open Targets result: {e}")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
