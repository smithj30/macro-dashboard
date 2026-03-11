"""
FRED API integration using the fredapi library.
Loads API key from .env via python-dotenv.
"""

import os
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()


def get_fred_client():
    """Return a Fred client instance, or None if no API key is set."""
    try:
        from fredapi import Fred
    except ImportError:
        return None, "fredapi is not installed."

    api_key = os.getenv("FRED_API_KEY", "").strip()
    if not api_key:
        return None, "FRED_API_KEY not found. Add it to your .env file."

    try:
        client = Fred(api_key=api_key)
        return client, None
    except Exception as e:
        return None, str(e)


def search_fred(query: str, limit: int = 20) -> pd.DataFrame:
    """
    Search FRED for series matching a keyword.

    Returns a DataFrame with columns: id, title, frequency, units,
    seasonal_adjustment, observation_start, observation_end.
    """
    client, err = get_fred_client()
    if err:
        raise RuntimeError(err)

    results = client.search(query, limit=limit)
    if results is None or results.empty:
        return pd.DataFrame()

    keep = [
        "id", "title", "frequency_short", "units_short",
        "seasonal_adjustment_short", "observation_start", "observation_end",
    ]
    available = [c for c in keep if c in results.columns]
    df = results[available].copy()
    df = df.rename(columns={
        "frequency_short": "frequency",
        "units_short": "units",
        "seasonal_adjustment_short": "seasonal_adj",
    })
    # id may be the index
    if "id" not in df.columns:
        df = df.reset_index()
    return df.reset_index(drop=True)


def load_fred_series(series_id: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    Load a FRED series by ID.

    Returns a DataFrame with a DatetimeIndex and a single column named
    after the series_id.
    """
    client, err = get_fred_client()
    if err:
        raise RuntimeError(err)

    kwargs = {}
    if start_date:
        kwargs["observation_start"] = start_date
    if end_date:
        kwargs["observation_end"] = end_date

    series = client.get_series(series_id, **kwargs)
    if series is None or series.empty:
        raise ValueError(f"No data returned for series '{series_id}'.")

    df = series.to_frame(name=series_id)
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"
    df = df.dropna()
    return df


def get_series_info(series_id: str) -> dict:
    """Return metadata for a FRED series."""
    client, err = get_fred_client()
    if err:
        raise RuntimeError(err)

    info = client.get_series_info(series_id)
    return info.to_dict() if hasattr(info, "to_dict") else {}


def _fred_api_key() -> str:
    """Return the FRED API key from env."""
    return os.getenv("FRED_API_KEY", "").strip()


def get_series_release_source(series_id: str) -> dict:
    """
    Fetch the release name and originating source for a FRED series.

    Uses the FRED REST API directly (fredapi doesn't wrap these endpoints).
    Returns {"release": "...", "release_id": ..., "source": "..."}.
    """
    api_key = _fred_api_key()
    if not api_key:
        return {}

    result = {}
    try:
        # Step 1: Get the release for this series
        resp = requests.get(
            "https://api.stlouisfed.org/fred/series/release",
            params={"series_id": series_id, "api_key": api_key, "file_type": "json"},
            timeout=10,
        )
        resp.raise_for_status()
        releases = resp.json().get("releases", [])
        if releases:
            rel = releases[0]
            result["release"] = rel.get("name", "")
            release_id = rel.get("id")
            result["release_id"] = release_id

            # Step 2: Get the source for this release
            if release_id:
                resp2 = requests.get(
                    "https://api.stlouisfed.org/fred/release/sources",
                    params={"release_id": release_id, "api_key": api_key, "file_type": "json"},
                    timeout=10,
                )
                resp2.raise_for_status()
                sources = resp2.json().get("sources", [])
                if sources:
                    result["source"] = sources[0].get("name", "")
    except Exception:
        pass

    return result
