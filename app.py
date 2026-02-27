"""
Macro Dashboard — main Streamlit entry point.

Run with:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np

# ── Dashboard views ───────────────────────────────────────────────────────────
from views.reindustrialization import render as render_reindustrialization
from views.dynamic_dashboard import render as render_dynamic
from views.dashboard_builder import render as render_builder
from views.zillow_browser import render as render_zillow_browser

from modules.config.dashboard_config import list_dynamic_dashboards
from modules.config.chart_catalog import (
    list_catalogs,
    load_catalog,
    save_catalog,
    create_catalog,
    delete_catalog,
    get_item as catalog_get_item,
    upsert_item,
    delete_item as catalog_delete_item,
)

# ── Module imports ────────────────────────────────────────────────────────────
from modules.data_ingestion.fred_loader import (
    get_fred_client,
    search_fred,
    load_fred_series,
    get_series_info,
)
from modules.data_ingestion.file_loader import load_uploaded_file
from modules.data_ingestion.web_scraper import scrape_table, scrape_tables
from modules.data_ingestion.zillow_loader import load_zillow_csv, get_region_series
from modules.data_ingestion.bea_loader import (
    get_bea_key_status,
    list_bea_tables,
    fetch_bea_table,
    last_n_years,
    SUPPORTED_DATASETS,
    ANNUAL_ONLY_DATASETS,
)

from modules.data_processing.transforms import (
    year_over_year,
    month_over_month,
    merge_dataframes,
    summary_statistics,
    rolling_mean,
)
from modules.analysis.regression import (
    run_ols,
    format_ols_table,
    rolling_correlation,
    correlation_matrix,
)
from modules.visualization.charts import (
    time_series_chart,
    correlation_heatmap,
    scatter_chart,
    rolling_corr_chart,
    residual_plot,
    residual_histogram,
    apply_clip_arrows,
)

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Macro Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { min-width: 260px; max-width: 320px; }
    .metric-card {
        background: #f8f9fa;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 4px 0;
    }
    h1 { font-size: 1.8rem !important; }
    h2 { font-size: 1.3rem !important; border-bottom: 1px solid #e0e0e0; padding-bottom: 4px; }
    h3 { font-size: 1.1rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Navigation config ─────────────────────────────────────────────────────────

# Scan dashboards/ for dynamic configs on every rerun (builder writes → immediate refresh)
_dynamic_dashboards = list_dynamic_dashboards()
_dynamic_page_map = {cfg["title"]: cfg for cfg in _dynamic_dashboards}

_DASHBOARD_PAGES = ["US Reindustrialization"] + [cfg["title"] for cfg in _dynamic_dashboards]
_TOOL_PAGES = ["Data Sources", "Zillow Browser", "Chart Builder", "Chart Catalogs", "Dashboard Builder", "Regression & Analysis", "Data Table"]

if "page" not in st.session_state:
    st.session_state.page = "US Reindustrialization"

# ── Session state initialisation ──────────────────────────────────────────────

if "catalog" not in st.session_state:
    # catalog: dict[str, pd.DataFrame]  — name → DataFrame with DatetimeIndex
    st.session_state.catalog = {}

if "zillow_cache" not in st.session_state:
    # For Zillow data that needs region selection after loading
    st.session_state.zillow_cache = None

if "cb_recent_fred" not in st.session_state:
    st.session_state.cb_recent_fred = []   # list[{id, title}], max 10
if "cb_pending_dataset" not in st.session_state:
    st.session_state.cb_pending_dataset = None  # str | None

# Chart/Card catalog state
if "cb_item_id" not in st.session_state:
    st.session_state.cb_item_id = None
if "cb_item_type" not in st.session_state:
    st.session_state.cb_item_type = "Chart"
if "cb_catalog_id" not in st.session_state:
    st.session_state.cb_catalog_id = None
if "cb_edit_request" not in st.session_state:
    st.session_state.cb_edit_request = None

# Card-specific session state (new format: dataset/column based)
if "cb_card_dataset" not in st.session_state:
    st.session_state.cb_card_dataset = ""
if "cb_card_column" not in st.session_state:
    st.session_state.cb_card_column = ""
if "cb_card_fred_id" not in st.session_state:
    st.session_state.cb_card_fred_id = ""
if "cb_card_title" not in st.session_state:
    st.session_state.cb_card_title = ""
if "cb_card_value_format" not in st.session_state:
    st.session_state.cb_card_value_format = ",.2f"
if "cb_card_value_suffix" not in st.session_state:
    st.session_state.cb_card_value_suffix = ""
if "cb_card_delta_type" not in st.session_state:
    st.session_state.cb_card_delta_type = "none"


# ── Helpers ───────────────────────────────────────────────────────────────────

def add_to_catalog(name: str, df: pd.DataFrame):
    """Add or overwrite a dataset in the session catalog."""
    if not isinstance(df.index, pd.DatetimeIndex):
        try:
            df.index = pd.to_datetime(df.index)
        except Exception:
            pass
    st.session_state.catalog[name] = df


def catalog_names() -> list[str]:
    return list(st.session_state.catalog.keys())


def get_numeric_columns(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include=[np.number]).columns.tolist()


def get_merged_df(selected_datasets: list[str]) -> pd.DataFrame:
    """Merge selected datasets from catalog into one DataFrame."""
    dfs = [st.session_state.catalog[n] for n in selected_datasets if n in st.session_state.catalog]
    if not dfs:
        return pd.DataFrame()
    return merge_dataframes(dfs, how="outer")


# ── Sidebar navigation ────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📈 Macro Dashboard")
    st.markdown("---")

    st.markdown(
        "<p style='color:#888;font-size:0.72rem;font-weight:700;"
        "letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px'>"
        "Dashboards</p>",
        unsafe_allow_html=True,
    )
    for _p in _DASHBOARD_PAGES:
        if st.button(
            _p,
            key=f"nav_{_p}",
            use_container_width=True,
            type="primary" if st.session_state.page == _p else "secondary",
        ):
            st.session_state.page = _p
            st.rerun()

    st.markdown(
        "<p style='color:#888;font-size:0.72rem;font-weight:700;"
        "letter-spacing:0.08em;text-transform:uppercase;margin:14px 0 6px'>"
        "Tools</p>",
        unsafe_allow_html=True,
    )
    for _p in _TOOL_PAGES:
        if st.button(
            _p,
            key=f"nav_{_p}",
            use_container_width=True,
            type="primary" if st.session_state.page == _p else "secondary",
        ):
            st.session_state.page = _p
            st.rerun()

    # Loaded Datasets — always visible
    st.markdown("---")
    st.markdown("**Loaded Datasets**")
    if st.session_state.catalog:
        for _ds_name, _ds_df in st.session_state.catalog.items():
            _dc1, _dc2 = st.columns([4, 1])
            with _dc1:
                st.caption(f"`{_ds_name}`  \n{len(_ds_df):,} rows · {len(_ds_df.columns)} col(s)")
            with _dc2:
                if st.button("→", key=f"sb_ds_{_ds_name}", help="Use in Chart Builder"):
                    st.session_state.cb_pending_dataset = _ds_name
                    st.session_state.page = "Chart Builder"
                    st.rerun()
        if st.button("Clear All Data", use_container_width=True):
            st.session_state.catalog = {}
            st.session_state.zillow_cache = None
            st.rerun()
    else:
        st.caption("No datasets loaded yet.")

    if st.session_state.get("cb_recent_fred"):
        st.markdown("**Recent FRED**")
        for _r in st.session_state.cb_recent_fred[:5]:
            st.caption(f"📈 `{_r['id']}`  {_r.get('title', '')[:25]}")

    st.markdown("---")
    st.caption("Built with Streamlit · Plotly · FRED API")

page = st.session_state.page


# =============================================================================
# PAGE: US REINDUSTRIALIZATION (dashboard)
# =============================================================================

if page == "US Reindustrialization":
    render_reindustrialization()

elif page in _dynamic_page_map:
    render_dynamic(_dynamic_page_map[page])


# =============================================================================
# PAGE: DASHBOARD BUILDER
# =============================================================================

elif page == "Dashboard Builder":
    render_builder()


# =============================================================================
# PAGE: DATA SOURCES
# =============================================================================

elif page == "Data Sources":
    st.title("Data Sources")
    st.markdown("Load data from FRED, BEA, file uploads, web scraping, or Zillow CSVs.")

    tab_fred, tab_bea, tab_file, tab_web, tab_zillow = st.tabs(
        ["🏦 FRED", "🏛️ BEA", "📁 File Upload", "🌐 Web Scraper", "🏠 Zillow"]
    )

    # ── FRED ─────────────────────────────────────────────────────────────────
    with tab_fred:
        st.subheader("FRED API")

        _, err = get_fred_client()
        if err:
            st.warning(
                f"**FRED API key not configured.**\n\n{err}\n\n"
                "Copy `.env.example` to `.env` and add your key."
            )

        col1, col2 = st.columns([3, 1])
        with col1:
            search_query = st.text_input(
                "Search FRED",
                placeholder="e.g. unemployment rate, CPI, GDP…",
                key="fred_search_query",
            )
        with col2:
            search_limit = st.number_input("Results", min_value=5, max_value=100, value=20, step=5)

        if st.button("Search", key="fred_search_btn", use_container_width=True):
            if not search_query:
                st.warning("Enter a search term.")
            else:
                with st.spinner("Searching FRED…"):
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
            st.markdown(f"**{len(results)} result(s)** — click a row to select it:")
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
                    f"**{_ds_row['id']}** — {_ds_row.get('title', '')}  \n"
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
                with st.spinner(f"Loading {series_id}…"):
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
                        st.success(f"Loaded **{name}** — {len(df):,} observations.")

                        # Show info
                        try:
                            info = get_series_info(series_id)
                            if info:
                                title = info.get("title", "")
                                units = info.get("units", "")
                                freq = info.get("frequency", "")
                                st.caption(f"{title} | {units} | {freq}")
                        except Exception:
                            pass

                        st.line_chart(df)
                    except Exception as e:
                        st.error(f"Failed to load series: {e}")

    # ── BEA ──────────────────────────────────────────────────────────────────
    with tab_bea:
        st.subheader("BEA (Bureau of Economic Analysis)")

        _bea_key, _bea_err = get_bea_key_status()
        if _bea_err:
            st.warning(
                f"**BEA API key not configured.**\n\n{_bea_err}\n\n"
                "Copy `.env.example` to `.env` and add your key."
            )

        # ── Dataset + Frequency ───────────────────────────────────────────
        _bea_ds_col, _bea_freq_col = st.columns([2, 1])
        with _bea_ds_col:
            _bea_dataset = st.selectbox(
                "Dataset",
                options=list(SUPPORTED_DATASETS.keys()),
                format_func=lambda k: f"{k} — {SUPPORTED_DATASETS[k]}",
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

        # ── Table browser ─────────────────────────────────────────────────
        @st.cache_data(ttl=86400, show_spinner=False)
        def _bea_get_tables(dataset: str) -> pd.DataFrame:
            return list_bea_tables(dataset)

        if _bea_key:
            try:
                with st.spinner("Loading table list…"):
                    _bea_tables_df = _bea_get_tables(_bea_dataset)
            except Exception as _e:
                st.error(f"Could not load table list: {_e}")
                _bea_tables_df = pd.DataFrame(columns=["TableName", "Description"])
        else:
            _bea_tables_df = pd.DataFrame(columns=["TableName", "Description"])

        _bea_filter = st.text_input(
            "Filter tables",
            placeholder="e.g. GDP, investment, price index…",
            key="bea_filter",
        )

        _bea_display = _bea_tables_df.copy()
        if _bea_filter.strip():
            _mask = _bea_display["Description"].str.contains(
                _bea_filter.strip(), case=False, na=False
            )
            _bea_display = _bea_display[_mask].reset_index(drop=True)

        st.markdown(f"**{len(_bea_display)} table(s)** — click a row to select it:")
        _bea_table_event = st.dataframe(
            _bea_display,
            use_container_width=True,
            height=220,
            selection_mode="single-row",
            on_select="rerun",
            key="bea_table_grid",
        )
        _bea_sel_rows = _bea_table_event.selection.rows

        # Auto-preview when a row is selected
        _bea_prev_sel = st.session_state.get("_bea_prev_table_sel", [])
        if _bea_sel_rows != _bea_prev_sel:
            st.session_state["_bea_prev_table_sel"] = _bea_sel_rows
            st.session_state.pop("bea_preview", None)  # clear stale preview

        _bea_selected_table = None
        if _bea_sel_rows and not _bea_display.empty:
            _bea_row = _bea_display.iloc[_bea_sel_rows[0]]
            _bea_selected_table = _bea_row["TableName"]
            st.info(f"**{_bea_selected_table}** — {_bea_row['Description']}")

        # ── Preview lines ─────────────────────────────────────────────────
        st.markdown("---")

        if _bea_selected_table:
            _bea_cached = st.session_state.get("bea_preview", {})
            _need_preview = (
                _bea_cached.get("table") != _bea_selected_table
                or _bea_cached.get("dataset") != _bea_dataset
                or _bea_cached.get("freq") != _bea_freq
            )

            if _need_preview and _bea_key:
                with st.spinner(f"Previewing {_bea_selected_table}…"):
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
                st.markdown(f"**{len(_all_lines)} line(s) available** — select which to load:")

                # Sample data preview
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
                    with st.spinner(f"Loading {_bea_selected_table} (all years)…"):
                        try:
                            _full_df = fetch_bea_table(
                                _bea_dataset, _bea_selected_table, _bea_freq, years="ALL"
                            )
                            _out_df = _full_df[
                                [c for c in _bea_sel_lines if c in _full_df.columns]
                            ]
                            add_to_catalog(_bea_name.strip(), _out_df)
                            st.success(
                                f"Loaded **{_bea_name.strip()}** — "
                                f"{len(_out_df):,} rows × {len(_out_df.columns)} series."
                            )
                            st.line_chart(_out_df)
                        except Exception as _e:
                            st.error(f"Load failed: {_e}")
        else:
            st.caption("Select a table above to preview its contents.")

    # ── File Upload ──────────────────────────────────────────────────────────
    with tab_file:
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
                with st.spinner("Parsing file…"):
                    try:
                        df, msg = load_uploaded_file(uploaded)
                        add_to_catalog(file_name, df)
                        st.success(f"Loaded **{file_name}** — {len(df):,} rows, {len(df.columns)} columns.")
                        st.caption(msg)
                        st.dataframe(df.head(10), use_container_width=True)
                    except Exception as e:
                        st.error(f"Failed to load file: {e}")

    # ── Web Scraper ──────────────────────────────────────────────────────────
    with tab_web:
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
                with st.spinner("Fetching page…"):
                    try:
                        # First pass: get table count
                        tables = scrape_tables(url)
                        st.info(f"Found {len(tables)} table(s) on the page.")

                        df, msg = scrape_table(url, table_index=int(table_idx))
                        add_to_catalog(scraper_name, df)
                        st.success(f"Loaded **{scraper_name}** — {len(df):,} rows.")
                        st.caption(msg)
                        st.dataframe(df.head(10), use_container_width=True)
                    except Exception as e:
                        st.error(f"Scraping failed: {e}")

    # ── Zillow ────────────────────────────────────────────────────────────────
    with tab_zillow:
        st.subheader("Zillow Data")
        st.caption(
            "Upload a Zillow public CSV export (ZHVI, ZORI, etc.). "
            "Download from [zillow.com/research/data](https://www.zillow.com/research/data/)."
        )

        zillow_file = st.file_uploader(
            "Upload Zillow CSV",
            type=["csv"],
            key="zillow_uploader",
        )

        value_col_name = st.text_input(
            "Value column label",
            value="value",
            key="zillow_value_col",
        )

        if st.button("Parse Zillow File", key="zillow_parse_btn", use_container_width=True):
            if not zillow_file:
                st.warning("Upload a Zillow CSV first.")
            else:
                with st.spinner("Parsing Zillow CSV…"):
                    try:
                        data = load_zillow_csv(zillow_file, value_col_name=value_col_name)
                        st.session_state.zillow_cache = data
                        st.success(
                            f"Parsed {len(data['wide']):,} regions × "
                            f"{len(data['date_columns'])} time periods."
                        )
                    except Exception as e:
                        st.error(f"Failed to parse: {e}")

        if st.session_state.zillow_cache:
            data = st.session_state.zillow_cache
            regions = data["regions"]

            selected_regions = st.multiselect(
                "Select regions to add to catalog",
                options=regions,
                default=regions[:3] if len(regions) >= 3 else regions,
                key="zillow_regions",
            )

            zillow_prefix = st.text_input(
                "Name prefix for catalog entries",
                value="Zillow",
                key="zillow_prefix",
            )

            if st.button("Add to Catalog", key="zillow_add_btn", use_container_width=True):
                if not selected_regions:
                    st.warning("Select at least one region.")
                else:
                    added = []
                    for region in selected_regions:
                        series_df = get_region_series(data, region, value_col=value_col_name)
                        entry_name = f"{zillow_prefix} — {region}"
                        add_to_catalog(entry_name, series_df)
                        added.append(entry_name)
                    st.success(f"Added {len(added)} region(s) to catalog.")


# =============================================================================
# PAGE: ZILLOW BROWSER
# =============================================================================

elif page == "Zillow Browser":
    render_zillow_browser()


# =============================================================================
# PAGE: CHART BUILDER
# =============================================================================

elif page == "Chart Builder":
    st.title("Chart Builder")

    # ── Handle edit request from Chart Catalogs page ──────────────────────────
    _edit_req = st.session_state.cb_edit_request
    if _edit_req:
        st.session_state.cb_edit_request = None
        _er_item = catalog_get_item(_edit_req["catalog_id"], _edit_req["item_id"])
        if _er_item:
            _er_type = _er_item.get("type", "chart")
            st.session_state.cb_item_id = _er_item["id"]
            st.session_state.cb_catalog_id = _edit_req["catalog_id"]
            st.session_state.cb_item_type = "Chart" if _er_type == "chart" else "Card"
            if _er_type == "chart":
                st.session_state.cb_series = _er_item.get("series", [])
                st.session_state["cb_chart_title"] = _er_item.get("title", "")
                _ya = _er_item.get("y_axis") or {}
                _ya2 = _er_item.get("y_axis2") or {}
                st.session_state["cb_use_y_min"] = _ya.get("min") is not None
                st.session_state["cb_y_min"] = _ya.get("min") or 0.0
                st.session_state["cb_use_y_max"] = _ya.get("max") is not None
                st.session_state["cb_y_max"] = _ya.get("max") or 100.0
                st.session_state["cb_use_y_min2"] = _ya2.get("min") is not None
                st.session_state["cb_y_min2"] = _ya2.get("min") or 0.0
                st.session_state["cb_use_y_max2"] = _ya2.get("max") is not None
                st.session_state["cb_y_max2"] = _ya2.get("max") or 100.0
                st.session_state["cb_show_legend"] = _er_item.get("show_legend", True)
                st.session_state.cb_data = {}  # data will be reloaded from session catalog
            else:
                st.session_state.cb_card_dataset = _er_item.get("dataset_name", "")
                st.session_state.cb_card_column = _er_item.get("column", "")
                st.session_state.cb_card_fred_id = _er_item.get("fred_series_id", "")
                st.session_state.cb_card_title = _er_item.get("title", "")
                st.session_state.cb_card_value_format = _er_item.get("value_format", ",.2f")
                st.session_state.cb_card_value_suffix = _er_item.get("value_suffix", "")
                st.session_state.cb_card_delta_type = _er_item.get("delta_type", "none")

    # ── Load / New bar ────────────────────────────────────────────────────────
    _cb_catalogs = list_catalogs()
    _col_load, _col_status = st.columns([3, 2])
    with _col_load:
        if _cb_catalogs:
            _load_exp = st.expander("Load from catalog")
            with _load_exp:
                _lc_options = {c["title"]: c["id"] for c in _cb_catalogs}
                _lc_sel = st.selectbox(
                    "Catalog",
                    options=list(_lc_options.keys()),
                    key="cb_load_catalog_sel",
                )
                if _lc_sel:
                    _lc_id = _lc_options[_lc_sel]
                    _lc_cat = load_catalog(_lc_id)
                    _lc_items = _lc_cat.get("items", []) if _lc_cat else []
                    if _lc_items:
                        _li_options = {
                            f"{it.get('title', it['id'])} [{it.get('type','chart')}]": it["id"]
                            for it in _lc_items
                        }
                        _li_sel = st.selectbox(
                            "Item",
                            options=list(_li_options.keys()),
                            key="cb_load_item_sel",
                        )
                        if st.button("Load Item", key="cb_load_item_btn"):
                            _loaded = catalog_get_item(_lc_id, _li_options[_li_sel])
                            if _loaded:
                                st.session_state.cb_item_id = _loaded["id"]
                                st.session_state.cb_catalog_id = _lc_id
                                _ltype = _loaded.get("type", "chart")
                                st.session_state.cb_item_type = "Chart" if _ltype == "chart" else "Card"
                                if _ltype == "chart":
                                    st.session_state.cb_series = _loaded.get("series", [])
                                    st.session_state["cb_chart_title"] = _loaded.get("title", "")
                                    _ya = _loaded.get("y_axis") or {}
                                    _ya2 = _loaded.get("y_axis2") or {}
                                    st.session_state["cb_use_y_min"] = _ya.get("min") is not None
                                    st.session_state["cb_y_min"] = _ya.get("min") or 0.0
                                    st.session_state["cb_use_y_max"] = _ya.get("max") is not None
                                    st.session_state["cb_y_max"] = _ya.get("max") or 100.0
                                    st.session_state["cb_use_y_min2"] = _ya2.get("min") is not None
                                    st.session_state["cb_y_min2"] = _ya2.get("min") or 0.0
                                    st.session_state["cb_use_y_max2"] = _ya2.get("max") is not None
                                    st.session_state["cb_y_max2"] = _ya2.get("max") or 100.0
                                    st.session_state["cb_show_legend"] = _loaded.get("show_legend", True)
                                    # Repopulate cb_data for FRED series (best-effort)
                                    from modules.data_ingestion.fred_loader import load_fred_series as _lfs
                                    from modules.data_processing.transforms import year_over_year as _yoy_fn
                                    from modules.data_processing.transforms import month_over_month as _mom_fn
                                    from modules.data_processing.transforms import rolling_mean as _rm_fn
                                    _new_data = {}
                                    for _sd in _loaded.get("series", []):
                                        if _sd.get("source") == "fred" and _sd.get("series_id"):
                                            try:
                                                _df_tmp = _lfs(_sd["series_id"])
                                                _s_tmp = _df_tmp.iloc[:, 0]
                                                _tr = _sd.get("transform", "none")
                                                if _tr == "yoy":
                                                    _s_tmp = _yoy_fn(_s_tmp)
                                                elif _tr == "mom":
                                                    _s_tmp = _mom_fn(_s_tmp)
                                                elif _tr == "rolling":
                                                    _s_tmp = _rm_fn(_s_tmp, _sd.get("rolling_window", 12))
                                                _new_data[_sd["label"]] = _s_tmp
                                            except Exception:
                                                pass
                                    st.session_state.cb_data = _new_data
                                else:
                                    st.session_state.cb_card_dataset = _loaded.get("dataset_name", "")
                                    st.session_state.cb_card_column = _loaded.get("column", "")
                                    st.session_state.cb_card_fred_id = _loaded.get("fred_series_id", "")
                                    st.session_state.cb_card_title = _loaded.get("title", "")
                                    st.session_state.cb_card_value_format = _loaded.get("value_format", ",.2f")
                                    st.session_state.cb_card_value_suffix = _loaded.get("value_suffix", "")
                                    st.session_state.cb_card_delta_type = _loaded.get("delta_type", "none")
                                st.rerun()
                    else:
                        st.caption("Catalog is empty.")
        else:
            st.caption("No catalogs yet — save an item below to create one.")

    with _col_status:
        if st.session_state.cb_item_id:
            _status_label = st.session_state.get("cb_chart_title") or st.session_state.get("cb_card_title") or st.session_state.cb_item_id
            st.info(f"Editing: **{_status_label}**")
            if st.button("New (clear)", key="cb_new_btn"):
                st.session_state.cb_item_id = None
                st.session_state.cb_catalog_id = None
                st.session_state.cb_series = []
                st.session_state.cb_data = {}
                st.session_state.cb_card_dataset = ""
                st.session_state.cb_card_column = ""
                st.session_state.cb_card_fred_id = ""
                st.session_state.cb_card_title = ""
                st.session_state.cb_card_delta_type = "none"
                st.rerun()
        else:
            st.caption("Unsaved item")

    # ── Item type radio ───────────────────────────────────────────────────────
    st.session_state.cb_item_type = st.radio(
        "Item type",
        ["Chart", "Card"],
        index=0 if st.session_state.cb_item_type == "Chart" else 1,
        horizontal=True,
        key="cb_item_type_radio",
    )
    _cb_item_type = st.session_state.cb_item_type

    st.markdown("---")

    # ─────────────────────────────────────────────────────────────────────────
    # CHART BUILDER
    # ─────────────────────────────────────────────────────────────────────────
    if _cb_item_type == "Chart":
        chart_type = st.selectbox(
            "Chart type",
            ["Time Series", "Correlation Heatmap", "Scatter Plot"],
            key="chart_type",
        )

        st.markdown("---")

    # ── Time Series ──────────────────────────────────────────────────────────
    if _cb_item_type == "Chart" and chart_type == "Time Series":
        st.subheader("Time Series")

        # Session state initialisation
        if "cb_series" not in st.session_state:
            st.session_state.cb_series = []
        if "cb_data" not in st.session_state:
            st.session_state.cb_data = {}
        if "cb_fred_results" not in st.session_state:
            st.session_state.cb_fred_results = None

        cb_series = st.session_state.cb_series
        cb_data = st.session_state.cb_data

        # Pre-select catalog dataset when navigating from sidebar
        if st.session_state.cb_pending_dataset:
            st.session_state["cb_source"] = "From catalog"
            st.session_state["cb_cat_dataset"] = st.session_state.cb_pending_dataset
            st.session_state.cb_pending_dataset = None

        @st.cache_data(ttl=1800, show_spinner=False)
        def _cb_load_fred(series_id: str, transform: str, rolling_window: int) -> pd.Series:
            df_fred = load_fred_series(series_id)
            s = df_fred.iloc[:, 0]
            if transform == "yoy":
                s = year_over_year(s)
            elif transform == "mom":
                s = month_over_month(s)
            elif transform == "rolling":
                s = rolling_mean(s, rolling_window)
            return s

        # ── Current Series list ──────────────────────────────────────────────
        if cb_series:
            st.markdown("**Current Series**")
            for idx, _s in enumerate(list(cb_series)):
                src_info = f"{_s['source']}·{_s['chart_type']}·{_s.get('transform', 'none')}·ax{_s['axis']}"
                _ca, _cb, _cc, _cd = st.columns([5, 1, 1, 1])
                with _ca:
                    st.markdown(
                        f"`{_s['label']}` <small style='color:#888'>({src_info})</small>",
                        unsafe_allow_html=True,
                    )
                with _cb:
                    if st.button("↑", key=f"cb_up_{idx}", disabled=(idx == 0)):
                        cb_series[idx - 1], cb_series[idx] = cb_series[idx], cb_series[idx - 1]
                        st.rerun()
                with _cc:
                    if st.button("↓", key=f"cb_dn_{idx}", disabled=(idx == len(cb_series) - 1)):
                        cb_series[idx], cb_series[idx + 1] = cb_series[idx + 1], cb_series[idx]
                        st.rerun()
                with _cd:
                    if st.button("✕", key=f"cb_rm_{idx}"):
                        removed = cb_series.pop(idx)
                        cb_data.pop(removed["label"], None)
                        st.rerun()
        else:
            st.info("Add series below to begin")

        st.markdown("---")

        # ── Add Series / Add Computed Series tabs ────────────────────────────
        tab_add, tab_computed = st.tabs(["Add Series", "Add Computed Series"])

        with tab_add:
            # Series come from loaded datasets only (load data in Data Sources first)
            if not st.session_state.catalog:
                st.info("No datasets loaded yet. Go to **Data Sources** to load data first.")
            else:
                cb_cat_dataset = st.selectbox("Dataset", options=catalog_names(), key="cb_cat_dataset")
                if cb_cat_dataset:
                    _cat_df = st.session_state.catalog[cb_cat_dataset]
                    _cat_numeric = get_numeric_columns(_cat_df)
                    if _cat_numeric:
                        _cc1, _cc2 = st.columns(2)
                        with _cc1:
                            cb_cat_col = st.selectbox("Column", options=_cat_numeric, key="cb_cat_col")
                        with _cc2:
                            cb_cat_label = st.text_input(
                                "Label", key="cb_cat_label", placeholder="Display name (optional)"
                            )

                        _ctr_col, _croll_col = st.columns([2, 1])
                        with _ctr_col:
                            cb_cat_transform = st.selectbox(
                                "Transform", ["none", "yoy", "mom", "rolling"], key="cb_cat_transform"
                            )
                        with _croll_col:
                            cb_cat_rolling = st.number_input(
                                "Window",
                                min_value=2,
                                max_value=120,
                                value=12,
                                key="cb_cat_rolling",
                                disabled=(cb_cat_transform != "rolling"),
                            )

                        _ctype_col, _caxis_col = st.columns(2)
                        with _ctype_col:
                            cb_cat_type = st.selectbox(
                                "Chart type", ["line", "bar", "area"], key="cb_cat_type"
                            )
                        with _caxis_col:
                            cb_cat_axis = st.selectbox("Axis", [1, 2], key="cb_cat_axis")

                        if st.button("+ Add to Chart", key="cb_cat_add", use_container_width=True):
                            _label = (cb_cat_label.strip() or cb_cat_col)
                            if _label in cb_data:
                                st.warning(f"A series named '{_label}' already exists.")
                            else:
                                _s = _cat_df[cb_cat_col].dropna()
                                if not isinstance(_s.index, pd.DatetimeIndex):
                                    try:
                                        _s.index = pd.to_datetime(_s.index)
                                    except Exception:
                                        pass
                                if cb_cat_transform == "yoy":
                                    _s = year_over_year(_s)
                                elif cb_cat_transform == "mom":
                                    _s = month_over_month(_s)
                                elif cb_cat_transform == "rolling":
                                    _s = rolling_mean(_s, int(cb_cat_rolling))
                                cb_data[_label] = _s
                                cb_series.append({
                                    "label": _label,
                                    "chart_type": cb_cat_type,
                                    "axis": cb_cat_axis,
                                    "source": "catalog",
                                    "series_id": None,
                                    "catalog_name": cb_cat_dataset,
                                    "col": cb_cat_col,
                                    "transform": cb_cat_transform,
                                    "rolling_window": int(cb_cat_rolling),
                                })
                                st.rerun()
                    else:
                        st.warning("No numeric columns in selected dataset.")

        with tab_computed:
            if len(cb_series) < 2:
                st.info("Add at least two series before creating a computed series.")
            else:
                _existing_labels = [_s["label"] for _s in cb_series]
                _comp_a_col, _comp_op_col, _comp_b_col = st.columns([2, 1, 2])
                with _comp_a_col:
                    comp_a = st.selectbox("Series A", options=_existing_labels, key="cb_comp_a")
                with _comp_op_col:
                    comp_op = st.selectbox(
                        "Op", ["A÷B", "A−B", "A+B", "A×B", "% diff"], key="cb_comp_op"
                    )
                with _comp_b_col:
                    comp_b = st.selectbox("Series B", options=_existing_labels, key="cb_comp_b")

                comp_label = st.text_input("Label", key="cb_comp_label", placeholder="e.g. INDPRO÷UNRATE")
                _comp_type_col, _comp_axis_col = st.columns(2)
                with _comp_type_col:
                    comp_type = st.selectbox("Chart type", ["line", "bar", "area"], key="cb_comp_type")
                with _comp_axis_col:
                    comp_axis = st.selectbox("Axis", [1, 2], key="cb_comp_axis")

                if st.button("+ Add Computed Series", key="cb_comp_add", use_container_width=True):
                    _label = comp_label.strip()
                    if not _label:
                        st.warning("Enter a label for the computed series.")
                    elif comp_a == comp_b:
                        st.warning("Series A and Series B must be different.")
                    elif _label in cb_data:
                        st.warning(f"A series named '{_label}' already exists.")
                    else:
                        _sa, _sb = cb_data[comp_a].align(cb_data[comp_b], join="inner")
                        _op_map = {
                            "A÷B": "div", "A−B": "sub", "A+B": "add",
                            "A×B": "mul", "% diff": "pct_diff",
                        }
                        _op = _op_map[comp_op]
                        if _op == "div":
                            _result = _sa / _sb
                        elif _op == "sub":
                            _result = _sa - _sb
                        elif _op == "add":
                            _result = _sa + _sb
                        elif _op == "mul":
                            _result = _sa * _sb
                        else:  # pct_diff
                            _result = (_sa - _sb) / _sb * 100
                        _result.name = _label
                        cb_data[_label] = _result
                        cb_series.append({
                            "label": _label,
                            "chart_type": comp_type,
                            "axis": comp_axis,
                            "source": "computed",
                            "series_id": None,
                            "catalog_name": None,
                            "col": None,
                            "transform": "none",
                            "rolling_window": 12,
                            "op": _op,
                            "series_a": comp_a,
                            "series_b": comp_b,
                        })
                        st.rerun()

        # ── Chart Settings ────────────────────────────────────────────────────
        _has_dual_axis = any(_s["axis"] == 2 for _s in cb_series)
        with st.expander("Chart Settings", expanded=False):
            chart_title = st.text_input("Title", value="Time Series", key="cb_chart_title")

            st.markdown("**Primary Y-axis**")
            _ymin_col, _ymax_col = st.columns(2)
            with _ymin_col:
                _use_y_min = st.checkbox("Set min", key="cb_use_y_min")
                y_min = st.number_input("Min", value=0.0, key="cb_y_min") if _use_y_min else None
            with _ymax_col:
                _use_y_max = st.checkbox("Set max", key="cb_use_y_max")
                y_max = st.number_input("Max", value=100.0, key="cb_y_max") if _use_y_max else None

            if _has_dual_axis:
                st.markdown("**Secondary Y-axis**")
                _y2min_col, _y2max_col = st.columns(2)
                with _y2min_col:
                    _use_y_min2 = st.checkbox("Set min", key="cb_use_y_min2")
                    y_min2 = st.number_input("Min", value=0.0, key="cb_y_min2") if _use_y_min2 else None
                with _y2max_col:
                    _use_y_max2 = st.checkbox("Set max", key="cb_use_y_max2")
                    y_max2 = st.number_input("Max", value=100.0, key="cb_y_max2") if _use_y_max2 else None
            else:
                y_min2 = y_max2 = None

            show_legend = st.checkbox("Show legend", value=True, key="cb_show_legend")

            if st.button("Clear All Series", key="cb_clear_all"):
                st.session_state.cb_series = []
                st.session_state.cb_data = {}
                st.rerun()

        # ── Chart render ──────────────────────────────────────────────────────
        if cb_series:
            _valid = [_s for _s in cb_series if _s["label"] in cb_data]
            if _valid:
                plot_df = pd.DataFrame({_s["label"]: cb_data[_s["label"]] for _s in _valid})
                _series_types = {_s["label"]: _s["chart_type"] for _s in _valid}
                dual_col = next((_s["label"] for _s in _valid if _s["axis"] == 2), None)
                fig = time_series_chart(
                    plot_df,
                    title=chart_title,
                    dual_axis_col=dual_col,
                    series_types=_series_types,
                    y_min=y_min,
                    y_max=y_max,
                    y_min2=y_min2,
                    y_max2=y_max2,
                    show_legend=show_legend,
                )
                if y_min is not None or y_max is not None:
                    apply_clip_arrows(fig, y_min, y_max)
                st.plotly_chart(fig, use_container_width=True)

        # ── Save bar (Chart) — always visible ─────────────────────────────────
        st.markdown("---")
        st.markdown("**Save to Catalog**")
        _sv_catalogs = list_catalogs()
        _sv_col1, _sv_col2 = st.columns([3, 2])
        with _sv_col1:
            _sv_cat_options = {c["title"]: c["id"] for c in _sv_catalogs}
            if _sv_cat_options:
                _sv_cat_sel = st.selectbox(
                    "Catalog",
                    options=list(_sv_cat_options.keys()),
                    key="cb_save_catalog_sel",
                )
                _sv_cat_id = _sv_cat_options.get(_sv_cat_sel, "")
            else:
                _sv_cat_id = ""
                st.caption("No catalogs yet — create one below.")
            with st.expander("Create new catalog"):
                _new_cat_title = st.text_input("New catalog name", key="cb_new_cat_title")
                _new_cat_desc = st.text_input("Description (optional)", key="cb_new_cat_desc")
                if st.button("Create Catalog", key="cb_create_cat_btn"):
                    if _new_cat_title.strip():
                        _created = create_catalog(_new_cat_title.strip(), _new_cat_desc.strip())
                        st.success(f"Created catalog: {_created['title']}")
                        st.rerun()
                    else:
                        st.warning("Enter a catalog name.")

        with _sv_col2:
            _sv_item_title = st.text_input(
                "Item title",
                value=st.session_state.get("cb_chart_title", ""),
                key="cb_save_item_title",
            )
            _sv_can_save = bool(_sv_cat_id and cb_series)
            if st.button(
                "Save to Catalog",
                key="cb_save_chart_btn",
                type="primary",
                disabled=not _sv_can_save,
                help="Add at least one series and select a catalog first" if not _sv_can_save else "",
            ):
                _item_dict = {
                    "type": "chart",
                    "title": _sv_item_title.strip() or st.session_state.get("cb_chart_title", "Untitled"),
                    "chart_subtype": "Time Series",
                    "y_axis": {
                        "min": y_min,
                        "max": y_max,
                    },
                    "y_axis2": {
                        "min": y_min2,
                        "max": y_max2,
                    },
                    "show_legend": st.session_state.get("cb_show_legend", True),
                    "series": list(cb_series),
                }
                if st.session_state.cb_item_id:
                    _item_dict["id"] = st.session_state.cb_item_id
                _saved_id = upsert_item(_sv_cat_id, _item_dict)
                st.session_state.cb_item_id = _saved_id
                st.session_state.cb_catalog_id = _sv_cat_id
                _cat_title = _sv_cat_sel if _sv_cat_options else _sv_cat_id
                st.toast(f"Saved to {_cat_title}")
                st.rerun()

    # ── Correlation Heatmap ──────────────────────────────────────────────────
    elif _cb_item_type == "Chart" and chart_type == "Correlation Heatmap":
        st.subheader("Correlation Heatmap")

        selected_datasets = st.multiselect(
            "Select datasets",
            options=catalog_names(),
            default=catalog_names()[:3],
            key="heat_datasets",
        )

        if not selected_datasets:
            st.info("Select at least two datasets.")
            st.stop()

        merged = get_merged_df(selected_datasets)
        numeric_cols = get_numeric_columns(merged)

        selected_cols = st.multiselect(
            "Series to include",
            options=numeric_cols,
            default=numeric_cols[:8],
            key="heat_cols",
        )

        corr_method = st.selectbox("Method", ["pearson", "spearman", "kendall"], key="heat_method")

        if selected_cols and len(selected_cols) >= 2:
            sub = merged[selected_cols].dropna()
            corr = sub.corr(method=corr_method)
            fig = correlation_heatmap(corr, title=f"{corr_method.title()} Correlation Matrix")
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("Show correlation table"):
                st.dataframe(corr.round(4), use_container_width=True)
        else:
            st.info("Select at least two series.")

    # ── Scatter Plot ─────────────────────────────────────────────────────────
    elif _cb_item_type == "Chart" and chart_type == "Scatter Plot":
        st.subheader("Scatter Plot")

        selected_datasets = st.multiselect(
            "Select datasets",
            options=catalog_names(),
            default=catalog_names()[:2],
            key="scatter_datasets",
        )

        if not selected_datasets:
            st.info("Select at least one dataset.")
            st.stop()

        merged = get_merged_df(selected_datasets)
        numeric_cols = get_numeric_columns(merged)

        if len(numeric_cols) < 2:
            st.warning("Need at least two numeric columns.")
            st.stop()

        col1, col2 = st.columns(2)
        with col1:
            x_col = st.selectbox("X-axis", options=numeric_cols, index=0, key="scatter_x")
        with col2:
            y_col = st.selectbox("Y-axis", options=numeric_cols, index=min(1, len(numeric_cols) - 1), key="scatter_y")

        col3, col4 = st.columns(2)
        with col3:
            add_trendline = st.checkbox("Add trendline", value=True, key="scatter_trend")
        with col4:
            color_by_date = st.checkbox("Colour by date", value=True, key="scatter_color")

        if x_col and y_col and x_col != y_col:
            fig = scatter_chart(
                merged[x_col],
                merged[y_col],
                add_trendline=add_trendline,
                color_by_date=color_by_date,
            )
            st.plotly_chart(fig, use_container_width=True)

            # Quick correlation readout
            combined = pd.concat([merged[x_col], merged[y_col]], axis=1).dropna()
            if len(combined) > 2:
                r = combined.iloc[:, 0].corr(combined.iloc[:, 1])
                st.metric("Pearson r", f"{r:.4f}")
        else:
            st.info("Select two different series.")

    # ─────────────────────────────────────────────────────────────────────────
    # CARD BUILDER
    # ─────────────────────────────────────────────────────────────────────────
    elif _cb_item_type == "Card":
        st.subheader("Card Builder")

        if not st.session_state.catalog:
            st.info("No datasets loaded yet. Go to **Data Sources** to load data first.")
        else:
            # ── Data source ───────────────────────────────────────────────────
            _cd_col1, _cd_col2 = st.columns(2)
            with _cd_col1:
                # Determine initial dataset index (for when loading from catalog)
                _card_ds_options = catalog_names()
                _card_ds_init = (
                    _card_ds_options.index(st.session_state.cb_card_dataset)
                    if st.session_state.cb_card_dataset in _card_ds_options
                    else 0
                )
                _card_dataset = st.selectbox(
                    "Dataset",
                    options=_card_ds_options,
                    index=_card_ds_init,
                    key="cb_card_dataset_sel",
                )
                st.session_state.cb_card_dataset = _card_dataset
            with _cd_col2:
                _card_df = st.session_state.catalog.get(_card_dataset, pd.DataFrame())
                _card_numeric = get_numeric_columns(_card_df)
                if _card_numeric:
                    _card_col_init = (
                        _card_numeric.index(st.session_state.cb_card_column)
                        if st.session_state.cb_card_column in _card_numeric
                        else 0
                    )
                    _card_column = st.selectbox(
                        "Column",
                        options=_card_numeric,
                        index=_card_col_init,
                        key="cb_card_column_sel",
                    )
                    st.session_state.cb_card_column = _card_column
                else:
                    st.warning("No numeric columns in this dataset.")
                    _card_column = ""

            # ── Card settings ─────────────────────────────────────────────────
            _cds_col1, _cds_col2, _cds_col3 = st.columns(3)
            with _cds_col1:
                _card_title = st.text_input(
                    "Card title",
                    value=st.session_state.cb_card_title or (_card_column if _card_column else ""),
                    placeholder="e.g. Unemployment Rate",
                    key="cb_card_title_input",
                )
                st.session_state.cb_card_title = _card_title
            with _cds_col2:
                _card_fmt = st.text_input(
                    "Value format",
                    value=st.session_state.cb_card_value_format,
                    placeholder=",.2f",
                    key="cb_card_fmt_input",
                    help="Python format spec, e.g. ',.2f', '.1f', ',.0f'",
                )
                st.session_state.cb_card_value_format = _card_fmt
            with _cds_col3:
                _card_sfx = st.text_input(
                    "Suffix",
                    value=st.session_state.cb_card_value_suffix,
                    placeholder="e.g. %  or  K",
                    key="cb_card_sfx_input",
                )
                st.session_state.cb_card_value_suffix = _card_sfx

            _delta_options = ["none", "period", "yoy"]
            _delta_labels = {"none": "No change", "period": "Prior period change", "yoy": "Year-over-year %"}
            _delta_init = (
                _delta_options.index(st.session_state.cb_card_delta_type)
                if st.session_state.cb_card_delta_type in _delta_options
                else 0
            )
            _card_delta = st.selectbox(
                "Show change",
                options=_delta_options,
                index=_delta_init,
                format_func=lambda x: _delta_labels[x],
                key="cb_card_delta_sel",
            )
            st.session_state.cb_card_delta_type = _card_delta

            # ── Live preview ──────────────────────────────────────────────────
            if _card_column:
                _prev_s = _card_df[_card_column].dropna()
                if not isinstance(_prev_s.index, pd.DatetimeIndex):
                    try:
                        _prev_s.index = pd.to_datetime(_prev_s.index)
                    except Exception:
                        pass
                if not _prev_s.empty:
                    st.markdown("---")
                    st.markdown("**Live Preview**")
                    _prev_val = _prev_s.iloc[-1]
                    _prev_delta_str = None
                    if _card_delta == "period" and len(_prev_s) >= 2:
                        _chg = _prev_s.iloc[-1] - _prev_s.iloc[-2]
                        _prev_delta_str = f"{_chg:+.4g} vs prior period"
                    elif _card_delta == "yoy" and len(_prev_s) >= 13:
                        try:
                            _yoy_val = (_prev_s.iloc[-1] / _prev_s.iloc[-13] - 1) * 100
                            _prev_delta_str = f"{_yoy_val:+.2f}% YoY"
                        except Exception:
                            pass
                    _fmt_spec = _card_fmt or ",.2f"
                    try:
                        _prev_val_str = f"{format(_prev_val, _fmt_spec)}{_card_sfx}"
                    except Exception:
                        _prev_val_str = f"{_prev_val}{_card_sfx}"
                    st.metric(_card_title or _card_column, _prev_val_str, _prev_delta_str)

            # ── Save bar (Card) ───────────────────────────────────────────────
            st.markdown("---")
            st.markdown("**Save to Catalog**")
            _sv_catalogs_c = list_catalogs()
            _svc_col1, _svc_col2 = st.columns([3, 2])
            with _svc_col1:
                _svc_options = {c["title"]: c["id"] for c in _sv_catalogs_c}
                if _svc_options:
                    _svc_sel = st.selectbox(
                        "Catalog",
                        options=list(_svc_options.keys()),
                        key="cb_save_catalog_card_sel",
                    )
                    _svc_id = _svc_options.get(_svc_sel, "")
                else:
                    _svc_id = ""
                    st.caption("No catalogs yet.")
                with st.expander("Create new catalog"):
                    _new_cat_title_c = st.text_input("New catalog name", key="cb_new_cat_title_c")
                    _new_cat_desc_c = st.text_input("Description (optional)", key="cb_new_cat_desc_c")
                    if st.button("Create Catalog", key="cb_create_cat_btn_c"):
                        if _new_cat_title_c.strip():
                            _created_c = create_catalog(_new_cat_title_c.strip(), _new_cat_desc_c.strip())
                            st.success(f"Created catalog: {_created_c['title']}")
                            st.rerun()
                        else:
                            st.warning("Enter a catalog name.")

            with _svc_col2:
                _svc_item_title = st.text_input(
                    "Item title",
                    value=_card_title or _card_column or "",
                    key="cb_save_card_item_title",
                )
                _svc_can_save = bool(_svc_id and _card_column)
                if st.button(
                    "Save to Catalog",
                    key="cb_save_card_btn",
                    type="primary",
                    disabled=not _svc_can_save,
                    help="Select a dataset column and catalog first" if not _svc_can_save else "",
                ):
                    _card_item = {
                        "type": "card",
                        "title": _svc_item_title.strip() or _card_title or _card_column,
                        "dataset_name": _card_dataset,
                        "column": _card_column,
                        "fred_series_id": st.session_state.cb_card_fred_id or "",
                        "value_format": _card_fmt or ",.2f",
                        "value_suffix": _card_sfx,
                        "delta_type": _card_delta,
                    }
                    if st.session_state.cb_item_id:
                        _card_item["id"] = st.session_state.cb_item_id
                    _saved_card_id = upsert_item(_svc_id, _card_item)
                    st.session_state.cb_item_id = _saved_card_id
                    st.session_state.cb_catalog_id = _svc_id
                    _cat_title_c = _svc_sel if _svc_options else _svc_id
                    st.toast(f"Saved to {_cat_title_c}")
                    st.rerun()


# =============================================================================
# PAGE: CHART CATALOGS
# =============================================================================

elif page == "Chart Catalogs":
    st.title("Chart Catalogs")
    st.markdown("Review and manage saved charts and cards.")

    _cc_catalogs = list_catalogs()

    if not _cc_catalogs:
        st.info("No catalogs yet. Build a chart or card in **Chart Builder** and save it to a catalog.")
    else:
        # Catalog selector
        _cc_cat_titles = [c["title"] for c in _cc_catalogs]
        _cc_cat_ids = {c["title"]: c["id"] for c in _cc_catalogs}

        _cc_selected_title = st.selectbox(
            "Catalog",
            options=_cc_cat_titles,
            key="cc_catalog_sel",
        )
        _cc_catalog_id = _cc_cat_ids[_cc_selected_title]
        _cc_cat_data = load_catalog(_cc_catalog_id)

        if _cc_cat_data:
            # Catalog header — inline title edit
            _cc_header_col, _cc_del_col = st.columns([5, 1])
            with _cc_header_col:
                _cc_new_title = st.text_input(
                    "Catalog title",
                    value=_cc_cat_data.get("title", ""),
                    key="cc_cat_title_input",
                    label_visibility="collapsed",
                )
            with _cc_del_col:
                if st.button("Delete Catalog", key="cc_del_cat_btn", type="secondary"):
                    delete_catalog(_cc_catalog_id)
                    st.toast(f"Deleted catalog: {_cc_selected_title}")
                    st.rerun()

            _cc_desc = st.text_input(
                "Description",
                value=_cc_cat_data.get("description", ""),
                key="cc_cat_desc_input",
                placeholder="Optional description",
                label_visibility="visible",
            )

            if st.button("Save catalog info", key="cc_save_cat_btn"):
                _cc_cat_data["title"] = _cc_new_title.strip() or _cc_cat_data["title"]
                _cc_cat_data["description"] = _cc_desc.strip()
                save_catalog(_cc_cat_data)
                st.toast("Catalog updated.")
                st.rerun()

            st.markdown("---")

            _cc_items = _cc_cat_data.get("items", [])
            if not _cc_items:
                st.info("This catalog is empty.")
            else:
                st.markdown(f"**{len(_cc_items)} item(s)**")

                for _ci in _cc_items:
                    _ci_type = _ci.get("type", "chart")
                    _ci_icon = "📊" if _ci_type == "chart" else "🔢"
                    _ci_title = _ci.get("title", _ci["id"])

                    with st.expander(f"{_ci_icon} {_ci_title}  `[{_ci_type}]`", expanded=False):
                        _cc_i_col1, _cc_i_col2 = st.columns([4, 1])
                        with _cc_i_col1:
                            _cc_new_item_title = st.text_input(
                                "Title",
                                value=_ci_title,
                                key=f"cc_item_title_{_ci['id']}",
                            )
                            if _ci_type == "chart":
                                _ci_series = _ci.get("series", [])
                                if _ci_series:
                                    st.caption(
                                        "Series: " + ", ".join(
                                            f"`{s['label']}`" for s in _ci_series
                                        )
                                    )
                            elif _ci_type == "card":
                                _ci_ds = _ci.get("dataset_name", "")
                                _ci_col = _ci.get("column", "")
                                _ci_delta = _ci.get("delta_type", "none")
                                st.caption(
                                    f"Dataset: `{_ci_ds}`  ·  Column: `{_ci_col}`  ·  Delta: {_ci_delta}"
                                )
                            _ci_updated = _ci.get("updated_at", "")
                            if _ci_updated:
                                st.caption(f"Updated: {_ci_updated[:19]}")

                        with _cc_i_col2:
                            if st.button("Edit in Builder", key=f"cc_edit_{_ci['id']}"):
                                st.session_state.cb_edit_request = {
                                    "catalog_id": _cc_catalog_id,
                                    "item_id": _ci["id"],
                                }
                                st.session_state.page = "Chart Builder"
                                st.rerun()
                            if st.button("Delete", key=f"cc_del_{_ci['id']}", type="secondary"):
                                catalog_delete_item(_cc_catalog_id, _ci["id"])
                                st.toast(f"Deleted: {_ci_title}")
                                st.rerun()

                        # Save title change
                        if _cc_new_item_title.strip() != _ci_title:
                            if st.button("Save title", key=f"cc_save_item_{_ci['id']}"):
                                _ci["title"] = _cc_new_item_title.strip()
                                upsert_item(_cc_catalog_id, _ci)
                                st.toast("Title updated.")
                                st.rerun()


# =============================================================================
# PAGE: REGRESSION & ANALYSIS
# =============================================================================

elif page == "Regression & Analysis":
    st.title("Regression & Analysis")

    if not st.session_state.catalog:
        st.info("No data loaded yet. Go to **Data Sources** to load some datasets.")
        st.stop()

    tab_ols, tab_rolcor, tab_transform, tab_stats = st.tabs(
        ["📐 OLS Regression", "📉 Rolling Correlation", "🔄 Transforms", "📊 Summary Stats"]
    )

    # ── OLS ──────────────────────────────────────────────────────────────────
    with tab_ols:
        st.subheader("OLS Regression")

        selected_datasets = st.multiselect(
            "Select datasets",
            options=catalog_names(),
            default=catalog_names()[:2],
            key="ols_datasets",
        )

        if not selected_datasets:
            st.info("Select at least one dataset.")
            st.stop()

        merged = get_merged_df(selected_datasets)
        numeric_cols = get_numeric_columns(merged)

        if len(numeric_cols) < 2:
            st.warning("Need at least two numeric columns for regression.")
            st.stop()

        col1, col2 = st.columns(2)
        with col1:
            dep_var = st.selectbox("Dependent variable (Y)", options=numeric_cols, key="ols_dep")
        with col2:
            indep_candidates = [c for c in numeric_cols if c != dep_var]
            indep_vars = st.multiselect(
                "Independent variable(s) (X)",
                options=indep_candidates,
                default=indep_candidates[:1],
                key="ols_indep",
            )

        add_const = st.checkbox("Add intercept (constant)", value=True, key="ols_const")

        if st.button("Run Regression", key="ols_run", use_container_width=True):
            if not indep_vars:
                st.warning("Select at least one independent variable.")
            else:
                with st.spinner("Running OLS…"):
                    try:
                        result = run_ols(merged, dep_var, indep_vars, add_constant=add_const)
                        st.session_state["ols_result"] = result
                        st.session_state["ols_merged"] = merged
                    except Exception as e:
                        st.error(f"Regression failed: {e}")

        if "ols_result" in st.session_state:
            result = st.session_state["ols_result"]

            # KPI row
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("R²", f"{result['rsquared']:.4f}")
            c2.metric("Adj. R²", f"{result['rsquared_adj']:.4f}")
            c3.metric("F-statistic", f"{result['fstatistic']:.4f}")
            c4.metric("Observations", f"{result['nobs']:,}")

            st.markdown("**Coefficient Table**")
            coef_table = format_ols_table(result)
            st.dataframe(
                coef_table.style.applymap(
                    lambda v: "color: green; font-weight: bold" if v is True else "",
                    subset=["significant"],
                ),
                use_container_width=True,
            )

            with st.expander("Full statsmodels summary"):
                st.markdown(result["summary_html"], unsafe_allow_html=True)

            # Residual plots
            st.markdown("**Residual Diagnostics**")
            rc1, rc2 = st.columns(2)
            with rc1:
                fig_resid = residual_plot(result["fitted"], result["residuals"])
                st.plotly_chart(fig_resid, use_container_width=True)
            with rc2:
                fig_hist = residual_histogram(result["residuals"])
                st.plotly_chart(fig_hist, use_container_width=True)

            # Fitted vs actual
            merged_plot = st.session_state["ols_merged"]
            actual_col = dep_var if "dep_var" not in st.session_state else dep_var
            actual = merged_plot[dep_var].dropna()
            fitted_series = result["fitted"].reindex(actual.index)

            plot_df = pd.DataFrame({
                f"{dep_var} (actual)": actual,
                f"{dep_var} (fitted)": fitted_series,
            })
            fig_fit = time_series_chart(plot_df, title="Actual vs Fitted")
            st.plotly_chart(fig_fit, use_container_width=True)

    # ── Rolling Correlation ──────────────────────────────────────────────────
    with tab_rolcor:
        st.subheader("Rolling Correlation")

        selected_datasets = st.multiselect(
            "Select datasets",
            options=catalog_names(),
            default=catalog_names()[:2],
            key="rc_datasets",
        )

        if not selected_datasets:
            st.info("Select at least one dataset.")
            st.stop()

        merged = get_merged_df(selected_datasets)
        numeric_cols = get_numeric_columns(merged)

        col1, col2, col3 = st.columns(3)
        with col1:
            s1_col = st.selectbox("Series A", numeric_cols, index=0, key="rc_s1")
        with col2:
            s2_col = st.selectbox("Series B", numeric_cols, index=min(1, len(numeric_cols) - 1), key="rc_s2")
        with col3:
            window = st.number_input("Window (periods)", min_value=3, max_value=500, value=36, key="rc_window")

        if st.button("Compute", key="rc_run", use_container_width=True):
            if s1_col == s2_col:
                st.warning("Select two different series.")
            else:
                try:
                    rc = rolling_correlation(merged[s1_col], merged[s2_col], window=int(window))
                    fig = rolling_corr_chart(rc)
                    st.plotly_chart(fig, use_container_width=True)

                    full_corr = merged[s1_col].corr(merged[s2_col])
                    st.metric("Full-period Pearson r", f"{full_corr:.4f}")
                except Exception as e:
                    st.error(f"Failed: {e}")

    # ── Transforms ───────────────────────────────────────────────────────────
    with tab_transform:
        st.subheader("Compute Transforms")
        st.caption("Compute YoY/MoM percent changes and add them to the catalog.")

        t_dataset = st.selectbox("Dataset", catalog_names(), key="tr_dataset")
        if t_dataset:
            df = st.session_state.catalog[t_dataset]
            numeric_cols = get_numeric_columns(df)

            t_cols = st.multiselect("Series", numeric_cols, default=numeric_cols[:3], key="tr_cols")

            tc1, tc2, tc3 = st.columns(3)
            with tc1:
                do_yoy = st.checkbox("Year-over-Year %", key="tr_yoy")
            with tc2:
                do_mom = st.checkbox("Month-over-Month %", key="tr_mom")
            with tc3:
                do_ma = st.checkbox("Rolling Mean", key="tr_ma")
                if do_ma:
                    tr_ma_window = st.number_input("Window", 2, 120, 12, key="tr_ma_win")

            new_name = st.text_input(
                "Save as (catalog name)",
                value=f"{t_dataset}_transformed",
                key="tr_new_name",
            )

            if st.button("Apply & Save", key="tr_apply", use_container_width=True):
                if not t_cols:
                    st.warning("Select at least one series.")
                else:
                    parts = []
                    for col in t_cols:
                        s = df[col].dropna()
                        if do_yoy:
                            parts.append(year_over_year(s))
                        if do_mom:
                            parts.append(month_over_month(s))
                        if do_ma:
                            parts.append(rolling_mean(s, int(tr_ma_window)))
                        if not (do_yoy or do_mom or do_ma):
                            parts.append(s)

                    new_df = pd.concat(parts, axis=1)
                    add_to_catalog(new_name, new_df)
                    st.success(f"Saved **{new_name}** to catalog ({len(new_df.columns)} series).")
                    st.dataframe(new_df.tail(8), use_container_width=True)

    # ── Summary Stats ─────────────────────────────────────────────────────────
    with tab_stats:
        st.subheader("Summary Statistics")

        stat_datasets = st.multiselect(
            "Select datasets",
            options=catalog_names(),
            default=catalog_names()[:2],
            key="stat_datasets",
        )

        if stat_datasets:
            merged = get_merged_df(stat_datasets)
            stats = summary_statistics(merged)
            if stats.empty:
                st.info("No numeric data found.")
            else:
                st.dataframe(stats, use_container_width=True)

                # Download
                csv = stats.to_csv()
                st.download_button(
                    "Download CSV",
                    data=csv,
                    file_name="summary_statistics.csv",
                    mime="text/csv",
                )
        else:
            st.info("Select at least one dataset.")


# =============================================================================
# PAGE: DATA TABLE
# =============================================================================

elif page == "Data Table":
    st.title("Data Table")

    if not st.session_state.catalog:
        st.info("No data loaded yet. Go to **Data Sources** to load some datasets.")
        st.stop()

    selected = st.selectbox("Dataset", catalog_names(), key="dt_selected")

    if selected:
        df = st.session_state.catalog[selected]

        # Header metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Rows", f"{len(df):,}")
        c2.metric("Columns", f"{len(df.columns)}")
        if isinstance(df.index, pd.DatetimeIndex) and len(df) > 0:
            c3.metric("Date Range", f"{df.index.min().date()} → {df.index.max().date()}")

        st.markdown("---")

        # Column filter
        all_cols = list(df.columns)
        show_cols = st.multiselect(
            "Show columns",
            options=all_cols,
            default=all_cols[:10] if len(all_cols) > 10 else all_cols,
            key="dt_cols",
        )

        if show_cols:
            view_df = df[show_cols]
        else:
            view_df = df

        # Date range filter
        if isinstance(df.index, pd.DatetimeIndex) and len(df) > 0:
            col_a, col_b = st.columns(2)
            with col_a:
                d_start = st.date_input(
                    "From",
                    value=df.index.min().date(),
                    key="dt_start",
                )
            with col_b:
                d_end = st.date_input(
                    "To",
                    value=df.index.max().date(),
                    key="dt_end",
                )
            view_df = view_df.loc[
                (view_df.index >= pd.Timestamp(d_start)) &
                (view_df.index <= pd.Timestamp(d_end))
            ]

        st.dataframe(view_df, use_container_width=True, height=500)

        # Remove from catalog
        col_dl, col_rm = st.columns([3, 1])
        with col_dl:
            csv = view_df.to_csv()
            st.download_button(
                "Download CSV",
                data=csv,
                file_name=f"{selected}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col_rm:
            if st.button("Remove from catalog", use_container_width=True, key="dt_remove"):
                del st.session_state.catalog[selected]
                st.rerun()
