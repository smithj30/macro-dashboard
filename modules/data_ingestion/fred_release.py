"""
FRED release date fetcher.

Provides get_release_dates(series_id) → (prior_date_str, next_date_str)
wrapping fredapi's series release and release dates endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple


def get_release_dates(series_id: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Return (prior_date, next_date) for a FRED series.

    - prior_date: most recent past release date (YYYY-MM-DD or None)
    - next_date:  nearest upcoming release date (YYYY-MM-DD or None)
    Returns (None, None) on any error.
    """
    try:
        from modules.data_ingestion.fred_loader import get_fred_client

        client, err = get_fred_client()
        if err:
            return None, None

        # Get the release associated with this series
        release_df = client.get_series_release(series_id)
        if release_df is None:
            return None, None
        if hasattr(release_df, "empty") and release_df.empty:
            return None, None

        # Extract the release_id
        if "id" in release_df.columns:
            release_id = int(release_df["id"].iloc[0])
        elif hasattr(release_df, "index") and len(release_df.index) > 0:
            release_id = int(release_df.index[0])
        else:
            return None, None

        today_str = datetime.today().strftime("%Y-%m-%d")

        # --- Past release dates ---
        prior: Optional[str] = None
        try:
            past = client.get_release_dates(
                release_id,
                realtime_start="2000-01-01",
                realtime_end=today_str,
                limit=200,
                sort_order="desc",
                include_release_dates_with_no_data=False,
            )
            if past is not None and len(past) > 0:
                candidates = sorted(
                    [str(d)[:10] for d in past if str(d)[:10] <= today_str],
                    reverse=True,
                )
                if candidates:
                    prior = candidates[0]
        except Exception:
            pass

        # --- Future release dates ---
        nxt: Optional[str] = None
        try:
            future = client.get_release_dates(
                release_id,
                realtime_start=today_str,
                realtime_end="2099-12-31",
                limit=5,
                sort_order="asc",
                include_release_dates_with_no_data=False,
            )
            if future is not None and len(future) > 0:
                candidates = sorted(
                    [str(d)[:10] for d in future if str(d)[:10] > today_str]
                )
                if candidates:
                    nxt = candidates[0]
        except Exception:
            pass

        return prior, nxt

    except Exception:
        return None, None
