"""
FRED data provider — wraps modules/data_ingestion/fred_loader.py.
"""

from typing import Any, Dict, Optional

import pandas as pd

from providers.base_provider import BaseProvider
from modules.data_ingestion.fred_loader import (
    get_fred_client,
    search_fred,
    load_fred_series,
    get_series_info,
    get_series_release_source,
)


class FredProvider(BaseProvider):

    @property
    def name(self) -> str:
        return "FRED"

    def fetch_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs,
    ) -> pd.DataFrame:
        return load_fred_series(series_id, start_date=start_date, end_date=end_date)

    def search(self, query: str, limit: int = 20) -> pd.DataFrame:
        results = search_fred(query, limit=limit)
        if results.empty:
            return results

        # Enrich top 10 results with source and release
        sources = []
        releases = []
        for i, row in results.iterrows():
            if i < 10:
                try:
                    rs = get_series_release_source(str(row["id"]))
                    sources.append(rs.get("source", ""))
                    releases.append(rs.get("release", ""))
                except Exception:
                    sources.append("")
                    releases.append("")
            else:
                sources.append("")
                releases.append("")
        results["source"] = sources
        results["release"] = releases
        return results

    def get_metadata(self, series_id: str) -> Dict[str, Any]:
        meta = get_series_info(series_id)
        # Enrich with source and release
        try:
            rs = get_series_release_source(series_id)
            if rs.get("source"):
                meta["source"] = rs["source"]
            if rs.get("release"):
                meta["release"] = rs["release"]
            if rs.get("release_id"):
                meta["release_id"] = rs["release_id"]
        except Exception:
            pass
        return meta

    def check_status(self) -> tuple:
        client, err = get_fred_client()
        if err:
            return False, err
        return True, "FRED API key configured"
