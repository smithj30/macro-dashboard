"""
Data transformation utilities: YoY, MoM percent change, merge, resampling.
"""

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Percent-change transforms
# ---------------------------------------------------------------------------

def year_over_year(series: pd.Series) -> pd.Series:
    """
    Compute year-over-year percent change.
    Assumes a DatetimeIndex. Tries 12-period shift first (monthly),
    falls back to 4-period (quarterly) or 1-period (annual) based on
    inferred frequency.
    """
    freq = pd.infer_freq(series.index)
    if freq is None:
        # guess from median gap
        gaps = series.index.to_series().diff().dt.days.dropna()
        median_gap = gaps.median()
        if median_gap <= 10:
            periods = 252  # daily → ~1 year of trading days
        elif median_gap <= 35:
            periods = 12   # monthly
        elif median_gap <= 100:
            periods = 4    # quarterly
        else:
            periods = 1    # annual
    elif freq.startswith("M") or freq.startswith("MS"):
        periods = 12
    elif freq.startswith("Q"):
        periods = 4
    elif freq.startswith("A") or freq.startswith("Y"):
        periods = 1
    elif freq.startswith("W"):
        periods = 52
    elif freq.startswith("D") or freq.startswith("B"):
        periods = 252
    else:
        periods = 12  # default assumption

    result = series.pct_change(periods=periods) * 100
    result.name = f"{series.name} (YoY %)"
    return result


def month_over_month(series: pd.Series) -> pd.Series:
    """Compute month-over-month (1-period) percent change."""
    result = series.pct_change(periods=1) * 100
    result.name = f"{series.name} (MoM %)"
    return result


# ---------------------------------------------------------------------------
# Merge / align utilities
# ---------------------------------------------------------------------------

def merge_series(series_list: list[pd.Series], how: str = "outer") -> pd.DataFrame:
    """
    Merge a list of named Series on their date index.

    Parameters
    ----------
    series_list : list of pd.Series, each with a DatetimeIndex and a .name
    how : 'outer' (default) keeps all dates; 'inner' keeps only common dates

    Returns
    -------
    pd.DataFrame with one column per series
    """
    if not series_list:
        return pd.DataFrame()

    df = pd.concat(series_list, axis=1, join=how)
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"
    df = df.sort_index()
    return df


def merge_dataframes(df_list: list[pd.DataFrame], how: str = "outer") -> pd.DataFrame:
    """
    Merge a list of DataFrames on their date index.
    """
    if not df_list:
        return pd.DataFrame()

    result = df_list[0]
    for df in df_list[1:]:
        result = result.join(df, how=how, rsuffix="_dup")
    result.index = pd.to_datetime(result.index)
    result.index.name = "date"
    result = result.sort_index()
    return result


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------

def summary_statistics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a summary statistics table for numeric columns.
    Includes: count, mean, std, min, 25%, 50%, 75%, max, skew, kurt.
    """
    numeric = df.select_dtypes(include=[np.number])
    if numeric.empty:
        return pd.DataFrame()

    desc = numeric.describe().T
    desc["skew"] = numeric.skew()
    desc["kurt"] = numeric.kurt()
    desc.index.name = "series"
    return desc.round(4)


# ---------------------------------------------------------------------------
# Rolling transforms
# ---------------------------------------------------------------------------

def rolling_mean(series: pd.Series, window: int) -> pd.Series:
    result = series.rolling(window=window).mean()
    result.name = f"{series.name} ({window}-period MA)"
    return result


# ---------------------------------------------------------------------------
# New v2 transforms
# ---------------------------------------------------------------------------

def index_to_date(series: pd.Series, base_date: str = None) -> pd.Series:
    """
    Rebase a series to 100 at the given date (or the first date if not specified).

    Useful for comparing series with different scales on the same chart.
    """
    if base_date:
        base_ts = pd.Timestamp(base_date)
        # Find the closest date
        idx = series.index.get_indexer([base_ts], method="nearest")[0]
        base_val = series.iloc[idx]
    else:
        base_val = series.dropna().iloc[0]

    if base_val == 0:
        result = series * 0
    else:
        result = (series / base_val) * 100

    result.name = f"{series.name} (indexed)"
    return result


def diff(series: pd.Series, periods: int = 1) -> pd.Series:
    """Compute the first difference (change between consecutive periods)."""
    result = series.diff(periods=periods)
    result.name = f"{series.name} (diff)"
    return result


def cumulative(series: pd.Series) -> pd.Series:
    """Compute cumulative sum of the series."""
    result = series.cumsum()
    result.name = f"{series.name} (cumulative)"
    return result


def log_transform(series: pd.Series) -> pd.Series:
    """Compute natural log of the series. Handles non-positive values with NaN."""
    result = np.log(series.where(series > 0))
    result.name = f"{series.name} (log)"
    return result


def resample_series(series: pd.Series, freq: str, agg: str = "mean") -> pd.Series:
    """
    Resample a series to a target frequency.

    freq examples: 'MS' (month start), 'QS', 'A'
    agg: 'mean', 'last', 'sum', 'first'
    """
    resampled = series.resample(freq).agg(agg)
    resampled.name = series.name
    return resampled
