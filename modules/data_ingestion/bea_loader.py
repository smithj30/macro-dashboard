"""
BEA API integration.

Loads BEA_API_KEY from .env via python-dotenv.
"""

import os
from datetime import datetime
from typing import Optional, Tuple

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

_BEA_URL = "https://apps.bea.gov/api/data/"

# Datasets that use TableName + Frequency parameters (same data structure)
SUPPORTED_DATASETS = {
    "NIPA": "National Income and Product Accounts",
    "FixedAssets": "Fixed Assets",
}

# Datasets that only support Annual frequency
ANNUAL_ONLY_DATASETS = {"FixedAssets"}


def get_bea_key_status() -> Tuple[Optional[str], Optional[str]]:
    """Returns (key, error_message). Mirrors get_fred_client() pattern."""
    key = os.getenv("BEA_API_KEY", "").strip()
    if not key:
        return None, (
            "BEA_API_KEY not set. Register at https://apps.bea.gov/api/signup/ "
            "then add it to your .env file."
        )
    return key, None


def _get_key() -> str:
    key, err = get_bea_key_status()
    if err:
        raise RuntimeError(err)
    return key


def list_bea_tables(dataset: str) -> pd.DataFrame:
    """
    Return a DataFrame of available tables for a dataset.
    Columns: TableName, Description.
    """
    key = _get_key()
    resp = requests.get(
        _BEA_URL,
        params={
            "UserID": key,
            "method": "GetParameterValues",
            "datasetname": dataset,
            "ParameterName": "TableName",
            "ResultFormat": "JSON",
        },
        timeout=20,
    )
    resp.raise_for_status()
    values = resp.json()["BEAAPI"]["Results"]["ParamValue"]
    df = pd.DataFrame(values)[["TableName", "Description"]]
    return df.reset_index(drop=True)


def fetch_bea_table(
    dataset: str,
    table_name: str,
    frequency: str = "Q",
    years: str = "ALL",
    line_codes: Optional[list] = None,
) -> pd.DataFrame:
    """
    Fetch any NIPA-style BEA table.

    Returns a DataFrame with DatetimeIndex and one column per LineDescription.
    Annual tables use January 1 of the year as the date.
    """
    key = _get_key()
    params: dict = {
        "UserID": key,
        "method": "GetData",
        "datasetname": dataset,
        "TableName": table_name,
        "Frequency": frequency,
        "Year": years,
        "ResultFormat": "JSON",
    }

    resp = requests.get(_BEA_URL, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    # BEA sometimes returns errors inside a 200 response
    results = payload["BEAAPI"].get("Results", {})
    if "Data" not in results:
        errmsg = payload["BEAAPI"].get("Error", {}).get("APIErrorDescription", "Unknown BEA error")
        raise RuntimeError(f"BEA API error: {errmsg}")

    rows = results["Data"]
    df = pd.DataFrame(rows)

    if line_codes is not None:
        df = df[df["LineNumber"].isin([str(c) for c in line_codes])]

    if df.empty:
        return pd.DataFrame()

    df["DataValue"] = pd.to_numeric(
        df["DataValue"].astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    )

    def _parse_period(p: str) -> pd.Timestamp:
        if "Q" in str(p):
            year, q = p.split("Q")
            month = (int(q) - 1) * 3 + 1
            return pd.Timestamp(f"{year}-{month:02d}-01")
        return pd.Timestamp(f"{p}-01-01")

    df["date"] = df["TimePeriod"].apply(_parse_period)

    out = df.pivot_table(
        index="date",
        columns="LineDescription",
        values="DataValue",
        aggfunc="first",
    )
    out.index.name = "date"
    return out.sort_index()


def last_n_years(n: int = 5) -> str:
    """Return a comma-separated string of the last N years for BEA Year parameter."""
    current = datetime.now().year
    return ",".join(str(y) for y in range(current - n + 1, current + 1))


# ── Convenience wrappers (backward compatible) ────────────────────────────────

def fetch_bea_nipa(
    table_name: str,
    frequency: str = "Q",
    years: str = "ALL",
    line_codes: Optional[list] = None,
) -> pd.DataFrame:
    """Fetch a NIPA table. Kept for backward compatibility."""
    return fetch_bea_table("NIPA", table_name, frequency, years, line_codes)


def fetch_manufacturing_investment() -> pd.DataFrame:
    """
    NIPA Table 5.3.5 (Real Private Fixed Investment by Type, Chained Dollars).
    Lines 3 (Structures) and 4 (Equipment).
    """
    return fetch_bea_nipa("T50305", frequency="Q", years="ALL", line_codes=[3, 4])
