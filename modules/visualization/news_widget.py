"""
Shared Streamlit news feed renderer.

Uses a 15-minute cache. Degrades gracefully when the API key is missing
or the request fails.
"""

from __future__ import annotations

import streamlit as st

from modules.data_ingestion.news_loader import fetch_reuters_headlines


@st.cache_data(ttl=900, show_spinner=False)
def _fetch_cached(query: str, page_size: int):
    """Cached wrapper around fetch_reuters_headlines."""
    return fetch_reuters_headlines(query, page_size=page_size)


def render_news_section(
    query: str,
    title: str = "Latest News",
    page_size: int = 8,
) -> None:
    """
    Render a news feed section in Streamlit.

    Shows bold linked headlines, date captions, and description snippets.
    Degrades gracefully: shows st.info() if key missing, st.warning() on error.
    """
    if not query:
        return

    st.markdown("---")
    st.subheader(title)

    try:
        articles = _fetch_cached(query, page_size)
    except RuntimeError as e:
        st.info(str(e))
        return
    except Exception as e:
        st.warning(f"Could not load news: {e}")
        return

    if not articles:
        st.caption("No headlines found for this query.")
        return

    for article in articles:
        headline = article.get("title", "").strip()
        url = article.get("url", "").strip()
        date = article.get("published_at", "").strip()
        desc = article.get("description", "").strip()

        if not headline:
            continue

        if url:
            st.markdown(f"**[{headline}]({url})**")
        else:
            st.markdown(f"**{headline}**")

        if date:
            st.caption(date)

        if desc:
            # Truncate long descriptions
            snippet = desc if len(desc) <= 200 else desc[:197] + "…"
            st.markdown(snippet)

        st.markdown("---")
