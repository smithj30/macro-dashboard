"""
Data resolver — single entry point for fetching feed data.

Every call site that needs data from a feed should go through here
instead of manually calling get_provider().fetch_series().
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from modules.config.feed_catalog import get_feed
from providers import get_provider

logger = logging.getLogger(__name__)


def resolve_feed_data(
    feed_id_or_feed,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Fetch data for a feed by ID or feed dict.

    Parameters
    ----------
    feed_id_or_feed : str or dict
        Either a feed_id string or the full feed dict.
    start_date, end_date : optional date strings

    Returns
    -------
    pd.DataFrame  (may be empty if fetch fails)
    """
    if isinstance(feed_id_or_feed, str):
        feed = get_feed(feed_id_or_feed)
        if feed is None:
            return pd.DataFrame()
    else:
        feed = feed_id_or_feed

    provider_name = feed.get("provider", "")
    series_id = feed.get("series_id", "")
    params = dict(feed.get("params", {}))

    if not provider_name:
        return pd.DataFrame()

    # Remove keys that are already passed as explicit arguments to avoid
    # "got multiple values for argument" TypeError.
    params.pop("series_id", None)
    params.pop("start_date", None)
    params.pop("end_date", None)

    try:
        prov = get_provider(provider_name)
        df = prov.fetch_series(
            series_id,
            start_date=start_date,
            end_date=end_date,
            **params,
        )
        if df is None:
            return pd.DataFrame()
        return df
    except Exception:
        logger.exception("resolve_feed_data failed for %s", feed.get("id", feed_id_or_feed))
        return pd.DataFrame()
