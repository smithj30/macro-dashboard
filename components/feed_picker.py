"""
Feed Picker — reusable Streamlit widget for selecting feeds from the catalog.

Usage:
    from components.feed_picker import feed_picker
    selected = feed_picker(key="my_picker")
    # selected is a feed dict or None
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List

import streamlit as st

from modules.config.feed_catalog import list_feeds


def feed_picker(
    key: str = "feed_picker",
    label: str = "Select a data feed",
    provider_filter: Optional[str] = None,
    tag_filter: Optional[List[str]] = None,
    allow_none: bool = True,
    help_text: str = "Choose a registered data feed",
) -> Optional[Dict[str, Any]]:
    """
    Render a feed selection dropdown.

    Returns the selected feed dict, or None if nothing selected.
    """
    feeds = list_feeds(provider=provider_filter, tags=tag_filter)

    if not feeds:
        st.caption("No feeds registered yet. Add feeds in the Feed Manager.")
        return None

    options = []
    feed_map = {}
    if allow_none:
        options.append("— None —")

    for f in feeds:
        display = f"{f['name']} ({f['provider']}: {f['series_id']})"
        options.append(display)
        feed_map[display] = f

    selected = st.selectbox(label, options, key=key, help=help_text)

    if selected == "— None —" or selected is None:
        return None

    return feed_map.get(selected)


def multi_feed_picker(
    key: str = "multi_feed_picker",
    label: str = "Select data feeds",
    provider_filter: Optional[str] = None,
    tag_filter: Optional[List[str]] = None,
    help_text: str = "Choose one or more registered data feeds",
) -> List[Dict[str, Any]]:
    """
    Render a multi-select feed picker.

    Returns list of selected feed dicts.
    """
    feeds = list_feeds(provider=provider_filter, tags=tag_filter)

    if not feeds:
        st.caption("No feeds registered yet. Add feeds in the Feed Manager.")
        return []

    options = []
    feed_map = {}
    for f in feeds:
        display = f"{f['name']} ({f['provider']}: {f['series_id']})"
        options.append(display)
        feed_map[display] = f

    selected = st.multiselect(label, options, key=key, help=help_text)

    return [feed_map[s] for s in selected if s in feed_map]
