"""
Data Explorer — browse, preview, save-as-feed, and create computed feeds.

Extracted from the former "Data Sources" page in app.py, with added:
- Shared preview section with date-range filtering
- Save as Feed form (persists to feed catalog)
- Computed Feed tab (create derived series from two feeds)
- Edit mode for computed feeds (navigated from Feed Manager)
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st

from modules.data_ingestion.fred_loader import (
    get_fred_client,
    search_fred,
    load_fred_series,
    get_series_info,
)
from modules.data_ingestion.file_loader import load_uploaded_file
from modules.data_ingestion.web_scraper import scrape_table, scrape_tables
from modules.data_ingestion.bea_loader import (
    get_bea_key_status,
    list_bea_tables,
    fetch_bea_table,
    last_n_years,
    SUPPORTED_DATASETS,
    ANNUAL_ONLY_DATASETS,
)
from views.zillow_browser import render as render_zillow_browser

from modules.config.feed_catalog import (
    create_feed,
    find_feed,
    get_feed,
    update_feed,
    list_feeds,
)
from modules.visualization.charts import time_series_chart
from components.chart_renderer import apply_style, apply_range_slider
from components.feed_picker import feed_picker
from providers.computed_provider import OPERATIONS, OP_LABELS


# ---------------------------------------------------------------------------
# Helpers (imported by app.py as well)
# ---------------------------------------------------------------------------

def add_to_catalog(name: str, df: pd.DataFrame):
    """Add or overwrite a dataset in the session catalog."""
    if not isinstance(df.index, pd.DatetimeIndex):
        try:
            df.index = pd.to_datetime(df.index)
        except Exception:
            pass
    st.session_state.catalog[name] = df


def catalog_names() -> list:
    return list(st.session_state.catalog.keys())


def get_numeric_columns(df: pd.DataFrame) -> list:
    return df.select_dtypes(include=[np.number]).columns.tolist()


# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

def _init_state():
    if "catalog" not in st.session_state:
        st.session_state.catalog = {}
    if "de_source_meta" not in st.session_state:
        st.session_state.de_source_meta = {}
    if "de_edit_computed_id" not in st.session_state:
        st.session_state.de_edit_computed_id = None


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def render():
    """Render the Data Explorer page."""
    _init_state()

    st.title("Data Explorer")
    st.markdown("Load data from FRED, BEA, file uploads, web scraping, Zillow, or create computed feeds.")

    # Determine if we need to auto-switch to Computed tab (edit mode)
    edit_id = st.session_state.get("de_edit_computed_id")

    tab_labels = [
        "FRED", "BEA", "File Upload",
        "Web Scraper", "Zillow", "Computed Feed",
    ]
    # Default to last tab if editing a computed feed
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        _render_fred_tab()
    with tabs[1]:
        _render_bea_tab()
    with tabs[2]:
        _render_file_tab()
    with tabs[3]:
        _render_web_tab()
    with tabs[4]:
        render_zillow_browser()
    with tabs[5]:
        _render_computed_tab()

    st.markdown("---")
    _render_preview_section()


# ---------------------------------------------------------------------------
# FRED tab
# ---------------------------------------------------------------------------

def _render_fred_tab():
    st.subheader("FRED API")

    _, err = get_fred_client()
    if err:
        st.warning(
            f"**FRED API key not configured.**\n\n{err}\n\n"
            "Copy `.env.example` to `.env` and add your key."
        )

    with st.form("fred_search_form"):
        col1, col2 = st.columns([3, 1])
        with col1:
            search_query = st.text_input(
                "Search FRED",
                placeholder="e.g. unemployment rate, CPI, GDP...",
                key="fred_search_query",
            )
        with col2:
            search_limit = st.number_input("Results", min_value=5, max_value=100, value=20, step=5)

        submitted = st.form_submit_button("Search", use_container_width=True)

    if submitted:
        if not search_query:
            st.warning("Enter a search term.")
        else:
            with st.spinner("Searching FRED..."):
                try:
                    results = search_fred(search_query, limit=search_limit)
                    if results.empty:
                        st.info("No results found.")
                    else:
                        st.session_state["fred_search_results"] = results
                        st.session_state["_ds_prev_fred_sel"] = []
                except Exception as e:
                    st.error(f"Search failed: {e}")

    if "fred_search_results" in st.session_state:
        results = st.session_state["fred_search_results"]
        st.markdown(f"**{len(results)} result(s)** -- click a row to select it:")
        _ds_event = st.dataframe(
            results, use_container_width=True, height=250,
            selection_mode="single-row", on_select="rerun",
            key="ds_fred_results_table",
        )
        _ds_sel = _ds_event.selection.rows
        _ds_prev = st.session_state.get("_ds_prev_fred_sel", [])
        if _ds_sel != _ds_prev:
            st.session_state["_ds_prev_fred_sel"] = _ds_sel
            if _ds_sel:
                _ds_row = results.iloc[_ds_sel[0]]
                st.session_state["fred_series_id"] = str(_ds_row["id"])
                if "title" in _ds_row:
                    st.session_state["fred_name"] = str(_ds_row["title"])[:80]

        if _ds_sel:
            _ds_row = results.iloc[_ds_sel[0]]
            st.info(
                f"**{_ds_row['id']}** -- {_ds_row.get('title', '')}  \n"
                "Series ID and name pre-filled below. Adjust dates if needed, then click **Load Series**."
            )

    st.markdown("---")
    st.markdown("**Load a Series by ID**")

    col_a, col_b, col_c = st.columns([2, 1, 1])
    with col_a:
        series_id = st.text_input(
            "Series ID",
            placeholder="e.g. UNRATE, CPIAUCSL, GDP",
            key="fred_series_id",
        ).strip().upper()
    with col_b:
        start_date = st.date_input("Start Date Override", value=None, key="fred_start")
    with col_c:
        end_date = st.date_input("End Date Override", value=None, key="fred_end")

    units_multiplier = st.number_input(
        "Units Multiplier (e.g. 0.001 to convert to thousands)",
        value=1.0,
        format="%g",
        key="fred_units_multiplier",
    )

    custom_name = st.text_input(
        "Dataset name (optional)",
        placeholder="Leave blank to use Series ID",
        key="fred_name",
    ).strip()

    if st.button("Load Series", key="fred_load_btn", use_container_width=True):
        if not series_id:
            st.warning("Enter a Series ID.")
        else:
            with st.spinner(f"Loading {series_id}..."):
                try:
                    df = load_fred_series(
                        series_id,
                        start_date=str(start_date) if start_date else None,
                        end_date=str(end_date) if end_date else None,
                    )
                    if units_multiplier != 1.0:
                        df = df * units_multiplier
                    name = custom_name or series_id
                    add_to_catalog(name, df)

                    # Capture source metadata for save-as-feed
                    meta = {"provider": "fred", "series_id": series_id, "dataset_name": name}
                    try:
                        info = get_series_info(series_id)
                        if info:
                            meta["frequency"] = info.get("frequency", "")
                            meta["units"] = info.get("units", "")
                            meta["title"] = info.get("title", "")
                    except Exception:
                        pass
                    st.session_state.de_source_meta = meta

                    st.success(f"Loaded **{name}** — select it in the Preview section below.")
                except Exception as e:
                    st.error(f"Failed to load series: {e}")


# ---------------------------------------------------------------------------
# BEA tab
# ---------------------------------------------------------------------------

def _render_bea_tab():
    st.subheader("BEA (Bureau of Economic Analysis)")

    _bea_key, _bea_err = get_bea_key_status()
    if _bea_err:
        st.warning(
            f"**BEA API key not configured.**\n\n{_bea_err}\n\n"
            "Copy `.env.example` to `.env` and add your key."
        )

    _bea_ds_col, _bea_freq_col = st.columns([2, 1])
    with _bea_ds_col:
        _bea_dataset = st.selectbox(
            "Dataset",
            options=list(SUPPORTED_DATASETS.keys()),
            format_func=lambda k: f"{k} -- {SUPPORTED_DATASETS[k]}",
            key="bea_dataset",
        )
    with _bea_freq_col:
        _bea_freq_opts = ["A"] if _bea_dataset in ANNUAL_ONLY_DATASETS else ["Q", "A"]
        _bea_freq = st.selectbox(
            "Frequency",
            options=_bea_freq_opts,
            format_func=lambda f: {"Q": "Quarterly", "A": "Annual"}[f],
            key="bea_freq",
        )

    @st.cache_data(ttl=86400, show_spinner=False)
    def _bea_get_tables(dataset: str) -> pd.DataFrame:
        return list_bea_tables(dataset)

    if _bea_key:
        try:
            with st.spinner("Loading table list..."):
                _bea_tables_df = _bea_get_tables(_bea_dataset)
        except Exception as _e:
            st.error(f"Could not load table list: {_e}")
            _bea_tables_df = pd.DataFrame(columns=["TableName", "Description"])
    else:
        _bea_tables_df = pd.DataFrame(columns=["TableName", "Description"])

    _bea_filter = st.text_input(
        "Filter tables",
        placeholder="e.g. GDP, investment, price index...",
        key="bea_filter",
    )

    _bea_display = _bea_tables_df.copy()
    if _bea_filter.strip():
        _mask = _bea_display["Description"].str.contains(
            _bea_filter.strip(), case=False, na=False
        )
        _bea_display = _bea_display[_mask].reset_index(drop=True)

    st.markdown(f"**{len(_bea_display)} table(s)** -- click a row to select it:")
    _bea_table_event = st.dataframe(
        _bea_display,
        use_container_width=True,
        height=220,
        selection_mode="single-row",
        on_select="rerun",
        key="bea_table_grid",
    )
    _bea_sel_rows = _bea_table_event.selection.rows

    _bea_prev_sel = st.session_state.get("_bea_prev_table_sel", [])
    if _bea_sel_rows != _bea_prev_sel:
        st.session_state["_bea_prev_table_sel"] = _bea_sel_rows
        st.session_state.pop("bea_preview", None)

    _bea_selected_table = None
    if _bea_sel_rows and not _bea_display.empty:
        _bea_row = _bea_display.iloc[_bea_sel_rows[0]]
        _bea_selected_table = _bea_row["TableName"]
        st.info(f"**{_bea_selected_table}** -- {_bea_row['Description']}")

    st.markdown("---")

    if _bea_selected_table:
        _bea_cached = st.session_state.get("bea_preview", {})
        _need_preview = (
            _bea_cached.get("table") != _bea_selected_table
            or _bea_cached.get("dataset") != _bea_dataset
            or _bea_cached.get("freq") != _bea_freq
        )

        if _need_preview and _bea_key:
            with st.spinner(f"Previewing {_bea_selected_table}..."):
                try:
                    _prev_df = fetch_bea_table(
                        _bea_dataset, _bea_selected_table, _bea_freq,
                        years=last_n_years(5),
                    )
                    st.session_state["bea_preview"] = {
                        "table": _bea_selected_table,
                        "dataset": _bea_dataset,
                        "freq": _bea_freq,
                        "columns": list(_prev_df.columns),
                        "sample": _prev_df.tail(4),
                    }
                except Exception as _e:
                    st.error(f"Preview failed: {_e}")

        _bea_preview = st.session_state.get("bea_preview", {})
        if _bea_preview.get("table") == _bea_selected_table:
            _all_lines = _bea_preview["columns"]
            st.markdown(f"**{len(_all_lines)} line(s) available** -- select which to load:")

            with st.expander("Sample data (last 4 periods)", expanded=False):
                st.dataframe(_bea_preview["sample"], use_container_width=True)

            _bea_sel_lines = st.multiselect(
                "Lines to load",
                options=_all_lines,
                default=_all_lines[:min(5, len(_all_lines))],
                key="bea_lines_sel",
            )

            _bea_name = st.text_input(
                "Dataset name",
                value=_bea_selected_table,
                key="bea_ds_name",
                placeholder="Name for the loaded dataset",
            )

            _bea_can_load = bool(_bea_sel_lines and _bea_name.strip())
            if st.button(
                "Load Selected Lines",
                key="bea_load_btn",
                type="primary",
                use_container_width=True,
                disabled=not _bea_can_load,
            ):
                with st.spinner(f"Loading {_bea_selected_table} (all years)..."):
                    try:
                        _full_df = fetch_bea_table(
                            _bea_dataset, _bea_selected_table, _bea_freq, years="ALL"
                        )
                        _out_df = _full_df[
                            [c for c in _bea_sel_lines if c in _full_df.columns]
                        ]
                        add_to_catalog(_bea_name.strip(), _out_df)

                        # Capture source metadata
                        freq_label = {"Q": "Quarterly", "A": "Annual"}.get(_bea_freq, _bea_freq)
                        st.session_state.de_source_meta = {
                            "provider": "bea",
                            "series_id": _bea_selected_table,
                            "dataset_name": _bea_name.strip(),
                            "frequency": freq_label,
                        }

                        st.success(
                            f"Loaded **{_bea_name.strip()}** -- "
                            f"{len(_out_df):,} rows x {len(_out_df.columns)} series."
                        )
                        st.line_chart(_out_df)
                    except Exception as _e:
                        st.error(f"Load failed: {_e}")
    else:
        st.caption("Select a table above to preview its contents.")


# ---------------------------------------------------------------------------
# File Upload tab
# ---------------------------------------------------------------------------

def _render_file_tab():
    st.subheader("CSV / Excel Upload")

    uploaded = st.file_uploader(
        "Upload a CSV or Excel file",
        type=["csv", "xlsx", "xls"],
        key="file_uploader",
    )

    if uploaded:
        col1, col2 = st.columns([3, 1])
        with col1:
            file_name = st.text_input(
                "Dataset name",
                value=uploaded.name.rsplit(".", 1)[0],
                key="file_name",
            )

        if st.button("Load File", key="file_load_btn", use_container_width=True):
            with st.spinner("Parsing file..."):
                try:
                    df, msg = load_uploaded_file(uploaded)
                    add_to_catalog(file_name, df)

                    st.session_state.de_source_meta = {
                        "provider": "file",
                        "series_id": uploaded.name,
                        "dataset_name": file_name,
                    }

                    st.success(f"Loaded **{file_name}** -- {len(df):,} rows, {len(df.columns)} columns.")
                    st.caption(msg)
                    st.dataframe(df.head(10), use_container_width=True)
                except Exception as e:
                    st.error(f"Failed to load file: {e}")


# ---------------------------------------------------------------------------
# Web Scraper tab
# ---------------------------------------------------------------------------

def _render_web_tab():
    st.subheader("Web Table Scraper")
    st.caption("Scrapes HTML `<table>` elements from a public URL.")

    url = st.text_input(
        "URL",
        placeholder="https://example.com/data-page",
        key="scraper_url",
    )

    col1, col2 = st.columns([1, 2])
    with col1:
        table_idx = st.number_input("Table index (0 = first)", min_value=0, value=0, key="scraper_idx")
    with col2:
        scraper_name = st.text_input(
            "Dataset name",
            value="scraped_table",
            key="scraper_name",
        )

    if st.button("Scrape", key="scraper_btn", use_container_width=True):
        if not url:
            st.warning("Enter a URL.")
        else:
            with st.spinner("Fetching page..."):
                try:
                    tables = scrape_tables(url)
                    st.info(f"Found {len(tables)} table(s) on the page.")

                    df, msg = scrape_table(url, table_index=int(table_idx))
                    add_to_catalog(scraper_name, df)
                    st.success(f"Loaded **{scraper_name}** -- {len(df):,} rows.")
                    st.caption(msg)
                    st.dataframe(df.head(10), use_container_width=True)
                except Exception as e:
                    st.error(f"Scraping failed: {e}")


# ---------------------------------------------------------------------------
# Computed Feed tab
# ---------------------------------------------------------------------------

def _render_computed_tab():
    st.subheader("Computed Feed")
    st.caption("Create a derived series from two existing feeds (e.g. Manufacturing Output / GDP).")

    edit_id = st.session_state.get("de_edit_computed_id")
    editing_feed = None
    if edit_id:
        editing_feed = get_feed(edit_id)
        if editing_feed:
            st.info(f"Editing computed feed: **{editing_feed['name']}**")

    # Operation choices
    op_keys = list(OPERATIONS.keys())
    op_display = [OP_LABELS[k] for k in op_keys]

    col_a, col_op, col_b = st.columns([2, 1, 2])
    with col_a:
        st.markdown("**Operand A**")
        feed_a = feed_picker(key="de_comp_feed_a", label="Feed A", allow_none=True)
    with col_op:
        # Pre-select operation if editing
        default_op_idx = 0
        if editing_feed:
            edit_op = editing_feed.get("params", {}).get("operation", "div")
            if edit_op in op_keys:
                default_op_idx = op_keys.index(edit_op)
        selected_op_label = st.selectbox(
            "Operation", op_display, index=default_op_idx, key="de_comp_op"
        )
        selected_op = op_keys[op_display.index(selected_op_label)]
    with col_b:
        st.markdown("**Operand B**")
        feed_b = feed_picker(key="de_comp_feed_b", label="Feed B", allow_none=True)

    if feed_a and feed_b:
        if st.button("Preview Computed Series", key="de_comp_preview_btn", use_container_width=True):
            with st.spinner("Computing..."):
                try:
                    from providers import get_provider
                    prov = get_provider("computed")
                    result_df = prov.fetch_series(
                        "computed",
                        operand_a=feed_a["id"],
                        operand_b=feed_b["id"],
                        operation=selected_op,
                    )
                    label = f"{feed_a['name']} {OP_LABELS[selected_op]} {feed_b['name']}"
                    add_to_catalog(label, result_df)
                    st.session_state.de_source_meta = {
                        "provider": "computed",
                        "series_id": "computed",
                        "dataset_name": label,
                        "operand_a": feed_a["id"],
                        "operand_b": feed_b["id"],
                        "operation": selected_op,
                    }
                    st.success(f"Computed **{label}** -- {len(result_df):,} observations.")
                    fig = time_series_chart(result_df, title=label)
                    fig = apply_style(fig)
                    st.plotly_chart(fig, use_container_width=True, key="de_comp_preview_chart")
                except Exception as e:
                    st.error(f"Computation failed: {e}")

        # Save / Update form
        st.markdown("---")
        default_name = ""
        if editing_feed:
            default_name = editing_feed["name"]
        elif feed_a and feed_b:
            sym = OP_LABELS[selected_op].split(" ")[1] if " " in OP_LABELS[selected_op] else selected_op
            default_name = f"{feed_a['name']} {sym} {feed_b['name']}"

        comp_name = st.text_input("Feed name", value=default_name, key="de_comp_name")
        comp_tags = st.text_input("Tags (comma-separated)", value="computed", key="de_comp_tags")

        if editing_feed:
            col_upd, col_cancel = st.columns(2)
            with col_upd:
                if st.button("Update Computed Feed", key="de_comp_update_btn", type="primary", use_container_width=True):
                    tags = [t.strip() for t in comp_tags.split(",") if t.strip()]
                    update_feed(editing_feed["id"], {
                        "name": comp_name.strip(),
                        "params": {
                            "operand_a": feed_a["id"],
                            "operand_b": feed_b["id"],
                            "operation": selected_op,
                        },
                        "tags": tags,
                    })
                    st.success(f"Updated computed feed: **{comp_name.strip()}**")
                    st.session_state.de_edit_computed_id = None
            with col_cancel:
                if st.button("Cancel Edit", key="de_comp_cancel_btn", use_container_width=True):
                    st.session_state.de_edit_computed_id = None
                    st.rerun()
        else:
            if st.button("Save Computed Feed", key="de_comp_save_btn", type="primary", use_container_width=True):
                if not comp_name.strip():
                    st.warning("Enter a name for the computed feed.")
                else:
                    tags = [t.strip() for t in comp_tags.split(",") if t.strip()]
                    new_feed = create_feed(
                        name=comp_name.strip(),
                        provider="computed",
                        series_id="computed",
                        tags=tags,
                        params={
                            "operand_a": feed_a["id"],
                            "operand_b": feed_b["id"],
                            "operation": selected_op,
                        },
                    )
                    st.success(f"Saved computed feed: **{comp_name.strip()}** (`{new_feed['id']}`)")
    else:
        st.caption("Select both Operand A and Operand B feeds to preview or save.")


# ---------------------------------------------------------------------------
# Shared Preview Section
# ---------------------------------------------------------------------------

def _render_preview_section():
    st.subheader("Preview")

    names = catalog_names()
    if not names:
        st.caption("Load a dataset above to preview it here.")
        return

    selected = st.selectbox("Dataset", names, key="de_preview_dataset")
    if not selected or selected not in st.session_state.catalog:
        return

    df = st.session_state.catalog[selected]

    # Date range filter
    if isinstance(df.index, pd.DatetimeIndex) and len(df) > 0:
        idx_min = df.index.min().date()
        idx_max = df.index.max().date()
        col_from, col_to = st.columns(2)
        with col_from:
            range_from = st.date_input("From", value=idx_min, min_value=idx_min, max_value=idx_max, key="de_prev_from")
        with col_to:
            range_to = st.date_input("To", value=idx_max, min_value=idx_min, max_value=idx_max, key="de_prev_to")
        mask = (df.index >= pd.Timestamp(range_from)) & (df.index <= pd.Timestamp(range_to))
        df_filtered = df.loc[mask]
    else:
        df_filtered = df

    # Column selector for multi-column datasets
    num_cols = get_numeric_columns(df_filtered)
    if len(num_cols) > 1:
        show_cols = st.multiselect(
            "Columns to show", num_cols, default=num_cols[:5], key="de_prev_cols"
        )
        if show_cols:
            df_filtered = df_filtered[show_cols]

    if df_filtered.empty:
        st.info("No data in the selected range.")
        return

    # Chart
    fig = time_series_chart(df_filtered, title=selected)
    fig = apply_style(fig)
    fig = apply_range_slider(fig, visible=True)
    st.plotly_chart(fig, use_container_width=True, key="de_preview_chart")

    # Save as Feed
    _render_save_as_feed(selected, df_filtered)


# ---------------------------------------------------------------------------
# Save as Feed
# ---------------------------------------------------------------------------

def _render_save_as_feed(dataset_name: str, df: pd.DataFrame):
    """Inline form to save the current preview dataset as a persistent feed."""
    st.markdown("---")
    st.subheader("Save as Feed")
    meta = st.session_state.get("de_source_meta", {})

    # Pre-fill from source metadata
    feed_name = st.text_input(
        "Feed name",
        value=meta.get("dataset_name", dataset_name),
        key="de_saf_name",
    )
    provider = st.text_input(
        "Provider",
        value=meta.get("provider", ""),
        key="de_saf_provider",
    )
    sid = st.text_input(
        "Series ID",
        value=meta.get("series_id", ""),
        key="de_saf_series_id",
    )

    col1, col2 = st.columns(2)
    with col1:
        frequency = st.text_input(
            "Frequency",
            value=meta.get("frequency", ""),
            key="de_saf_freq",
        )
    with col2:
        units = st.text_input(
            "Units",
            value=meta.get("units", ""),
            key="de_saf_units",
        )

    tags_str = st.text_input("Tags (comma-separated)", key="de_saf_tags")

    if st.button("Save as Feed", key="de_saf_save_btn", type="primary", use_container_width=True):
        if not feed_name.strip() or not provider.strip():
            st.warning("Feed name and provider are required.")
        else:
            # Duplicate check
            existing = find_feed(provider.strip(), sid.strip())
            if existing:
                st.warning(
                    f"A feed with provider=`{provider}` and series_id=`{sid}` "
                    f"already exists: **{existing['name']}** (`{existing['id']}`)"
                )
            else:
                tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                params = {"series_id": sid.strip()}
                # For computed feeds, pass through operation params
                if provider.strip() == "computed" and meta.get("operand_a"):
                    params = {
                        "operand_a": meta["operand_a"],
                        "operand_b": meta["operand_b"],
                        "operation": meta["operation"],
                    }
                new_feed = create_feed(
                    name=feed_name.strip(),
                    provider=provider.strip(),
                    series_id=sid.strip(),
                    frequency=frequency.strip(),
                    units=units.strip(),
                    tags=tags,
                    params=params,
                )
                st.success(f"Saved feed: **{feed_name.strip()}** (`{new_feed['id']}`)")
