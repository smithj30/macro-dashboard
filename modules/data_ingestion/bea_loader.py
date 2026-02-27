"""
BEA API integration — NIPA fixed investment data.

Loads BEA_API_KEY from .env via python-dotenv.
"""

import os
from typing import Optional

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

_BEA_URL = "https://apps.bea.gov/api/data/"


def _get_key() -> str:
    key = os.getenv("BEA_API_KEY", "").strip()
    if not key:
        raise RuntimeError("BEA_API_KEY not found. Add it to your .env file.")
    return key


def fetch_bea_nipa(
    table_name: str,
    frequency: str = "Q",
    years: str = "ALL",
    line_codes: Optional[list] = None,
) -> pd.DataFrame:
    """
    Fetch NIPA data from BEA.

    Returns a DataFrame with DatetimeIndex and one column per LineDescription.
    Values are in billions of chained 2017 dollars (BEA standard units).
    """
    params = {
        "UserID": _get_key(),
        "method": "GetData",
        "datasetname": "NIPA",
        "TableName": table_name,
        "Frequency": frequency,
        "Year": years,
        "ResultFormat": "JSON",
    }

    resp = requests.get(_BEA_URL, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    rows = payload["BEAAPI"]["Results"]["Data"]
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


def fetch_manufacturing_investment() -> pd.DataFrame:
    """
    NIPA Table 5.3.5 (Real Private Fixed Investment by Type, Chained Dollars).
    Lines 3 (Structures) and 4 (Equipment).
    Units: billions of chained 2017 dollars, quarterly.
    """
    return fetch_bea_nipa("T50305", frequency="Q", years="ALL", line_codes=[3, 4])
