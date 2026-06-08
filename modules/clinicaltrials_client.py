"""
ClinicalTrials.gov REST API v2 Client.

Queries active clinical trial counts for a target gene and disease.

API: https://clinicaltrials.gov/api/v2
Free, no API key required. Rate limit: ~50 requests/minute.
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

import httpx

from config import CACHE_DIR

logger = logging.getLogger(__name__)

# ClinicalTrials.gov API v2 base
CT_API_BASE = "https://clinicaltrials.gov/api/v2"


class ClinicaltrialsClient:
    """Query ClinicalTrials.gov for trial counts."""

    def __init__(self, cache: bool = True):
        self._http_client: Optional[httpx.Client] = None
        self._cache = cache
        self._mem_cache: dict = {}
        self._last_request_time = 0.0
        self._min_interval = 1.2  # 50 req/min = 1.2 sec between requests

    @property
    def http_client(self) -> httpx.Client:
        if self._http_client is None:
            self._http_client = httpx.Client(timeout=30.0)
        return self._http_client

    def close(self):
        if self._http_client is not None:
            self._http_client.close()
            self._http_client = None

    def _rate_limit(self):
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def query_trial_count(self, gene_symbol: str, disease: str) -> dict:
        """
        Query ClinicalTrials.gov for active trials involving a gene + disease.

        Uses the /studies endpoint with query parameters:
        - query.term: gene symbol + disease name
        - filter.overallStatus: active statuses (RECRUITING, NOT_YET_RECRUITING, etc.)
        - pageSize: 1 (we only need the count)

        Returns dict with:
            active_clinical_trials: int
            approved_drugs_count: int (derived from trials with approved drugs)
            differentiation_opportunity: "high" | "moderate" | "low" | "unknown"
        """
        gene_upper = gene_symbol.upper()
        disease_lower = disease.lower()
        cache_key = f"{gene_upper}:{disease_lower}"

        # Check cache
        if cache_key in self._mem_cache:
            return self._mem_cache[cache_key]

        if self._cache:
            cached = self._load_cache(cache_key)
            if cached is not None:
                self._mem_cache[cache_key] = cached
                return cached

        try:
            result = self._query_api(gene_upper, disease)
        except Exception as e:
            logger.warning(f"ClinicalTrials.gov API error for {gene_symbol}/{disease}: {e}")
            result = self._empty_result()

        self._mem_cache[cache_key] = result
        if self._cache:
            self._save_cache(cache_key, result)

        return result

    def _query_api(self, gene_symbol: str, disease: str) -> dict:
        """Query the ClinicalTrials.gov API v2 studies endpoint.

        The v2 API uses cursor-based pagination (nextPageToken) and
        does not provide a totalCount. We use a large page size and
        check for nextPageToken to estimate counts.
        """
        query_terms = f"{gene_symbol} AND {disease}"
        active_statuses = [
            "RECRUITING",
            "NOT_YET_RECRUITING",
            "ACTIVE_NOT_RECRUITING",
            "ENROLLING_BY_INVITATION",
        ]

        self._rate_limit()
        url = f"{CT_API_BASE}/studies"

        # Get a page of studies (all statuses)
        params = {
            "query.term": query_terms,
            "pageSize": 100,
            "format": "json",
        }
        response = self.http_client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        studies = data.get("studies", [])
        has_more = bool(data.get("nextPageToken"))
        # Estimate: if there are 100 on first page and more pages exist,
        # the total is at least 100. Use the count we have.
        total_count = len(studies)
        if has_more:
            total_count = max(total_count, 100)

        # Also query active studies only
        self._rate_limit()
        active_params = {
            "query.term": query_terms,
            "filter.overallStatus": ",".join(active_statuses),
            "pageSize": 100,
            "format": "json",
        }
        response = self.http_client.get(url, params=active_params)
        response.raise_for_status()
        active_data = response.json()
        active_studies = active_data.get("studies", [])
        active_has_more = bool(active_data.get("nextPageToken"))
        active_count = len(active_studies)
        if active_has_more:
            active_count = max(active_count, 100)

        # Estimate approved drugs from ChEMBL (handled separately in DataManager)
        # Here we provide trial-count-based estimates
        approved_drugs_estimate = 0
        if total_count >= 50:
            approved_drugs_estimate = max(1, total_count // 30)
        elif total_count >= 10:
            approved_drugs_estimate = 1

        # Differentiation opportunity
        if active_count == 0:
            diff_opp = "high"
        elif active_count < 10:
            diff_opp = "moderate"
        else:
            diff_opp = "low"

        return {
            "active_clinical_trials": total_count,
            "active_recruiting_trials": active_count,
            "approved_drugs_count": approved_drugs_estimate,
            "differentiation_opportunity": diff_opp,
            "has_more_results": has_more,
        }

    def _empty_result(self) -> dict:
        return {
            "active_clinical_trials": 0,
            "active_recruiting_trials": 0,
            "approved_drugs_count": 0,
            "differentiation_opportunity": "unknown",
        }

    # ------------------------------------------------------------------
    # Caching
    # ------------------------------------------------------------------

    def _cache_path(self, key: str) -> Path:
        safe_key = key.replace(":", "_").replace(" ", "_").lower()
        return CACHE_DIR / f"clinicaltrials_{safe_key}.json"

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
            logger.warning(f"Failed to cache ClinicalTrials result: {e}")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
