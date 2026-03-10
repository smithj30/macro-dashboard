"""
Macro Dashboard — main Streamlit entry point.

Run with:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np

# ── Dashboard views ───────────────────────────────────────────────────────────
from views.dynamic_dashboard import render as render_dynamic
from views.dashboard_builder import render as render_builder
from views.feed_manager import render as render_feed_manager
from views.tag_manager import render_tag_manager
from views.data_explorer import render as render_data_explorer

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
from modules.config.feed_catalog import get_feed as get_feed_by_id
from components.feed_picker import feed_picker

# ── Module imports ────────────────────────────────────────────────────────────
from modules.data_ingestion.fred_loader import load_fred_series

from modules.data_processing.transforms import (
    year_over_year,
    month_over_month,
    year_over_year_diff,
    month_over_month_diff,
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
    apply_recession_shading,
)
from components.chart_renderer import apply_style

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
    .block-container { padding-top: 1rem !important; padding-bottom: 0.5rem !important; max-width: 100% !important; padding-left: 1.5rem !important; padding-right: 1.5rem !important; }
    .main .block-container { width: 100% !important; }
    .metric-card {
        background: #FAF9F9;
        border: 1px solid #E1DBD4;
        border-radius: 8px;
        padding: 10px 14px;
        margin: 3px 0;
    }
    h1 { font-size: 1.5rem !important; }
    h2 { font-size: 1.1rem !important; border-bottom: 1px solid #E1DBD4; padding-bottom: 4px; }
    h3 { font-size: 0.95rem !important; }
    p, li, label, .stMarkdown, .stCaption, [data-testid="stText"] {
        font-size: 0.9rem !important;
    }
    .stButton button {
        font-size: 0.82rem !important;
        padding: 0.3rem 0.8rem !important;
    }
    [data-testid="stMetricValue"] { font-size: 1.3rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.82rem !important; }
    [data-testid="stMetricDelta"] { font-size: 0.78rem !important; }
    /* Hide heading anchor link icons */
    h1 a, h2 a, h3 a, h4 a, h5 a, h6 a,
    [data-testid="stHeaderActionElements"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Navigation config ─────────────────────────────────────────────────────────

# Scan dashboards/ for dynamic configs on every rerun (builder writes → immediate refresh)
_dynamic_dashboards = list_dynamic_dashboards()
_dynamic_page_map = {cfg["title"]: cfg for cfg in _dynamic_dashboards}

_DASHBOARD_PAGES = [cfg["title"] for cfg in _dynamic_dashboards]
_TOOL_PAGES = ["Data Explorer", "Feed Manager", "Chart Builder", "Chart Catalogs", "Dashboard Builder", "Tag Manager", "Regression & Analysis", "Data Table"]

if "page" not in st.session_state:
    st.session_state.page = _DASHBOARD_PAGES[0] if _DASHBOARD_PAGES else _TOOL_PAGES[0]

# ── Session state initialisation ──────────────────────────────────────────────

if "catalog" not in st.session_state:
    # catalog: dict[str, pd.DataFrame]  — name → DataFrame with DatetimeIndex
    st.session_state.catalog = {}

if "zillow_cache" not in st.session_state:
    # For Zillow data that needs region selection after loading
    st.session_state.zillow_cache = None

if "cb_recent_fred" not in st.session_state:
    st.session_state.cb_recent_fred = []   # list[{id, title}], max 10

# Chart/Card catalog state
if "cb_item_id" not in st.session_state:
    st.session_state.cb_item_id = None
if "cb_item_type" not in st.session_state:
    st.session_state.cb_item_type = "Chart"
if "cb_catalog_id" not in st.session_state:
    st.session_state.cb_catalog_id = None
if "cb_edit_request" not in st.session_state:
    st.session_state.cb_edit_request = None
if "cb_editing_idx" not in st.session_state:
    st.session_state.cb_editing_idx = None

# Card-specific session state (feed-based)
if "cb_card_feed_id" not in st.session_state:
    st.session_state.cb_card_feed_id = None
if "cb_card_title" not in st.session_state:
    st.session_state.cb_card_title = ""
if "cb_card_value_format" not in st.session_state:
    st.session_state.cb_card_value_format = ",.2f"
if "cb_card_value_suffix" not in st.session_state:
    st.session_state.cb_card_value_suffix = ""
if "cb_card_delta_type" not in st.session_state:
    st.session_state.cb_card_delta_type = "none"

# Chart Catalogs — delete confirmation state
if "cc_pending_delete_catalog" not in st.session_state:
    st.session_state.cc_pending_delete_catalog = None  # catalog_id awaiting confirmation
if "cc_pending_delete_item" not in st.session_state:
    st.session_state.cc_pending_delete_item = None  # item_id awaiting confirmation


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


    if st.session_state.get("cb_recent_fred"):
        st.markdown("**Recent FRED**")
        for _r in st.session_state.cb_recent_fred[:5]:
            st.caption(f"📈 `{_r['id']}`  {_r.get('title', '')[:25]}")

    st.markdown("---")
    st.caption("Built with Streamlit · Plotly · FRED API")

page = st.session_state.page


# =============================================================================
# PAGE: DYNAMIC DASHBOARDS
# =============================================================================

if page in _dynamic_page_map:
    render_dynamic(_dynamic_page_map[page])


# =============================================================================
# PAGE: DASHBOARD BUILDER
# =============================================================================

elif page == "Dashboard Builder":
    render_builder()


# =============================================================================
# PAGE: DATA EXPLORER
# =============================================================================

elif page == "Data Explorer":
    render_data_explorer()




# =============================================================================
# PAGE: FEED MANAGER
# =============================================================================

elif page == "Feed Manager":
    render_feed_manager()

# =============================================================================
# PAGE: CHART BUILDER
# =============================================================================

elif page == "Chart Builder":
    st.title("Chart Builder")

    # ── Helper: reload data for all series source types ──────────────────────
    def _load_chart_series_data(series_list):
        """Re-fetch data for a list of chart series (catalog, fred, feed, computed)."""
        from modules.data_ingestion.fred_loader import load_fred_series as _ld_lfs
        from modules.data_processing.transforms import year_over_year as _ld_yoy
        from modules.data_processing.transforms import month_over_month as _ld_mom
        from modules.data_processing.transforms import year_over_year_diff as _ld_yoy_diff
        from modules.data_processing.transforms import month_over_month_diff as _ld_mom_diff
        from modules.data_processing.transforms import rolling_mean as _ld_rm
        from providers import get_provider as _ld_gp

        def _apply_transform(s, tr, rw=None):
            if rw:
                s = _ld_rm(s, rw)
            if tr == "yoy":
                return _ld_yoy(s)
            elif tr == "mom":
                return _ld_mom(s)
            elif tr == "yoy_diff":
                return _ld_yoy_diff(s)
            elif tr == "mom_diff":
                return _ld_mom_diff(s)
            return s

        result = {}
        for sd in series_list:
            tr = sd.get("transform", "none")
            label = sd.get("label", "")
            rw = sd.get("rolling_window") if sd.get("rolling_enabled") else None
            source = sd.get("source", "")
            try:
                if source == "fred" and sd.get("series_id"):
                    df = _ld_lfs(sd["series_id"])
                    s = df.iloc[:, 0]
                    result[label] = _apply_transform(s, tr, rw)

                elif source == "feed" and sd.get("feed_id"):
                    feed = get_feed_by_id(sd["feed_id"])
                    if feed:
                        prov = _ld_gp(feed["provider"])
                        fdf = prov.fetch_series(feed["series_id"], **feed.get("kwargs", {}))
                        if fdf is not None and not fdf.empty:
                            s = fdf.iloc[:, 0]
                            result[label] = _apply_transform(s, tr, rw)

                elif source == "catalog":
                    # "catalog" source = data originally loaded from FRED via Data Sources.
                    # col holds the FRED series ID; catalog_name is the session key.
                    col = sd.get("col")
                    cat_name = sd.get("catalog_name", "")
                    # Try session state catalog first
                    if cat_name and cat_name in st.session_state.get("catalog", {}):
                        cat_df = st.session_state.catalog[cat_name]
                        if col and col in cat_df.columns:
                            s = cat_df[col].dropna()
                        else:
                            s = cat_df.iloc[:, 0].dropna()
                        result[label] = _apply_transform(s, tr, rw)
                    elif col:
                        # Fall back: re-fetch from FRED using col as series ID
                        df = _ld_lfs(col)
                        s = df.iloc[:, 0]
                        result[label] = _apply_transform(s, tr, rw)

                elif source == "computed" and sd.get("op"):
                    sa_name = sd.get("series_a", "")
                    sb_name = sd.get("series_b", "")
                    # Look up operands from already-built result dict
                    if sa_name in result and sb_name in result:
                        sa, sb = result[sa_name].align(result[sb_name], join="inner")
                        _op = sd["op"]
                        if _op == "div":
                            s = sa / sb
                        elif _op == "sub":
                            s = sa - sb
                        elif _op == "add":
                            s = sa + sb
                        elif _op == "mul":
                            s = sa * sb
                        elif _op == "pct_diff":
                            s = (sa - sb) / sb * 100
                        else:
                            continue
                        result[label] = _apply_transform(s, tr, rw)

            except Exception:
                pass
        return result

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
                st.session_state.cb_data = _load_chart_series_data(_er_item.get("series", []))
            else:
                # Feed-first: use feed_id if present, else try to resolve from old format
                _er_feed_id = _er_item.get("feed_id")
                if not _er_feed_id:
                    _er_fred_id = _er_item.get("fred_series_id", "")
                    if _er_fred_id:
                        from modules.config.feed_catalog import find_feed as _er_find
                        _er_found = _er_find("fred", _er_fred_id)
                        if _er_found:
                            _er_feed_id = _er_found["id"]
                st.session_state.cb_card_feed_id = _er_feed_id
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
                                    st.session_state.cb_data = _load_chart_series_data(_loaded.get("series", []))
                                else:
                                    # Feed-first: use feed_id if present, else resolve
                                    _ld_feed_id = _loaded.get("feed_id")
                                    if not _ld_feed_id:
                                        _ld_fred_id = _loaded.get("fred_series_id", "")
                                        if _ld_fred_id:
                                            from modules.config.feed_catalog import find_feed as _ld_find
                                            _ld_found = _ld_find("fred", _ld_fred_id)
                                            if _ld_found:
                                                _ld_feed_id = _ld_found["id"]
                                    st.session_state.cb_card_feed_id = _ld_feed_id
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
                st.session_state.cb_card_feed_id = None
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

        _TRANSFORM_LABELS = {
            "none": "None", "yoy": "YoY %", "mom": "MoM %",
            "yoy_diff": "YoY #", "mom_diff": "MoM #",
        }


        @st.cache_data(ttl=1800, show_spinner=False)
        def _cb_load_fred(series_id: str, transform: str, rolling_window: int = 0) -> pd.Series:
            df_fred = load_fred_series(series_id)
            s = df_fred.iloc[:, 0]
            if rolling_window:
                s = rolling_mean(s, rolling_window)
            if transform == "yoy":
                s = year_over_year(s)
            elif transform == "mom":
                s = month_over_month(s)
            elif transform == "yoy_diff":
                s = year_over_year_diff(s)
            elif transform == "mom_diff":
                s = month_over_month_diff(s)
            return s

        # ── Current Series list ──────────────────────────────────────────────
        if cb_series:
            st.markdown("**Current Series**")
            for idx, _s in enumerate(list(cb_series)):
                _tr_label = _TRANSFORM_LABELS.get(_s.get('transform', 'none'), _s.get('transform', 'none'))
                _rolling_label = f"R{_s.get('rolling_window', '')}" if _s.get('rolling_enabled') else ""
                src_info = f"{_s['source']}·{_s['chart_type']}·{_rolling_label + '→' if _rolling_label else ''}{_tr_label}·ax{_s['axis']}"
                _ca, _cb, _cc, _cd, _ce = st.columns([4, 1, 1, 1, 1])
                with _ca:
                    st.markdown(
                        f"`{_s['label']}` <small style='color:#888'>({src_info})</small>",
                        unsafe_allow_html=True,
                    )
                with _cb:
                    if st.button("Edit", key=f"cb_edit_{idx}"):
                        st.session_state.cb_editing_idx = idx
                        st.rerun()
                with _cc:
                    if st.button("↑", key=f"cb_up_{idx}", disabled=(idx == 0)):
                        cb_series[idx - 1], cb_series[idx] = cb_series[idx], cb_series[idx - 1]
                        st.rerun()
                with _cd:
                    if st.button("↓", key=f"cb_dn_{idx}", disabled=(idx == len(cb_series) - 1)):
                        cb_series[idx], cb_series[idx + 1] = cb_series[idx + 1], cb_series[idx]
                        st.rerun()
                with _ce:
                    if st.button("✕", key=f"cb_rm_{idx}"):
                        removed = cb_series.pop(idx)
                        cb_data.pop(removed["label"], None)
                        st.session_state.cb_editing_idx = None
                        st.rerun()

                # ── Inline edit form when this series is being edited ────
                if st.session_state.cb_editing_idx == idx:
                    with st.container():
                        st.markdown(f"**Editing: {_s['label']}**")
                        _ed_c1, _ed_c2 = st.columns(2)
                        with _ed_c1:
                            _ed_label = st.text_input("Label", value=_s["label"], key=f"cb_ed_label_{idx}")
                            _ed_chart_type = st.selectbox(
                                "Chart type",
                                ["line", "bar", "area"],
                                index=["line", "bar", "area"].index(_s.get("chart_type", "line")),
                                key=f"cb_ed_ctype_{idx}",
                            )
                        with _ed_c2:
                            _transform_opts = ["none", "yoy", "mom", "yoy_diff", "mom_diff"]
                            _cur_tr = _s.get("transform", "none")
                            # Migrate legacy "rolling" transform → rolling_enabled
                            if _cur_tr == "rolling":
                                _cur_tr = "none"
                            _ed_transform = st.selectbox(
                                "Transform",
                                _transform_opts,
                                index=_transform_opts.index(_cur_tr) if _cur_tr in _transform_opts else 0,
                                format_func=lambda x: _TRANSFORM_LABELS.get(x, x),
                                key=f"cb_ed_transform_{idx}",
                            )
                            _rc1, _rc2 = st.columns([1, 1])
                            with _rc1:
                                _ed_rolling_on = st.checkbox(
                                    "Rolling avg",
                                    value=_s.get("rolling_enabled", _s.get("transform") == "rolling"),
                                    key=f"cb_ed_rolling_on_{idx}",
                                )
                            with _rc2:
                                _ed_rolling = st.number_input(
                                    "Window",
                                    min_value=2, max_value=120,
                                    value=_s.get("rolling_window", 12),
                                    key=f"cb_ed_rolling_{idx}",
                                    disabled=(not _ed_rolling_on),
                                )
                        _ed_axis = st.selectbox(
                            "Axis", [1, 2],
                            index=[1, 2].index(_s.get("axis", 1)),
                            key=f"cb_ed_axis_{idx}",
                        )
                        _ed_apply, _ed_cancel = st.columns(2)
                        with _ed_apply:
                            if st.button("Apply", key=f"cb_ed_apply_{idx}", type="primary"):
                                old_label = cb_series[idx]["label"]
                                cb_series[idx]["label"] = _ed_label.strip() or old_label
                                cb_series[idx]["chart_type"] = _ed_chart_type
                                cb_series[idx]["transform"] = _ed_transform
                                cb_series[idx]["rolling_enabled"] = _ed_rolling_on
                                cb_series[idx]["rolling_window"] = int(_ed_rolling) if _ed_rolling_on else None
                                cb_series[idx]["axis"] = int(_ed_axis)
                                # Re-fetch data if transform or label changed
                                new_label = cb_series[idx]["label"]
                                if old_label != new_label:
                                    cb_data.pop(old_label, None)
                                new_data = _load_chart_series_data([cb_series[idx]])
                                if new_label in new_data:
                                    cb_data[new_label] = new_data[new_label]
                                # Auto-save to catalog when editing an existing item
                                if st.session_state.cb_item_id and st.session_state.cb_catalog_id:
                                    _as_ya = {
                                        "min": st.session_state.get("cb_y_min") if st.session_state.get("cb_use_y_min") else None,
                                        "max": st.session_state.get("cb_y_max") if st.session_state.get("cb_use_y_max") else None,
                                    }
                                    _as_ya2 = {
                                        "min": st.session_state.get("cb_y_min2") if st.session_state.get("cb_use_y_min2") else None,
                                        "max": st.session_state.get("cb_y_max2") if st.session_state.get("cb_use_y_max2") else None,
                                    }
                                    _autosave_item = {
                                        "type": "chart",
                                        "id": st.session_state.cb_item_id,
                                        "title": st.session_state.get("cb_chart_title", "Untitled"),
                                        "chart_subtype": "Time Series",
                                        "y_axis": _as_ya,
                                        "y_axis2": _as_ya2,
                                        "show_legend": st.session_state.get("cb_show_legend", True),
                                        "series": list(cb_series),
                                    }
                                    upsert_item(st.session_state.cb_catalog_id, _autosave_item)
                                st.session_state.cb_editing_idx = None
                                st.rerun()
                        with _ed_cancel:
                            if st.button("Cancel", key=f"cb_ed_cancel_{idx}"):
                                st.session_state.cb_editing_idx = None
                                st.rerun()
        else:
            st.info("Add series below to begin")

        st.markdown("---")

        # ── Add Series / Computed Series tabs ─────────────────────────────────
        tab_add, tab_computed = st.tabs(["Add Series", "Computed"])

        with tab_add:
            from providers import get_provider as _get_feed_prov
            from modules.config.feed_catalog import list_feeds as _list_feeds_cb
            _feed_list = _list_feeds_cb()
            if not _feed_list:
                st.info("No feeds registered yet. Add feeds in the **Feed Manager** first.")
            else:
                _fp_sel = feed_picker(
                    key="cb_feed_picker",
                    label="Select a feed",
                    allow_none=True,
                    help_text="Pick a data feed from the catalog (filter by tag)",
                )
                if _fp_sel:
                    _ff_col1, _ff_col2 = st.columns(2)
                    with _ff_col1:
                        cb_feed_label = st.text_input(
                            "Label",
                            key="cb_feed_label",
                            placeholder=f"e.g. {_fp_sel.get('name', '')}",
                        )
                    with _ff_col2:
                        cb_feed_transform = st.selectbox(
                            "Transform",
                            ["none", "yoy", "mom", "yoy_diff", "mom_diff"],
                            format_func=lambda x: _TRANSFORM_LABELS.get(x, x),
                            key="cb_feed_transform",
                        )
                    _ff_col3, _ff_col4, _ff_col5, _ff_col6 = st.columns([2, 1, 1, 1])
                    with _ff_col3:
                        cb_feed_type = st.selectbox(
                            "Chart type", ["line", "bar", "area"], key="cb_feed_chart_type"
                        )
                    with _ff_col4:
                        cb_feed_axis = st.selectbox("Axis", [1, 2], key="cb_feed_axis")
                    with _ff_col5:
                        cb_feed_rolling_on = st.checkbox("Rolling avg", key="cb_feed_rolling_on")
                    with _ff_col6:
                        cb_feed_rolling = st.number_input(
                            "Window",
                            min_value=2,
                            max_value=120,
                            value=12,
                            key="cb_feed_rolling",
                            disabled=(not cb_feed_rolling_on),
                        )

                    if st.button("+ Add Series", key="cb_feed_add", use_container_width=True):
                        _label = (cb_feed_label.strip() or _fp_sel.get("name", _fp_sel["series_id"]))
                        if _label in cb_data:
                            st.warning(f"A series named '{_label}' already exists.")
                        else:
                            try:
                                _f_prov = _get_feed_prov(_fp_sel["provider"])
                                _f_kwargs = _fp_sel.get("kwargs", {})
                                _f_df = _f_prov.fetch_series(_fp_sel["series_id"], **_f_kwargs)
                                if _f_df is not None and not _f_df.empty:
                                    _f_s = _f_df.iloc[:, 0].rename(_label)
                                    if cb_feed_rolling_on:
                                        _f_s = rolling_mean(_f_s, int(cb_feed_rolling))
                                    if cb_feed_transform == "yoy":
                                        _f_s = year_over_year(_f_s)
                                    elif cb_feed_transform == "mom":
                                        _f_s = month_over_month(_f_s)
                                    elif cb_feed_transform == "yoy_diff":
                                        _f_s = year_over_year_diff(_f_s)
                                    elif cb_feed_transform == "mom_diff":
                                        _f_s = month_over_month_diff(_f_s)
                                    cb_data[_label] = _f_s
                                    cb_series.append({
                                        "label": _label,
                                        "chart_type": cb_feed_type,
                                        "axis": cb_feed_axis,
                                        "source": "feed",
                                        "feed_id": _fp_sel["id"],
                                        "transform": cb_feed_transform,
                                        "rolling_enabled": cb_feed_rolling_on,
                                        "rolling_window": int(cb_feed_rolling) if cb_feed_rolling_on else None,
                                    })
                                    st.rerun()
                                else:
                                    st.warning(f"No data returned for feed '{_fp_sel.get('name', '')}'.")
                            except Exception as _fe:
                                st.error(f"Failed to load feed data: {_fe}")

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
                            "transform": "none",
                            "rolling_enabled": False,
                            "rolling_window": None,
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

            st.markdown("**Default date range**")
            _range_options = [("Show all", 0), ("1 year", 1), ("2 years", 2), ("3 years", 3), ("5 years", 5), ("10 years", 10), ("20 years", 20)]
            _range_labels = [r[0] for r in _range_options]
            _range_values = [r[1] for r in _range_options]
            _default_range_years = st.select_slider(
                "Default visible range",
                options=_range_values,
                value=0,
                format_func=lambda v: dict(_range_options).get(v, str(v)),
                key="cb_default_range",
                help="Set the default x-axis range shown when the chart loads. The range slider still allows panning.",
            )

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
                apply_style(fig)
                if y_min is not None or y_max is not None:
                    apply_clip_arrows(fig, y_min, y_max)
                # Apply default date range if set
                if _default_range_years and _default_range_years > 0:
                    from datetime import datetime, timedelta
                    _range_end = datetime.today()
                    _range_start = _range_end - timedelta(days=_default_range_years * 365)
                    fig.update_layout(xaxis=dict(range=[_range_start.strftime("%Y-%m-%d"), _range_end.strftime("%Y-%m-%d")]))
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
                    "default_range_years": _default_range_years if _default_range_years else None,
                    "series": list(cb_series),
                }
                if st.session_state.cb_item_id:
                    _item_dict["id"] = st.session_state.cb_item_id
                _saved_id = upsert_item(_sv_cat_id, _item_dict)
                _cat_title = _sv_cat_sel if _sv_cat_options else _sv_cat_id
                # Clear form for next chart
                st.session_state.cb_item_id = None
                st.session_state.cb_catalog_id = _sv_cat_id
                st.session_state.cb_series = []
                st.session_state.cb_data = {}
                st.session_state["cb_chart_title"] = ""
                st.toast(f"Saved to {_cat_title}")
                st.rerun()

            # Save As New (only when editing an existing item)
            if st.session_state.cb_item_id and _sv_can_save:
                if st.button(
                    "Save As New",
                    key="cb_saveas_chart_btn",
                    help="Save a copy without overwriting the original",
                ):
                    _item_dict_new = {
                        "type": "chart",
                        "title": _sv_item_title.strip() or st.session_state.get("cb_chart_title", "Untitled"),
                        "chart_subtype": "Time Series",
                        "y_axis": {"min": y_min, "max": y_max},
                        "y_axis2": {"min": y_min2, "max": y_max2},
                        "show_legend": st.session_state.get("cb_show_legend", True),
                        "default_range_years": _default_range_years if _default_range_years else None,
                        "series": list(cb_series),
                        # no "id" — forces upsert_item to create a new item
                    }
                    _saved_id = upsert_item(_sv_cat_id, _item_dict_new)
                    _cat_title = _sv_cat_sel if _sv_cat_options else _sv_cat_id
                    # Clear form for next chart
                    st.session_state.cb_item_id = None
                    st.session_state.cb_catalog_id = _sv_cat_id
                    st.session_state.cb_series = []
                    st.session_state.cb_data = {}
                    st.session_state["cb_chart_title"] = ""
                    st.toast(f"Saved as new to {_cat_title}")
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

        from providers import get_provider as _card_get_prov

        # ── Data source (feed picker) ────────────────────────────────────────
        _card_feed = feed_picker(
            key="cb_card_feed_picker",
            label="Select a feed for the card",
            allow_none=True,
            help_text="Pick a data feed from the catalog (filter by tag)",
            default_feed_id=st.session_state.cb_card_feed_id,
        )
        if _card_feed:
            st.session_state.cb_card_feed_id = _card_feed["id"]
        _card_feed_id = st.session_state.cb_card_feed_id

        # ── Card settings ─────────────────────────────────────────────────
        _card_feed_name = _card_feed.get("name", "") if _card_feed else ""
        _cds_col1, _cds_col2, _cds_col3 = st.columns(3)
        with _cds_col1:
            _card_title = st.text_input(
                "Card title",
                value=st.session_state.cb_card_title or _card_feed_name,
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
        _prev_s = None
        if _card_feed:
            try:
                _cprov = _card_get_prov(_card_feed["provider"])
                _cdf = _cprov.fetch_series(_card_feed["series_id"], **_card_feed.get("kwargs", {}))
                if _cdf is not None and not _cdf.empty:
                    _prev_s = _cdf.iloc[:, 0].dropna()
            except Exception:
                pass

        if _prev_s is not None and not _prev_s.empty:
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
            st.metric(_card_title or _card_feed_name or "Card", _prev_val_str, _prev_delta_str)

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
                value=_card_title or _card_feed_name or "",
                key="cb_save_card_item_title",
            )
            _svc_can_save = bool(_svc_id and _card_feed_id)
            if st.button(
                "Save to Catalog",
                key="cb_save_card_btn",
                type="primary",
                disabled=not _svc_can_save,
                help="Select a feed and catalog first" if not _svc_can_save else "",
            ):
                _card_item = {
                    "type": "card",
                    "title": _svc_item_title.strip() or _card_title or _card_feed_name,
                    "feed_id": _card_feed_id,
                    "value_format": _card_fmt or ",.2f",
                    "value_suffix": _card_sfx,
                    "delta_type": _card_delta,
                }
                if st.session_state.cb_item_id:
                    _card_item["id"] = st.session_state.cb_item_id
                _saved_card_id = upsert_item(_svc_id, _card_item)
                _cat_title_c = _svc_sel if _svc_options else _svc_id
                # Clear form for next card
                st.session_state.cb_item_id = None
                st.session_state.cb_catalog_id = _svc_id
                st.session_state.cb_card_feed_id = None
                st.session_state.cb_card_title = ""
                st.session_state.cb_card_value_format = ",.2f"
                st.session_state.cb_card_value_suffix = ""
                st.session_state.cb_card_delta_type = "none"
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
        # Catalog selector — remember selection across page visits
        _cc_cat_titles = [c["title"] for c in _cc_catalogs]
        _cc_cat_ids = {c["title"]: c["id"] for c in _cc_catalogs}

        # Restore previous selection if still valid
        _cc_default_idx = 0
        if "cc_last_catalog" in st.session_state:
            _cc_last = st.session_state.cc_last_catalog
            if _cc_last in _cc_cat_titles:
                _cc_default_idx = _cc_cat_titles.index(_cc_last)

        _cc_selected_title = st.selectbox(
            "Catalog",
            options=_cc_cat_titles,
            index=_cc_default_idx,
            key="cc_catalog_sel",
        )
        st.session_state.cc_last_catalog = _cc_selected_title
        _cc_catalog_id = _cc_cat_ids[_cc_selected_title]
        _cc_cat_data = load_catalog(_cc_catalog_id)

        if _cc_cat_data:
            # Catalog management in a compact row
            _cc_mgmt_col1, _cc_mgmt_col2 = st.columns([5, 1])
            with _cc_mgmt_col1:
                _cc_desc = _cc_cat_data.get("description", "")
                if _cc_desc:
                    st.caption(_cc_desc)
            with _cc_mgmt_col2:
                if st.session_state.cc_pending_delete_catalog == _cc_catalog_id:
                    _dcc1, _dcc2 = st.columns(2)
                    with _dcc1:
                        if st.button("Confirm Delete", key="cc_del_cat_confirm_btn", type="primary"):
                            delete_catalog(_cc_catalog_id)
                            st.session_state.cc_pending_delete_catalog = None
                            st.session_state.pop("cc_last_catalog", None)
                            st.toast(f"Deleted catalog: {_cc_selected_title}")
                            st.rerun()
                    with _dcc2:
                        if st.button("Cancel", key="cc_del_cat_cancel_btn"):
                            st.session_state.cc_pending_delete_catalog = None
                            st.rerun()
                else:
                    if st.button("Delete Catalog", key="cc_del_cat_btn", type="secondary"):
                        st.session_state.cc_pending_delete_catalog = _cc_catalog_id
                        st.rerun()

            # Edit catalog info in expander (less prominent)
            with st.expander("Edit catalog info"):
                _cc_new_title = st.text_input(
                    "Catalog title",
                    value=_cc_cat_data.get("title", ""),
                    key="cc_cat_title_input",
                )
                _cc_new_desc = st.text_input(
                    "Description",
                    value=_cc_cat_data.get("description", ""),
                    key="cc_cat_desc_input",
                    placeholder="Optional description",
                )
                if st.button("Save catalog info", key="cc_save_cat_btn"):
                    _cc_cat_data["title"] = _cc_new_title.strip() or _cc_cat_data["title"]
                    _cc_cat_data["description"] = _cc_new_desc.strip()
                    save_catalog(_cc_cat_data)
                    st.session_state.cc_last_catalog = _cc_cat_data["title"]
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

                    # Each item shown as a row with info + action buttons visible
                    _cc_i_col1, _cc_i_col2, _cc_i_col3 = st.columns([5, 1, 1])
                    with _cc_i_col1:
                        st.markdown(f"**{_ci_icon} {_ci_title}**  `{_ci_type}`")
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
                            st.caption(f"Dataset: `{_ci_ds}`  ·  Column: `{_ci_col}`")

                    with _cc_i_col2:
                        if st.button("Edit", key=f"cc_edit_{_ci['id']}", use_container_width=True):
                            st.session_state.cb_edit_request = {
                                "catalog_id": _cc_catalog_id,
                                "item_id": _ci["id"],
                            }
                            st.session_state.page = "Chart Builder"
                            st.rerun()

                    with _cc_i_col3:
                        if st.session_state.cc_pending_delete_item == _ci["id"]:
                            if st.button("Confirm", key=f"cc_del_confirm_{_ci['id']}", type="primary", use_container_width=True):
                                catalog_delete_item(_cc_catalog_id, _ci["id"])
                                st.session_state.cc_pending_delete_item = None
                                st.toast(f"Deleted: {_ci_title}")
                                st.rerun()
                            if st.button("Cancel", key=f"cc_del_cancel_{_ci['id']}", use_container_width=True):
                                st.session_state.cc_pending_delete_item = None
                                st.rerun()
                        else:
                            if st.button("Delete", key=f"cc_del_{_ci['id']}", type="secondary", use_container_width=True):
                                st.session_state.cc_pending_delete_item = _ci["id"]
                                st.rerun()

                    st.divider()


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


# =============================================================================
# PAGE: TAG MANAGER
# =============================================================================

elif page == "Tag Manager":
    render_tag_manager()
