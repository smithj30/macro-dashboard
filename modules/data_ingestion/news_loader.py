"""
Reuters news feed via RapidAPI.

Requires RAPIDAPI_KEY in .env.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import requests


_RAPIDAPI_HOST = "reuters-business-and-financial-news.p.rapidapi.com"
_BASE_URL = f"https://{_RAPIDAPI_HOST}"


def fetch_reuters_headlines(query: str, page_size: int = 10) -> List[Dict[str, Any]]:
    """
    Fetch article headlines from the Reuters RapidAPI endpoint.

    Parameters
    ----------
    query     : keyword search string (e.g. "US manufacturing reshoring")
    page_size : max articles to return

    Returns
    -------
    List of dicts with keys: title, url, published_at, description

    Raises
    ------
    RuntimeError if RAPIDAPI_KEY is not set
    requests.HTTPError on non-2xx responses
    """
    api_key = os.getenv("RAPIDAPI_KEY", "")
    if not api_key:
        raise RuntimeError(
            "RAPIDAPI_KEY not set. Add it to your .env file to enable news feeds."
        )

    url = f"{_BASE_URL}/get-articles-by-keyword-name/{query}/{page_size}"
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": _RAPIDAPI_HOST,
    }

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()

    # The API may return a list directly or nest under a key
    if isinstance(data, list):
        raw_articles = data
    elif isinstance(data, dict):
        # Try common wrapper keys
        for key in ("articles", "data", "results", "items"):
            if key in data and isinstance(data[key], list):
                raw_articles = data[key]
                break
        else:
            raw_articles = []
    else:
        raw_articles = []

    articles = []
    for item in raw_articles:
        if not isinstance(item, dict):
            continue
        articles.append(
            {
                "title": item.get("articlesName") or item.get("title") or item.get("headline") or "",
                "url": item.get("articlesUrl") or item.get("url") or item.get("link") or "",
                "published_at": item.get("published_at") or item.get("publishedAt") or item.get("date") or "",
                "description": item.get("description") or item.get("summary") or item.get("excerpt") or "",
            }
        )

    return articles
