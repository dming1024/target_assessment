"""
ChEMBL REST API Client.

Queries drug/compound information for a target gene:
- Approved drugs count
- Clinical candidate count
- Active compound count

API: https://www.ebi.ac.uk/chembl/api/data
Free, no API key required. Rate limit: ~1 request/second.
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

import httpx

from config import CHEMBL_API, CACHE_DIR

logger = logging.getLogger(__name__)


class ChemblClient:
    """Query ChEMBL for target druggability evidence."""

    def __init__(self, cache: bool = True):
        self._http_client: Optional[httpx.Client] = None
        self._cache = cache
        self._mem_cache: dict = {}
        self._last_request_time = 0.0
        self._min_interval = 1.1  # seconds between requests (>1 req/s limit)

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
        """Ensure we don't exceed 1 request/second."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def query_target(self, gene_symbol: str) -> dict:
        """
        Query ChEMBL for compounds associated with a target gene.

        Searches for the target by gene symbol, then fetches
        compound counts grouped by development phase.

        Returns dict with:
            approved_drugs: int
            clinical_candidates: int
            active_compounds: int
            modality_fit: "strong" | "moderate" | "weak" | "unknown"
        """
        gene_upper = gene_symbol.upper()

        # Check cache
        if gene_upper in self._mem_cache:
            return self._mem_cache[gene_upper]

        if self._cache:
            cached = self._load_cache(gene_upper)
            if cached is not None:
                self._mem_cache[gene_upper] = cached
                return cached

        try:
            result = self._query_api(gene_upper)
        except Exception as e:
            logger.warning(f"ChEMBL API error for {gene_symbol}: {e}")
            result = self._empty_result()

        self._mem_cache[gene_upper] = result
        if self._cache:
            self._save_cache(gene_upper, result)

        return result

    def _query_api(self, gene_symbol: str) -> dict:
        """
        Query ChEMBL API for target and its drugs.

        Approach:
        1. Search for target by gene symbol: /target/search?q=<symbol>
        2. For each target, filter to the best match (prefer SINGLE PROTEIN)
        3. Count drugs by max_phase (4=approved, 3/2=clinical, 1=active)
        """
        # Step 1: Find target
        self._rate_limit()
        search_url = f"{CHEMBL_API}/target/search"
        response = self.http_client.get(search_url, params={
            "q": gene_symbol,
            "organism": "Homo sapiens",
            "limit": 5,
            "format": "json",
        })
        if response.status_code in (404, 400):
            logger.info(f"ChEMBL: no target found for {gene_symbol} (status {response.status_code})")
            return self._empty_result()
        response.raise_for_status()

        try:
            search_data = response.json()
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"ChEMBL: invalid JSON response for {gene_symbol}")
            return self._empty_result()

        targets = search_data.get("targets", [])
        if not targets:
            logger.info(f"ChEMBL: no target found for {gene_symbol}")
            return self._empty_result()

        # Pick the best target match: prefer SINGLE PROTEIN
        best_target = None
        for t in targets:
            if t.get("target_type") == "SINGLE PROTEIN":
                best_target = t
                break

        if best_target is None:
            best_target = targets[0]

        target_chembl_id = best_target["target_chembl_id"]
        logger.info(f"ChEMBL target: {target_chembl_id} ({best_target.get('pref_name', gene_symbol)})")

        # Step 2: Count drugs by phase
        # ChEMBL mechanism_of_action or drug_mechanism can link targets to molecules.
        # A simpler approach: use the target's drug count from the target card, or
        # query /mechanism?target_chembl_id=...
        self._rate_limit()
        mech_url = f"{CHEMBL_API}/mechanism"
        response = self.http_client.get(mech_url, params={
            "target_chembl_id": target_chembl_id,
            "limit": 500,
            "format": "json",
        })
        response.raise_for_status()
        try:
            mech_data = response.json()
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"ChEMBL: invalid JSON from mechanism endpoint for {gene_symbol}")
            return self._empty_result()

        mechanisms = mech_data.get("mechanisms", [])
        approved = 0
        clinical = 0
        active = 0

        seen_molecules = set()
        for mech in mechanisms:
            mol_chembl_id = mech.get("molecule_chembl_id")
            if mol_chembl_id in seen_molecules:
                continue
            seen_molecules.add(mol_chembl_id)

            max_phase = mech.get("max_phase") or 0
            if max_phase >= 4:
                approved += 1
            elif max_phase >= 2:
                clinical += 1
            elif max_phase >= 1:
                active += 1
            else:
                active += 1  # count all with mechanism evidence

        # Step 3: Determine modality fit
        # Strong: approved + clinical >= 3
        # Moderate: approved + clinical >= 1 or active >= 5
        # Weak: otherwise
        if approved + clinical >= 3:
            modality_fit = "strong"
        elif approved + clinical >= 1 or active >= 5:
            modality_fit = "moderate"
        elif active > 0:
            modality_fit = "weak"
        else:
            modality_fit = "unknown"

        return {
            "approved_drugs": approved,
            "clinical_candidates": clinical,
            "active_compounds": active,
            "modality_fit": modality_fit,
            "chembl_target_id": target_chembl_id,
        }

    def _empty_result(self) -> dict:
        return {
            "approved_drugs": 0,
            "clinical_candidates": 0,
            "active_compounds": 0,
            "modality_fit": "unknown",
            "chembl_target_id": None,
        }

    # ------------------------------------------------------------------
    # Caching
    # ------------------------------------------------------------------

    def _cache_path(self, gene: str) -> Path:
        return CACHE_DIR / f"chembl_{gene}.json"

    def _load_cache(self, gene: str) -> Optional[dict]:
        path = self._cache_path(gene)
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return None

    def _save_cache(self, gene: str, data: dict):
        path = self._cache_path(gene)
        try:
            with open(path, "w") as f:
                json.dump(data, f)
        except IOError as e:
            logger.warning(f"Failed to cache ChEMBL result: {e}")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
