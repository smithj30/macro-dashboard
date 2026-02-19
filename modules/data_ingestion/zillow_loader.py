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
import pandas as pd


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
