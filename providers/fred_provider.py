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
        return search_fred(query, limit=limit)

    def get_metadata(self, series_id: str) -> Dict[str, Any]:
        return get_series_info(series_id)

    def check_status(self) -> tuple:
        client, err = get_fred_client()
        if err:
            return False, err
        return True, "FRED API key configured"
