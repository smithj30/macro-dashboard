"""
CSV and Excel file upload support with automatic date column detection.
"""

import io
from typing import Optional

import pandas as pd


def _detect_date_column(df: pd.DataFrame) -> Optional[str]:
    """
    Try to find a column that looks like a date.
    Checks column names first (heuristic), then tries parsing each column.
    """
    date_hints = {"date", "time", "period", "month", "year", "quarter", "week", "datetime", "timestamp"}

    for col in df.columns:
        if any(hint in col.lower() for hint in date_hints):
            try:
                pd.to_datetime(df[col])
                return col
            except Exception:
                continue

    # Fallback: try every object / string column
    for col in df.columns:
        if df[col].dtype == object:
            try:
                parsed = pd.to_datetime(df[col], infer_datetime_format=True)
                if parsed.notna().sum() > len(df) * 0.8:
                    return col
            except Exception:
                continue

    return None


def load_uploaded_file(uploaded_file) -> tuple[pd.DataFrame, str]:
    """
    Load a Streamlit UploadedFile (CSV or Excel) into a DataFrame.

    Returns (df, message) where message describes any auto-detection that occurred.
    """
    name = uploaded_file.name.lower()
    msg_parts = []

    if name.endswith(".csv"):
        raw = uploaded_file.read()
        # Try common encodings
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                df = pd.read_csv(io.BytesIO(raw), encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("Could not decode the CSV file with common encodings.")
    elif name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(uploaded_file)
    else:
        raise ValueError(f"Unsupported file type: {uploaded_file.name}")

    # Detect and parse date column
    date_col = _detect_date_column(df)
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], infer_datetime_format=True)
        df = df.set_index(date_col)
        df.index.name = "date"
        msg_parts.append(f"Auto-detected date column: '{date_col}'")
    else:
        msg_parts.append("No date column detected — using default integer index.")

    # Drop fully-empty columns
    before = len(df.columns)
    df = df.dropna(axis=1, how="all")
    dropped = before - len(df.columns)
    if dropped:
        msg_parts.append(f"Dropped {dropped} empty column(s).")

    # Coerce numeric columns
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="ignore")

    return df, " | ".join(msg_parts)


def load_csv_from_path(path: str) -> tuple[pd.DataFrame, str]:
    """Load a CSV from a local file path (used by Zillow loader)."""
    df = pd.read_csv(path)
    date_col = _detect_date_column(df)
    msg = ""
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.set_index(date_col)
        df.index.name = "date"
        msg = f"Date column: '{date_col}'"
    return df, msg
