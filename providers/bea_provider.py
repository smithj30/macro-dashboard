"""
BEA data provider — wraps modules/data_ingestion/bea_loader.py.
"""

from typing import Any, Dict, List, Optional

import pandas as pd

from providers.base_provider import BaseProvider
from modules.data_ingestion.bea_loader import (
    get_bea_key_status,
    list_bea_tables,
    fetch_bea_table,
    last_n_years,
    SUPPORTED_DATASETS,
)


class BEAProvider(BaseProvider):

    @property
    def name(self) -> str:
        return "BEA"

    def fetch_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Fetch a BEA table.

        series_id format: "<dataset>/<table_name>" (e.g. "NIPA/T10101")
        kwargs: frequency (Q/A), years, line_codes
        """
        parts = series_id.split("/", 1)
        if len(parts) == 2:
            dataset, table_name = parts
        else:
            dataset, table_name = "NIPA", parts[0]

        frequency = kwargs.get("frequency", "Q")
        years = kwargs.get("years", last_n_years(10))
        line_codes = kwargs.get("line_codes")

        return fetch_bea_table(
            dataset=dataset,
            table_name=table_name,
            frequency=frequency,
            years=years,
            line_codes=line_codes,
        )

    def search(self, query: str, limit: int = 20) -> pd.DataFrame:
        """Search across all supported BEA datasets for matching tables."""
        all_results = []
        for dataset in SUPPORTED_DATASETS:
            try:
                tables = list_bea_tables(dataset)
                mask = tables["Description"].str.contains(query, case=False, na=False)
                matched = tables[mask].head(limit).copy()
                matched["dataset"] = dataset
                matched["id"] = dataset + "/" + matched["TableName"]
                all_results.append(matched)
            except Exception:
                continue
        if not all_results:
            return pd.DataFrame()
        return pd.concat(all_results, ignore_index=True).head(limit)

    def get_metadata(self, series_id: str) -> Dict[str, Any]:
        parts = series_id.split("/", 1)
        dataset = parts[0] if len(parts) == 2 else "NIPA"
        table = parts[1] if len(parts) == 2 else parts[0]
        return {"dataset": dataset, "table_name": table, "provider": "BEA"}

    def check_status(self) -> tuple:
        key, err = get_bea_key_status()
        if err:
            return False, err
        return True, "BEA API key configured"

    def list_datasets(self) -> List[Dict[str, Any]]:
        results = []
        for ds_id, ds_title in SUPPORTED_DATASETS.items():
            results.append({"id": ds_id, "title": ds_title})
        return results
