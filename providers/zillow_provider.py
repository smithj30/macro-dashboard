"""
Zillow data provider — wraps modules/data_ingestion/zillow_loader.py.
"""

from typing import Any, Dict, List, Optional

import pandas as pd

from providers.base_provider import BaseProvider
from modules.data_ingestion.zillow_loader import (
    load_zillow_series,
    get_cached_datasets,
)
from modules.data_ingestion.zillow_registry import get_registry


class ZillowProvider(BaseProvider):

    @property
    def name(self) -> str:
        return "Zillow"

    def fetch_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Fetch a Zillow dataset.

        series_id: the registry entry 'filename' key (e.g. 'Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month')
        kwargs: regions (list of region names)
        """
        entry = self._find_entry(series_id)
        if entry is None:
            raise ValueError(f"Zillow dataset not found: {series_id}")

        regions = kwargs.get("regions")
        df = load_zillow_series(entry, regions=regions)

        if start_date and not df.empty:
            df = df[df.index >= pd.Timestamp(start_date)]
        if end_date and not df.empty:
            df = df[df.index <= pd.Timestamp(end_date)]

        return df

    def search(self, query: str, limit: int = 20) -> pd.DataFrame:
        """Search the Zillow dataset registry."""
        registry = get_registry()
        results = []
        q = query.lower()
        for entry in registry:
            searchable = f"{entry.get('label', '')} {entry.get('category', '')} {entry.get('notes', '')}".lower()
            if q in searchable:
                results.append({
                    "id": entry["filename"],
                    "title": entry.get("label", entry["filename"]),
                    "category": entry.get("category", ""),
                    "frequency": entry.get("frequency", "Monthly"),
                    "geography": entry.get("geography", ""),
                })
        return pd.DataFrame(results).head(limit)

    def get_metadata(self, series_id: str) -> Dict[str, Any]:
        entry = self._find_entry(series_id)
        if entry:
            return dict(entry)
        return {}

    def check_status(self) -> tuple:
        registry = get_registry()
        return True, f"Zillow registry: {len(registry)} datasets available"

    def list_datasets(self) -> List[Dict[str, Any]]:
        registry = get_registry()
        return [
            {
                "id": e["filename"],
                "title": e.get("label", e["filename"]),
                "category": e.get("category", ""),
            }
            for e in registry
        ]

    @staticmethod
    def _find_entry(series_id: str) -> Optional[Dict[str, Any]]:
        registry = get_registry()
        for entry in registry:
            if entry.get("filename") == series_id:
                return entry
        return None
