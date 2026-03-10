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
    default_feed_id: Optional[str] = None,
    show_tag_filter: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Render a feed selection dropdown with optional tag filter.

    Returns the selected feed dict, or None if nothing selected.
    """
    # Optional inline tag filter
    _active_tags = tag_filter
    if show_tag_filter and tag_filter is None:
        try:
            from modules.config.tag_catalog import list_tags as _fp_list_tags
            _all_tags = _fp_list_tags()
            if _all_tags:
                _tag_names = ["All"] + [t["name"] for t in _all_tags]
                _sel_tag = st.selectbox(
                    "Filter by tag",
                    options=_tag_names,
                    key=f"{key}_tag_filter",
                )
                if _sel_tag and _sel_tag != "All":
                    _active_tags = [_sel_tag]
        except Exception:
            pass

    feeds = list_feeds(provider=provider_filter, tags=_active_tags)

    if not feeds:
        st.caption("No feeds registered yet. Add feeds in the Feed Manager.")
        return None

    options = []
    feed_map = {}
    if allow_none:
        options.append("— None —")

    default_index = 0
    for i, f in enumerate(feeds):
        display = f"{f['name']} ({f['provider']}: {f['series_id']})"
        options.append(display)
        feed_map[display] = f
        if default_feed_id and f.get("id") == default_feed_id:
            default_index = i + (1 if allow_none else 0)

    selected = st.selectbox(label, options, index=default_index, key=key, help=help_text)

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
