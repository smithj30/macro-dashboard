"""
News provider — supports both RSS/Atom feeds (via feedparser) and
the existing Reuters RapidAPI source.
"""

from typing import Any, Dict, List, Optional

import pandas as pd

from providers.base_provider import BaseProvider


class NewsProvider(BaseProvider):

    @property
    def name(self) -> str:
        return "News/RSS"

    def fetch_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Fetch news articles.

        series_id: either an RSS/Atom URL or a search query for Reuters.
        kwargs:
            source: 'rss' or 'reuters' (default: auto-detect)
            limit: max articles (default 10)
        """
        source = kwargs.get("source", "auto")
        limit = kwargs.get("limit", 10)

        if source == "auto":
            source = "rss" if series_id.startswith("http") else "reuters"

        if source == "rss":
            return self._fetch_rss(series_id, limit)
        else:
            return self._fetch_reuters(series_id, limit)

    def search(self, query: str, limit: int = 20) -> pd.DataFrame:
        """Search is not applicable for news — return empty."""
        return pd.DataFrame()

    def check_status(self) -> tuple:
        # Check if feedparser is available
        try:
            import feedparser  # noqa: F401
            rss_ok = True
        except ImportError:
            rss_ok = False

        # Check if Reuters API key is set
        import os
        reuters_ok = bool(os.getenv("RAPIDAPI_KEY", "").strip())

        parts = []
        if rss_ok:
            parts.append("RSS/Atom: available")
        else:
            parts.append("RSS/Atom: install feedparser")
        if reuters_ok:
            parts.append("Reuters: API key configured")
        else:
            parts.append("Reuters: no API key")

        return True, "; ".join(parts)

    @staticmethod
    def _fetch_rss(url: str, limit: int) -> pd.DataFrame:
        """Parse an RSS/Atom feed URL into a DataFrame of articles."""
        try:
            import feedparser
        except ImportError:
            raise RuntimeError(
                "feedparser is not installed. Run: pip install feedparser"
            )

        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:limit]:
            articles.append({
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "published_at": entry.get("published", ""),
                "description": entry.get("summary", ""),
            })

        return pd.DataFrame(articles)

    @staticmethod
    def _fetch_reuters(query: str, limit: int) -> pd.DataFrame:
        """Fetch from Reuters via existing RapidAPI loader."""
        from modules.data_ingestion.news_loader import fetch_reuters_headlines

        articles = fetch_reuters_headlines(query, page_size=limit)
        return pd.DataFrame(articles)
