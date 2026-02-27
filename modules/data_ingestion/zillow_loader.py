"""
Zillow public CSV data ingestion.

Handles the wide-format Zillow CSVs (ZHVI, ZORI, etc.) where columns
are dates and rows are geographic regions.

Zillow CSV structure (typical):
    RegionID | SizeRank | RegionName | RegionType | StateName | ... | 2000-01-31 | 2000-02-29 | ...

This module melts the date columns into a long-format time series
and lets the user filter by region.
"""

import io
import json
import os
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st


# Metadata columns that appear before the date columns in Zillow CSVs
ZILLOW_META_COLS = [
    "RegionID", "SizeRank", "RegionName", "RegionType",
    "StateName", "State", "City", "Metro", "CountyName",
]


def _identify_date_columns(df: pd.DataFrame) -> list[str]:
    """Return column names that look like YYYY-MM-DD date strings."""
    date_cols = []
    for col in df.columns:
        try:
            pd.to_datetime(str(col))
            date_cols.append(col)
        except Exception:
            continue
    return date_cols


def load_zillow_csv(uploaded_file_or_path, value_col_name: str = "value") -> dict:
    """
    Load a Zillow CSV (uploaded file or local path).

    Returns a dict with:
        - 'wide': original DataFrame
        - 'long': melted long-format DataFrame (date, RegionName, value)
        - 'regions': list of unique region names
        - 'date_columns': list of date column strings
        - 'meta_columns': list of non-date metadata columns
    """
    if hasattr(uploaded_file_or_path, "read"):
        # Streamlit UploadedFile
        raw = uploaded_file_or_path.read()
        df = pd.read_csv(io.BytesIO(raw))
    else:
        df = pd.read_csv(uploaded_file_or_path)

    date_cols = _identify_date_columns(df)
    meta_cols = [c for c in df.columns if c not in date_cols]

    if not date_cols:
        raise ValueError(
            "No date columns detected. Expected Zillow-format CSV with columns like '2000-01-31'."
        )

    # Melt to long format
    id_vars = [c for c in meta_cols if c in df.columns]
    long_df = df.melt(id_vars=id_vars, value_vars=date_cols, var_name="date", value_name=value_col_name)
    long_df["date"] = pd.to_datetime(long_df["date"])
    long_df = long_df.sort_values("date").reset_index(drop=True)

    regions = []
    if "RegionName" in long_df.columns:
        regions = sorted(long_df["RegionName"].dropna().unique().tolist())

    return {
        "wide": df,
        "long": long_df,
        "regions": regions,
        "date_columns": date_cols,
        "meta_columns": meta_cols,
    }


def get_region_series(zillow_data: dict, region_name: str, value_col: str = "value") -> pd.DataFrame:
    """
    Extract a single-region time series from melted Zillow data.

    Returns a DataFrame with DatetimeIndex and one column named after the region.
    """
    long = zillow_data["long"]
    mask = long["RegionName"] == region_name
    subset = long[mask][["date", value_col]].dropna()
    subset = subset.set_index("date")
    subset.index.name = "date"
    subset = subset.rename(columns={value_col: region_name})
    return subset


# ── Download / Cache functions ───────────────────────────────────────────────

_DEFAULT_CACHE_DIR = "data/zillow_cache"


