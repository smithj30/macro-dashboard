"""
Simple HTML table scraper using requests + BeautifulSoup.
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup


def scrape_tables(url: str, timeout: int = 15) -> list[pd.DataFrame]:
    """
    Fetch a URL and return all <table> elements as a list of DataFrames.

    Raises requests.RequestException on network errors.
    Raises ValueError if no tables are found.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    tables = soup.find_all("table")

    if not tables:
        raise ValueError(f"No HTML tables found at {url}")

    dfs = []
    for table in tables:
        try:
            # pandas can parse a table element directly via its string
            df_list = pd.read_html(str(table))
            if df_list:
                dfs.append(df_list[0])
        except Exception:
            continue

    if not dfs:
        raise ValueError("Found table tags but could not parse any into DataFrames.")

    return dfs


def scrape_table(url: str, table_index: int = 0) -> tuple[pd.DataFrame, str]:
    """
    Scrape a single table by index from a URL.
    Returns (df, info_message).
    """
    tables = scrape_tables(url)
    if table_index >= len(tables):
        table_index = 0

    df = tables[table_index].copy()

    # Try to detect a date column
    from modules.data_ingestion.file_loader import _detect_date_column
    date_col = _detect_date_column(df)
    msg = f"Scraped {len(tables)} table(s). Showing table #{table_index + 1} ({len(df)} rows)."

    if date_col:
        try:
            df[date_col] = pd.to_datetime(df[date_col], infer_datetime_format=True)
            df = df.set_index(date_col)
            df.index.name = "date"
            msg += f" Auto-detected date column: '{date_col}'."
        except Exception:
            pass

    # Coerce numeric columns
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="ignore")

    return df, msg
