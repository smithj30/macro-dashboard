"""
Feed Manager — browse, add, edit, preview, and delete data feeds.

Feeds are named references to data series from any provider (FRED, BEA,
Zillow, RSS, file). Once registered, they can be used in charts and
dashboards by feed_id instead of embedding raw series IDs.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from modules.config.feed_catalog import (
    list_feeds,
    get_feed,
    find_feed,
    create_feed,
    update_feed,
    delete_feed,
    bulk_create_feeds,
    mark_refreshed,
    feed_count,
)
from providers import PROVIDERS, get_provider


def _init_state():
    """Initialise Feed Manager session state."""
    if "fm_mode" not in st.session_state:
        st.session_state.fm_mode = "browse"  # browse | add | edit | preview
    if "fm_edit_id" not in st.session_state:
        st.session_state.fm_edit_id = None
    if "fm_search_results" not in st.session_state:
        st.session_state.fm_search_results = None
    if "fm_pending_delete" not in st.session_state:
        st.session_state.fm_pending_delete = None  # feed_id awaiting confirmation


def render():
    """Main render function for the Feed Manager page."""
    _init_state()

    st.title("Feed Manager")
    st.caption(f"{feed_count()} registered feed(s)")

    # Toolbar
    col_add, col_bulk, col_refresh = st.columns([1, 1, 1])
    with col_add:
        if st.button("Add Feed", use_container_width=True, type="primary"):
            st.session_state.fm_mode = "add"
            st.session_state.fm_search_results = None
            st.rerun()
    with col_bulk:
        if st.button("Bulk Add", use_container_width=True):
            st.session_state.fm_mode = "bulk"
            st.rerun()
    with col_refresh:
        if st.button("Back to Browse", use_container_width=True):
            st.session_state.fm_mode = "browse"
            st.session_state.fm_edit_id = None
            st.rerun()

    st.markdown("---")

    mode = st.session_state.fm_mode
    if mode == "add":
        _render_add_feed()
    elif mode == "bulk":
        _render_bulk_add()
    elif mode == "edit":
        _render_edit_feed()
    elif mode == "preview":
        _render_preview_feed()
    else:
        _render_browse()


# ---------------------------------------------------------------------------
# Browse
# ---------------------------------------------------------------------------

def _render_browse():
    """List all feeds with filter/search."""
    # Filters
    col_prov, col_tag, col_search = st.columns([1, 1, 2])
    with col_prov:
        provider_names = ["All"] + list(PROVIDERS.keys())
        prov_filter = st.selectbox("Provider", provider_names, key="fm_prov_filter")
    with col_tag:
        tag_input = st.text_input("Tag filter", key="fm_tag_filter", placeholder="e.g. labor")
    with col_search:
        name_search = st.text_input("Search by name", key="fm_name_search", placeholder="Search...")

    provider = prov_filter if prov_filter != "All" else None
    tags = [t.strip() for t in tag_input.split(",") if t.strip()] if tag_input else None
    feeds = list_feeds(provider=provider, tags=tags)

    if name_search:
        q = name_search.lower()
        feeds = [f for f in feeds if q in f.get("name", "").lower() or q in f.get("series_id", "").lower()]

    if not feeds:
        st.info("No feeds match your filters. Use **Add Feed** to register data sources.")
        return

    # Display as table
    for feed in feeds:
        is_computed = feed.get("provider") == "computed"
        with st.container():
            cols = st.columns([3, 2, 2, 1, 1, 1])
            with cols[0]:
                st.markdown(f"**{feed['name']}**")
                # Show formula subtitle for computed feeds
                if is_computed:
                    params = feed.get("params", {})
                    op_a_feed = get_feed(params.get("operand_a", ""))
                    op_b_feed = get_feed(params.get("operand_b", ""))
                    op_name = params.get("operation", "?")
                    op_sym = {"div": "/", "sub": "-", "add": "+", "mul": "*", "pct_diff": "% diff"}.get(op_name, op_name)
                    a_name = op_a_feed["name"] if op_a_feed else "?"
                    b_name = op_b_feed["name"] if op_b_feed else "?"
                    st.caption(f"= {a_name} {op_sym} {b_name}")
            with cols[1]:
                st.caption(f"{feed['provider']}: {feed['series_id']}")
            with cols[2]:
                tags_str = ", ".join(feed.get("tags", []))
                if tags_str:
                    st.caption(f"Tags: {tags_str}")
            with cols[3]:
                if is_computed:
                    if st.button("Edit Formula", key=f"fm_editcomp_{feed['id']}", use_container_width=True):
                        st.session_state.de_edit_computed_id = feed["id"]
                        st.session_state.page = "Data Explorer"
                        st.rerun()
                else:
                    if st.button("Preview", key=f"fm_prev_{feed['id']}", use_container_width=True):
                        st.session_state.fm_mode = "preview"
                        st.session_state.fm_edit_id = feed["id"]
                        st.rerun()
            with cols[4]:
                if st.button("Edit", key=f"fm_edit_{feed['id']}", use_container_width=True):
                    st.session_state.fm_mode = "edit"
                    st.session_state.fm_edit_id = feed["id"]
                    st.rerun()
            with cols[5]:
                if st.session_state.fm_pending_delete == feed["id"]:
                    if st.button("Confirm", key=f"fm_del_confirm_{feed['id']}", use_container_width=True, type="primary"):
                        delete_feed(feed["id"])
                        st.session_state.fm_pending_delete = None
                        st.rerun()
                else:
                    if st.button("Delete", key=f"fm_del_{feed['id']}", use_container_width=True):
                        st.session_state.fm_pending_delete = feed["id"]
                        st.rerun()
            st.markdown("---")


# ---------------------------------------------------------------------------
# Add Feed
# ---------------------------------------------------------------------------

def _render_add_feed():
    """Step-by-step form to add a new feed."""
    st.subheader("Add New Feed")

    # Step 1: Pick provider
    provider_name = st.selectbox(
        "Data Provider",
        list(PROVIDERS.keys()),
        key="fm_add_provider",
        format_func=lambda p: f"{p} — {PROVIDERS[p]().name}",
    )

    provider = get_provider(provider_name)
    ok, status_msg = provider.check_status()
    if not ok:
        st.warning(status_msg)

    # Step 2: Search or enter series ID
    st.markdown("#### Find Series")

    search_col, id_col = st.columns([2, 1])
    with search_col:
        search_query = st.text_input(
            "Search for a series",
            key="fm_add_search",
            placeholder="e.g. unemployment rate",
        )
        if st.button("Search", key="fm_add_search_btn") and search_query:
            try:
                results = provider.search(search_query, limit=15)
                st.session_state.fm_search_results = results
            except Exception as e:
                st.error(f"Search failed: {e}")

    with id_col:
        manual_id = st.text_input(
            "Or enter series ID directly",
            key="fm_add_manual_id",
            placeholder="e.g. UNRATE",
        )

    # Show search results
    if st.session_state.fm_search_results is not None and not st.session_state.fm_search_results.empty:
        st.markdown("##### Search Results")
        results_df = st.session_state.fm_search_results
        st.dataframe(results_df, use_container_width=True, height=300)

        # Let user pick from results
        if "id" in results_df.columns:
            result_ids = results_df["id"].tolist()
            selected_id = st.selectbox("Select from results", result_ids, key="fm_add_result_select")
        else:
            selected_id = None
    else:
        selected_id = None

    # Determine final series_id
    series_id = manual_id or selected_id
    if not series_id:
        st.info("Search for a series or enter a series ID to continue.")
        return

    # Step 3: Check if already registered
    existing = find_feed(provider_name, series_id)
    if existing:
        st.warning(f"This series is already registered as feed '{existing['name']}' ({existing['id']})")

    # Step 4: Metadata
    st.markdown("#### Feed Details")

    # Try to get metadata from provider
    meta = {}
    try:
        meta = provider.get_metadata(series_id)
    except Exception:
        pass

    default_name = meta.get("title", series_id)
    if isinstance(default_name, dict):
        default_name = series_id

    feed_name = st.text_input("Feed Name", value=str(default_name), key="fm_add_name")
    col_freq, col_units = st.columns(2)
    with col_freq:
        frequency = st.text_input(
            "Frequency",
            value=str(meta.get("frequency", meta.get("frequency_short", ""))),
            key="fm_add_freq",
        )
    with col_units:
        units = st.text_input(
            "Units",
            value=str(meta.get("units", meta.get("units_short", ""))),
            key="fm_add_units",
        )

    tags_input = st.text_input(
        "Tags (comma-separated)",
        key="fm_add_tags",
        placeholder="e.g. labor, unemployment, monthly",
    )
    tags = [t.strip() for t in tags_input.split(",") if t.strip()] if tags_input else []

    refresh_schedule = st.selectbox(
        "Refresh Schedule",
        ["daily", "weekly", "monthly", "manual"],
        key="fm_add_refresh",
    )

    # Step 5: Save
    if st.button("Register Feed", type="primary", use_container_width=True):
        if not feed_name:
            st.error("Feed name is required.")
            return

        feed = create_feed(
            name=feed_name,
            provider=provider_name,
            series_id=series_id,
            frequency=frequency,
            units=units,
            tags=tags,
            refresh_schedule=refresh_schedule,
            provider_metadata=meta,
        )
        st.success(f"Feed registered: **{feed['name']}** ({feed['id']})")
        st.session_state.fm_mode = "browse"
        st.session_state.fm_search_results = None
        st.rerun()


# ---------------------------------------------------------------------------
# Bulk Add
# ---------------------------------------------------------------------------

def _render_bulk_add():
    """Add multiple FRED series at once."""
    st.subheader("Bulk Add Feeds")
    st.caption("Add multiple FRED series IDs at once (one per line).")

    provider_name = st.selectbox(
        "Provider",
        list(PROVIDERS.keys()),
        key="fm_bulk_provider",
    )

    ids_text = st.text_area(
        "Series IDs (one per line)",
        key="fm_bulk_ids",
        height=200,
        placeholder="UNRATE\nPAYEMS\nCPIAUCSL\nGDP",
    )

    tags_input = st.text_input(
        "Tags for all (comma-separated)",
        key="fm_bulk_tags",
        placeholder="e.g. macro, monthly",
    )
    tags = [t.strip() for t in tags_input.split(",") if t.strip()] if tags_input else []

    if st.button("Register All", type="primary", use_container_width=True):
        ids = [line.strip() for line in ids_text.strip().split("\n") if line.strip()]
        if not ids:
            st.error("Enter at least one series ID.")
            return

        provider = get_provider(provider_name)
        feed_defs = []
        failed_ids = []
        progress = st.progress(0, text="Fetching metadata...")

        for i, sid in enumerate(ids):
            progress.progress((i + 1) / len(ids), text=f"Processing {sid}...")
            meta = {}
            try:
                meta = provider.get_metadata(sid)
            except Exception:
                failed_ids.append(sid)

            name = meta.get("title", sid)
            if isinstance(name, dict):
                name = sid

            feed_defs.append({
                "name": str(name),
                "provider": provider_name,
                "series_id": sid,
                "frequency": str(meta.get("frequency", meta.get("frequency_short", ""))),
                "units": str(meta.get("units", meta.get("units_short", ""))),
                "tags": tags,
                "provider_metadata": meta,
            })

        progress.empty()
        created, skipped = bulk_create_feeds(feed_defs)
        if created:
            st.success(f"Registered {len(created)} feed(s).")
        if skipped:
            st.info(f"Skipped {len(skipped)} already-registered series: {', '.join(skipped)}")
        if failed_ids:
            st.warning(
                f"Could not fetch metadata for {len(failed_ids)} ID(s): "
                f"{', '.join(failed_ids)}. These were registered with the series ID as the name — "
                f"edit them in Feed Manager to add details."
            )
        st.session_state.fm_mode = "browse"
        st.rerun()


# ---------------------------------------------------------------------------
# Edit Feed
# ---------------------------------------------------------------------------

def _render_edit_feed():
    """Edit an existing feed's metadata."""
    feed_id = st.session_state.fm_edit_id
    if not feed_id:
        st.session_state.fm_mode = "browse"
        st.rerun()
        return

    feed = get_feed(feed_id)
    if not feed:
        st.error(f"Feed not found: {feed_id}")
        return

    st.subheader(f"Edit Feed: {feed['name']}")
    st.caption(f"ID: {feed['id']} | Provider: {feed['provider']} | Series: {feed['series_id']}")

    feed_name = st.text_input("Name", value=feed["name"], key="fm_edit_name")
    col1, col2 = st.columns(2)
    with col1:
        frequency = st.text_input("Frequency", value=feed.get("frequency", ""), key="fm_edit_freq")
    with col2:
        units = st.text_input("Units", value=feed.get("units", ""), key="fm_edit_units")

    tags_str = ", ".join(feed.get("tags", []))
    tags_input = st.text_input("Tags", value=tags_str, key="fm_edit_tags")
    tags = [t.strip() for t in tags_input.split(",") if t.strip()] if tags_input else []

    refresh_schedule = st.selectbox(
        "Refresh Schedule",
        ["daily", "weekly", "monthly", "manual"],
        index=["daily", "weekly", "monthly", "manual"].index(feed.get("refresh_schedule", "daily")),
        key="fm_edit_refresh",
    )

    if st.button("Save Changes", type="primary", use_container_width=True):
        update_feed(feed_id, {
            "name": feed_name,
            "frequency": frequency,
            "units": units,
            "tags": tags,
            "refresh_schedule": refresh_schedule,
        })
        st.success("Feed updated.")
        st.session_state.fm_mode = "browse"
        st.session_state.fm_edit_id = None
        st.rerun()