@st.cache_data(ttl=86400)
def download_zillow_csv(url: str, cache_dir: str = _DEFAULT_CACHE_DIR) -> pd.DataFrame:
    """Download a Zillow CSV from URL, cache locally, return as DataFrame."""
    os.makedirs(cache_dir, exist_ok=True)
    filename = url.rsplit("/", 1)[-1].split("?")[0]  # strip query params
    local_path = os.path.join(cache_dir, filename)
    meta_path = local_path + ".meta.json"

    resp = requests.get(url, timeout=60)
    resp.raise_for_status()

    with open(local_path, "wb") as f:
        f.write(resp.content)

    meta = {
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "url": url,
        "filename": filename,
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    return pd.read_csv(io.BytesIO(resp.content))


def download_datasets(entries: list, cache_dir: str = _DEFAULT_CACHE_DIR,
                      progress_callback=None) -> list:
    """
    Bulk download from a list of registry entries.

    Returns list of result dicts: {entry, success, error, row_count}.
    Calls optional progress_callback(i, total) after each download.
    """
    os.makedirs(cache_dir, exist_ok=True)
    results = []
    total = len(entries)
    for i, entry in enumerate(entries):
        try:
            df = download_zillow_csv(entry["url"], cache_dir=cache_dir)
            results.append({
                "entry": entry,
                "success": True,
                "error": None,
                "row_count": len(df),
            })
        except Exception as exc:
            results.append({
                "entry": entry,
                "success": False,
                "error": str(exc),
                "row_count": 0,
            })
        if progress_callback:
            progress_callback(i + 1, total)
    return results


def get_cached_datasets(cache_dir: str = _DEFAULT_CACHE_DIR) -> list:
    """
    Scan cache_dir for downloaded CSVs with companion .meta.json files.

    Returns list of {filename, downloaded_at, size_bytes, url}.
    """
    if not os.path.isdir(cache_dir):
        return []
    results = []
    for fname in sorted(os.listdir(cache_dir)):
        if not fname.endswith(".csv"):
            continue
        csv_path = os.path.join(cache_dir, fname)
        meta_path = csv_path + ".meta.json"
        if not os.path.isfile(meta_path):
            continue
        with open(meta_path) as f:
            meta = json.load(f)
        results.append({
            "filename": fname,
            "downloaded_at": meta.get("downloaded_at", ""),
            "size_bytes": os.path.getsize(csv_path),
            "url": meta.get("url", ""),
        })
    return results


def is_cache_stale(meta_path: str) -> bool:
    """
    Check if a cached dataset is stale.

    Zillow updates monthly around the 16th. Cache is stale if downloaded_at
    is before the 16th of the current month and today is past the 16th.
    """
    if not os.path.isfile(meta_path):
        return True
    with open(meta_path) as f:
        meta = json.load(f)
    downloaded_str = meta.get("downloaded_at", "")
    if not downloaded_str:
        return True
    downloaded = datetime.fromisoformat(downloaded_str)
    now = datetime.now(timezone.utc)
    # If today is past the 16th, cache is stale if downloaded before the 16th of this month
    if now.day >= 16:
        cutoff = datetime(now.year, now.month, 16, tzinfo=timezone.utc)
        return downloaded < cutoff
    return False


def _any_cache_stale(cache_dir: str = _DEFAULT_CACHE_DIR) -> bool:
    """Check if any cached dataset is stale."""
    if not os.path.isdir(cache_dir):
        return False
    for fname in os.listdir(cache_dir):
        if fname.endswith(".meta.json"):
            if is_cache_stale(os.path.join(cache_dir, fname)):
                return True
    return False


def _latest_download_date(cache_dir: str = _DEFAULT_CACHE_DIR) -> str:
    """Return the most recent downloaded_at date string, or empty."""
    cached = get_cached_datasets(cache_dir)
    if not cached:
        return ""
    dates = [c["downloaded_at"] for c in cached if c["downloaded_at"]]
    return max(dates) if dates else ""


def load_zillow_series(entry: dict, regions: list = None,
                       cache_dir: str = _DEFAULT_CACHE_DIR) -> pd.DataFrame:
    """
    Load a Zillow dataset from cache (or download if not cached),
    then extract region time series into a merged DataFrame.

    Args:
        entry: registry entry dict with 'url' and 'filename' keys
        regions: list of region names to include (None = all)
        cache_dir: local cache directory

    Returns:
        DataFrame with DatetimeIndex and columns = region names.
    """
    filename = entry["filename"] + ".csv"
    local_path = os.path.join(cache_dir, filename)

    # Load from cache if available, otherwise download
    if os.path.isfile(local_path):
        zillow_data = load_zillow_csv(local_path)
    else:
        download_zillow_csv(entry["url"], cache_dir=cache_dir)
        zillow_data = load_zillow_csv(local_path)

    available_regions = zillow_data["regions"]
    if regions:
        target_regions = [r for r in regions if r in available_regions]
    else:
        target_regions = available_regions

    if not target_regions:
        return pd.DataFrame()

    dfs = []
    for region in target_regions:
        series_df = get_region_series(zillow_data, region)
        dfs.append(series_df)

    if len(dfs) == 1:
        return dfs[0]

    merged = dfs[0]
    for df in dfs[1:]:
        merged = merged.join(df, how="outer")
    return merged
