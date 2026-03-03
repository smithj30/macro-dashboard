"""
BaseProvider — abstract interface for all data source providers.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import pandas as pd


class BaseProvider(ABC):
    """
    Abstract base class for data providers.

    Every provider must implement:
      - name: human-readable provider name
      - fetch_series: load a time series by ID
      - search: search for available series (optional)
      - get_metadata: return metadata for a series (optional)
      - check_status: verify provider is configured/available
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name (e.g. 'FRED', 'BEA')."""
        ...

    @abstractmethod
    def fetch_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Fetch a time series by ID.

        Returns a DataFrame with DatetimeIndex ('date') and one or more
        value columns.
        """
        ...

    def search(self, query: str, limit: int = 20) -> pd.DataFrame:
        """
        Search for available series. Returns a DataFrame of results.
        Default implementation returns empty — override in providers that
        support search.
        """
        return pd.DataFrame()

    def get_metadata(self, series_id: str) -> Dict[str, Any]:
        """Return metadata dict for a series. Default returns empty."""
        return {}

    def check_status(self) -> tuple:
        """
        Check if the provider is configured and available.
        Returns (is_ok: bool, message: str).
        """
        return True, "OK"

    def list_datasets(self) -> List[Dict[str, Any]]:
        """
        List available datasets/tables. Not all providers support this.
        Returns a list of dicts with at least 'id' and 'title' keys.
        """
        return []