# ---------------------------------------------------------------------------
# Preview Feed
# ---------------------------------------------------------------------------

def _render_preview_feed():
    """Preview a feed's data."""
    feed_id = st.session_state.fm_edit_id
    if not feed_id:
        st.session_state.fm_mode = "browse"
        st.rerun()
        return

    feed = get_feed(feed_id)
    if not feed:
        st.error(f"Feed not found: {feed_id}")
        return

    st.subheader(f"Preview: {feed['name']}")

    # Feed info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Provider", feed["provider"])
    with col2:
        st.metric("Series ID", feed["series_id"])
    with col3:
        st.metric("Frequency", feed.get("frequency", "—"))

    # Load data
    try:
        provider = get_provider(feed["provider"])
        kwargs = feed.get("kwargs", {})
        df = provider.fetch_series(feed["series_id"], **kwargs)

        if df.empty:
            st.warning("No data returned.")
            return

        # Summary
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Rows", f"{len(df):,}")
        with c2:
            st.metric("Columns", str(len(df.columns)))
        with c3:
            if hasattr(df.index, 'min'):
                st.metric("Date Range", f"{df.index.min().date()} — {df.index.max().date()}")

        # Chart
        from modules.visualization.charts import time_series_chart
        fig = time_series_chart(df, title=feed["name"])
        st.plotly_chart(fig, use_container_width=True, key=f"fm_preview_chart_{feed_id}")

        # Data table
        with st.expander("Raw Data (last 20 rows)"):
            st.dataframe(df.tail(20), use_container_width=True)

        # Mark as refreshed
        mark_refreshed(feed_id)

    except Exception as e:
        st.error(f"Error loading data: {e}")
