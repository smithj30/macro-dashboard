"""
Chart Builder — extracted from app.py.

Provides:
    render_chart_builder()   — the Chart Builder tool page

Two modes:
    - Explorer (default): filterable list of all saved charts/cards
    - Edit: the chart/card builder form (create or edit)
"""

import streamlit as st
import pandas as pd
import numpy as np

from modules.config.chart_config import (
    list_items as list_chart_items,
    get_item as get_chart_item,
    upsert_item,
    delete_item as delete_chart_item,
)
from modules.config.dashboard_config import list_dynamic_dashboards, load_config as load_dashboard_config, save_config as save_dashboard_config
from components.feed_picker import feed_picker
from components.tag_picker import tag_picker, tag_display

from modules.data_ingestion.fred_loader import load_fred_series

from modules.data_processing.transforms import (
    year_over_year,
    month_over_month,
    year_over_year_diff,
    month_over_month_diff,
    rolling_mean,
)
from modules.visualization.charts import (
    time_series_chart,
    correlation_heatmap,
    scatter_chart,
    apply_clip_arrows,
)
from components.chart_renderer import apply_style, apply_annotations


# ── Helpers used by other pages (imported from app.py) ────────────────────────

def catalog_names() -> list[str]:
    return list(st.session_state.catalog.keys())


def get_numeric_columns(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include=[np.number]).columns.tolist()


def get_merged_df(selected_datasets: list[str]) -> pd.DataFrame:
    """Merge selected datasets from catalog into one DataFrame."""
    from modules.data_processing.transforms import merge_dataframes
    dfs = [st.session_state.catalog[n] for n in selected_datasets if n in st.session_state.catalog]
    if not dfs:
        return pd.DataFrame()
    return merge_dataframes(dfs, how="outer")


# ── Session state initialisation ─────────────────────────────────────────────

def _init_state():
    """Initialise all cb_* and cc_* session state variables."""
    if "cb_mode" not in st.session_state:
        st.session_state.cb_mode = "explore"   # explore | edit
    if "cb_edit_id" not in st.session_state:
        st.session_state.cb_edit_id = None      # item_id when editing existing

    if "cb_recent_fred" not in st.session_state:
        st.session_state.cb_recent_fred = []   # list[{id, title}], max 10

    # Chart/Card catalog state
    if "cb_item_id" not in st.session_state:
        st.session_state.cb_item_id = None
    if "cb_item_type" not in st.session_state:
        st.session_state.cb_item_type = "Chart"
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

    # Annotations state
    if "cb_annotations" not in st.session_state:
        st.session_state.cb_annotations = []

    # Chart Catalogs — delete confirmation state
    if "cc_pending_delete_item" not in st.session_state:
        st.session_state.cc_pending_delete_item = None  # item_id awaiting confirmation

    # Explorer multi-select state
    if "ce_selected_ids" not in st.session_state:
        st.session_state.ce_selected_ids = set()
    if "ce_bulk_action" not in st.session_state:
        st.session_state.ce_bulk_action = None  # None | "dashboard" | "add_to_dash" | "tag" | "delete"


# ── Helper: reload data for all series source types ──────────────────────────

def _load_chart_series_data(series_list):
    """Re-fetch data for a list of chart series (catalog, fred, feed, computed)."""
    from modules.data_ingestion.fred_loader import load_fred_series as _ld_lfs
    from modules.data_processing.transforms import year_over_year as _ld_yoy
    from modules.data_processing.transforms import month_over_month as _ld_mom
    from modules.data_processing.transforms import year_over_year_diff as _ld_yoy_diff
    from modules.data_processing.transforms import month_over_month_diff as _ld_mom_diff
    from modules.data_processing.transforms import rolling_mean as _ld_rm
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
                from services.data_resolver import resolve_feed_data as _ld_rfd
                fdf = _ld_rfd(sd["feed_id"])
                if not fdf.empty:
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


# =============================================================================
# Dashboard reference scanner
# =============================================================================

def _compute_dashboard_refs() -> dict[str, list[str]]:
    """Scan all dashboards and return {chart_id: [dashboard_title, ...]}."""
    refs: dict[str, list[str]] = {}
    for dash in list_dynamic_dashboards():
        dash_title = dash.get("title", dash.get("id", "Untitled"))
        for sec in dash.get("sections", []):
            # Direct chart_id on section
            cid = sec.get("chart_id")
            if cid:
                refs.setdefault(cid, []).append(dash_title)
            # card_row cards
            for card in sec.get("cards", []):
                cid = card.get("chart_id")
                if cid:
                    refs.setdefault(cid, []).append(dash_title)
    # Deduplicate per chart
    return {k: sorted(set(v)) for k, v in refs.items()}


# =============================================================================
# MODE 1: Chart Explorer
# =============================================================================

def _layout_for_count(n: int) -> str:
    """Return default dashboard layout based on number of charts."""
    if n <= 2:
        return "full"
    elif n <= 4:
        return "half"
    elif n <= 6:
        return "third"
    return "quarter"


def _clear_selection():
    """Clear all checkbox keys and the selected_ids set."""
    for key in list(st.session_state.keys()):
        if key.startswith("ce_chk_"):
            st.session_state[key] = False
    st.session_state.ce_selected_ids = set()


def _render_bulk_action_bar(selected_ids: set, all_items: list, dash_refs: dict):
    """Render the bulk action bar when charts are selected."""
    import uuid as _uuid

    sel_count = len(selected_ids)
    sel_items = [i for i in all_items if i["id"] in selected_ids]
    sel_names = [i.get("title", i["id"]) for i in sel_items]

    st.markdown(f"**{sel_count} chart(s) selected**")

    action_cols = st.columns([1, 1, 1, 1])
    with action_cols[0]:
        if st.button("Create Dashboard", key="ce_bulk_create_dash", use_container_width=True):
            st.session_state.ce_bulk_action = "dashboard"
            st.rerun()
    with action_cols[1]:
        if st.button("Add to Dashboard", key="ce_bulk_add_dash", use_container_width=True):
            st.session_state.ce_bulk_action = "add_to_dash"
            st.rerun()
    with action_cols[2]:
        if st.button("Bulk Tag", key="ce_bulk_tag_btn", use_container_width=True):
            st.session_state.ce_bulk_action = "tag"
            st.rerun()
    with action_cols[3]:
        if st.button("Bulk Delete", key="ce_bulk_delete_btn", use_container_width=True):
            st.session_state.ce_bulk_action = "delete"
            st.rerun()

    # ── Expanded action panels ────────────────────────────────────────────
    bulk_action = st.session_state.ce_bulk_action

    if bulk_action == "dashboard":
        # Create Dashboard from Selected
        st.session_state.builder_prefill_charts = list(selected_ids)
        _clear_selection()
        st.session_state.ce_bulk_action = None
        st.session_state.page = "Dashboard Builder"
        st.rerun()

    elif bulk_action == "add_to_dash":
        dashboards = list_dynamic_dashboards()
        if not dashboards:
            st.warning("No existing dashboards found. Use **Create Dashboard** instead.")
            if st.button("Cancel", key="ce_add_dash_cancel"):
                st.session_state.ce_bulk_action = None
                st.rerun()
        else:
            dash_options = {d.get("title", d["id"]): d["id"] for d in dashboards}
            _sel_dash = st.selectbox(
                "Select dashboard",
                options=list(dash_options.keys()),
                key="ce_add_dash_sel",
            )
            _add_col1, _add_col2 = st.columns(2)
            with _add_col1:
                if st.button("Add Charts", key="ce_add_dash_confirm", type="primary", use_container_width=True):
                    dash_id = dash_options[_sel_dash]
                    dash_cfg = load_dashboard_config(dash_id)
                    if dash_cfg:
                        layout = _layout_for_count(sel_count)
                        for cid in selected_ids:
                            item = get_chart_item(cid)
                            sec_type = "card_row" if item and item.get("type") == "card" else "chart"
                            if sec_type == "card_row":
                                dash_cfg.setdefault("sections", []).append({
                                    "id": f"sec_{_uuid.uuid4().hex[:8]}",
                                    "type": "card_row",
                                    "layout": "full",
                                    "cards": [{"chart_id": cid}],
                                })
                            else:
                                dash_cfg.setdefault("sections", []).append({
                                    "id": f"sec_{_uuid.uuid4().hex[:8]}",
                                    "type": "chart",
                                    "layout": layout,
                                    "chart_id": cid,
                                })
                        save_dashboard_config(dash_cfg)
                        st.session_state.ce_selected_ids = set()
                        st.session_state.ce_bulk_action = None
                        st.toast(f"Added {sel_count} chart(s) to {_sel_dash}")
                        st.rerun()
            with _add_col2:
                if st.button("Cancel", key="ce_add_dash_cancel2", use_container_width=True):
                    st.session_state.ce_bulk_action = None
                    st.rerun()

    elif bulk_action == "tag":
        _bulk_tags = tag_picker(
            label="Tags to add",
            key="ce_bulk_tag_picker",
            allow_create=False,
        )
        _tag_col1, _tag_col2 = st.columns(2)
        with _tag_col1:
            if st.button("Apply Tags", key="ce_bulk_tag_apply", type="primary", use_container_width=True):
                if _bulk_tags:
                    for item in sel_items:
                        existing_tags = set(item.get("tags", []))
                        merged = sorted(existing_tags | set(_bulk_tags))
                        upsert_item({"id": item["id"], "tags": merged})
                    _clear_selection()
                    st.session_state.ce_bulk_action = None
                    st.toast(f"Tagged {sel_count} chart(s)")
                    st.rerun()
                else:
                    st.warning("Select at least one tag to apply.")
        with _tag_col2:
            if st.button("Cancel", key="ce_bulk_tag_cancel", use_container_width=True):
                st.session_state.ce_bulk_action = None
                st.rerun()

    elif bulk_action == "delete":
        st.warning(f"Delete **{sel_count}** chart(s)?")
        for _sn in sel_names:
            _sid = sel_items[sel_names.index(_sn)]["id"]
            _srefs = dash_refs.get(_sid, [])
            if _srefs:
                st.markdown(f"- **{_sn}** — referenced by: {', '.join(_srefs)}")
            else:
                st.markdown(f"- {_sn}")
        _del_col1, _del_col2 = st.columns(2)
        with _del_col1:
            if st.button("Confirm Delete", key="ce_bulk_del_confirm", type="primary", use_container_width=True):
                for cid in selected_ids:
                    delete_chart_item(cid)
                st.session_state.ce_selected_ids = set()
                st.session_state.ce_bulk_action = None
                st.toast(f"Deleted {sel_count} chart(s)")
                st.rerun()
        with _del_col2:
            if st.button("Cancel", key="ce_bulk_del_cancel", use_container_width=True):
                st.session_state.ce_bulk_action = None
                st.rerun()

    st.markdown("---")


def _render_chart_explorer():
    """Filterable list of all saved charts/cards with dashboard refs."""
    st.title("Chart Builder")

    # ── Action bar ────────────────────────────────────────────────────────
    _ab_col1, _ab_col2 = st.columns([4, 1])
    with _ab_col2:
        if st.button("+ New Chart", key="ce_new_chart", type="primary", use_container_width=True):
            st.session_state.cb_mode = "edit"
            st.session_state.cb_edit_id = None
            st.session_state.cb_item_id = None
            st.session_state.cb_series = []
            st.session_state.cb_data = {}
            st.session_state.cb_card_feed_id = None
            st.session_state.cb_card_title = ""
            st.session_state.cb_card_delta_type = "none"
            st.rerun()

    # ── Load data ─────────────────────────────────────────────────────────
    all_items = list_chart_items()
    dash_refs = _compute_dashboard_refs()

    if not all_items:
        st.info("No saved charts or cards yet. Click **+ New Chart** to create one.")
        return

    # ── Sync selected_ids from checkbox widget keys ─────────────────────
    # When a bulk action is pending, skip re-syncing from checkboxes
    # (the action panel needs the stored selection to operate on).
    if not st.session_state.ce_bulk_action:
        _synced = set()
        for _item in all_items:
            _chk_key = f"ce_chk_{_item['id']}"
            if st.session_state.get(_chk_key, False):
                _synced.add(_item["id"])
        st.session_state.ce_selected_ids = _synced
    selected_ids = st.session_state.ce_selected_ids

    # ── Bulk action bar (when items selected) ─────────────────────────────
    if selected_ids or st.session_state.ce_bulk_action:
        _render_bulk_action_bar(selected_ids, all_items, dash_refs)

    # ── Filters ───────────────────────────────────────────────────────────
    _f_col1, _f_col2, _f_col3 = st.columns([3, 2, 1])
    with _f_col1:
        _search = st.text_input(
            "Search",
            key="ce_search",
            placeholder="Filter by title...",
            label_visibility="collapsed",
        )
    with _f_col2:
        # Collect all tags across items
        _all_tags = sorted({t for item in all_items for t in item.get("tags", [])})
        _tag_filter = st.multiselect("Tags", options=_all_tags, key="ce_tag_filter", label_visibility="collapsed", placeholder="Filter by tag...")
    with _f_col3:
        _type_filter = st.selectbox("Type", ["All", "Charts", "Cards"], key="ce_type_filter", label_visibility="collapsed")

    # Apply filters
    filtered = all_items
    if _search:
        _search_lower = _search.lower()
        filtered = [i for i in filtered if _search_lower in i.get("title", "").lower()]
    if _tag_filter:
        _tf_set = set(t.lower() for t in _tag_filter)
        filtered = [i for i in filtered if _tf_set & set(t.lower() for t in i.get("tags", []))]
    if _type_filter == "Charts":
        filtered = [i for i in filtered if i.get("type") == "chart"]
    elif _type_filter == "Cards":
        filtered = [i for i in filtered if i.get("type") == "card"]

    filtered_ids = {i["id"] for i in filtered}

    # ── Select All / Deselect All toggle ──────────────────────────────────
    _sel_col1, _sel_col2, _sel_col3 = st.columns([1, 1, 4])
    with _sel_col1:
        if st.button("Select All", key="ce_select_all", use_container_width=True):
            for _fid in filtered_ids:
                st.session_state[f"ce_chk_{_fid}"] = True
            st.session_state.ce_selected_ids = st.session_state.ce_selected_ids | filtered_ids
            st.rerun()
    with _sel_col2:
        if st.button("Deselect All", key="ce_deselect_all", use_container_width=True):
            for _fid in filtered_ids:
                st.session_state[f"ce_chk_{_fid}"] = False
            st.session_state.ce_selected_ids = st.session_state.ce_selected_ids - filtered_ids
            st.rerun()
    with _sel_col3:
        st.caption(f"{len(filtered)} of {len(all_items)} item(s)")

    # ── Item list ─────────────────────────────────────────────────────────
    for _ci in filtered:
        _ci_id = _ci["id"]
        _ci_type = _ci.get("type", "chart")
        _ci_icon = "📊" if _ci_type == "chart" else "🔢"
        _ci_title = _ci.get("title", _ci_id)
        _ci_tags = _ci.get("tags", [])
        _ci_refs = dash_refs.get(_ci_id, [])

        _row_chk, _row_col1, _row_col2, _row_col3 = st.columns([0.5, 4.5, 1, 1])

        with _row_chk:
            _is_checked = st.checkbox(
                "sel",
                value=(_ci_id in selected_ids),
                key=f"ce_chk_{_ci_id}",
                label_visibility="collapsed",
            )
            # Sync checkbox state with selected_ids (no rerun — synced live)
            if _is_checked:
                st.session_state.ce_selected_ids.add(_ci_id)
            else:
                st.session_state.ce_selected_ids.discard(_ci_id)

        with _row_col1:
            # Title + type badge
            st.markdown(f"**{_ci_icon} {_ci_title}**  `{_ci_type}`")
            # Tags as colored pills
            if _ci_tags:
                tag_display(_ci_tags, key_prefix=f"ce_td_{_ci_id}")
            # Dashboard refs or orphan badge
            if _ci_refs:
                _ref_str = ", ".join(_ci_refs)
                st.caption(f"Used in: {_ref_str}")
            else:
                st.markdown(
                    '<span style="background-color: #ff990022; color: #ff9900; '
                    'border: 1px solid #ff990044; padding: 2px 8px; border-radius: 12px; '
                    'font-size: 0.8em;">Orphan</span>',
                    unsafe_allow_html=True,
                )

        with _row_col2:
            if st.button("Edit", key=f"ce_edit_{_ci_id}", use_container_width=True):
                st.session_state.cb_mode = "edit"
                st.session_state.cb_edit_id = _ci_id
                st.session_state.cb_edit_request = {"item_id": _ci_id}
                st.rerun()

        with _row_col3:
            if st.session_state.cc_pending_delete_item == _ci_id:
                # Confirmation step
                if _ci_refs:
                    st.warning(f"Referenced by: {', '.join(_ci_refs)}")
                if st.button("Confirm", key=f"ce_del_confirm_{_ci_id}", type="primary", use_container_width=True):
                    delete_chart_item(_ci_id)
                    st.session_state.cc_pending_delete_item = None
                    st.toast(f"Deleted: {_ci_title}")
                    st.rerun()
                if st.button("Cancel", key=f"ce_del_cancel_{_ci_id}", use_container_width=True):
                    st.session_state.cc_pending_delete_item = None
                    st.rerun()
            else:
                if st.button("Delete", key=f"ce_del_{_ci_id}", type="secondary", use_container_width=True):
                    st.session_state.cc_pending_delete_item = _ci_id
                    if _ci_refs:
                        st.warning(f"This item is used in: {', '.join(_ci_refs)}")
                    st.rerun()

        st.divider()


# =============================================================================
# MODE 2: Chart Edit (the original builder)
# =============================================================================

def render_chart_builder():
    """Render the Chart Builder page — routes between Explorer and Edit modes."""
    _init_state()

    # Handle external edit requests (from Dashboard Builder, etc.)
    if st.session_state.cb_edit_request:
        st.session_state.cb_mode = "edit"

    if st.session_state.cb_mode == "explore":
        _render_chart_explorer()
        return

    # ── Edit mode ─────────────────────────────────────────────────────────
    _render_chart_edit()


def _render_chart_edit():
    """Render the chart/card edit form (Mode 2)."""
    st.title("Chart Builder")

    # ── Back to Explorer ──────────────────────────────────────────────────
    if st.button("← Back to Explorer", key="cb_back_to_explorer"):
        st.session_state.cb_mode = "explore"
        st.session_state.cb_edit_id = None
        st.rerun()

    # ── Handle edit request from Chart Catalogs page ──────────────────────
    _edit_req = st.session_state.cb_edit_request
    if _edit_req:
        st.session_state.cb_edit_request = None
        _er_item = get_chart_item(_edit_req["item_id"])
        if _er_item:
            _er_type = _er_item.get("type", "chart")
            st.session_state.cb_item_id = _er_item["id"]
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
                st.session_state.cb_annotations = list(_er_item.get("annotations", []))
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

    # ── Load / New bar ────────────────────────────────────────────────────
    _saved_items = list_chart_items()
    _col_load, _col_status = st.columns([3, 2])
    with _col_load:
        if _saved_items:
            _load_exp = st.expander("Load saved chart/card")
            with _load_exp:
                _li_options = {
                    f"{it.get('title', it['id'])} [{it.get('type','chart')}]": it["id"]
                    for it in _saved_items
                }
                _li_sel = st.selectbox(
                    "Item",
                    options=list(_li_options.keys()),
                    key="cb_load_item_sel",
                )
                if st.button("Load Item", key="cb_load_item_btn"):
                    _loaded = get_chart_item(_li_options[_li_sel])
                    if _loaded:
                        st.session_state.cb_item_id = _loaded["id"]
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
                            _ld_feed_id = _loaded.get("feed_id")
                            st.session_state.cb_card_feed_id = _ld_feed_id
                            st.session_state.cb_card_title = _loaded.get("title", "")
                            st.session_state.cb_card_value_format = _loaded.get("value_format", ",.2f")
                            st.session_state.cb_card_value_suffix = _loaded.get("value_suffix", "")
                            st.session_state.cb_card_delta_type = _loaded.get("delta_type", "none")
                        st.rerun()
        else:
            st.caption("No saved charts yet — save an item below.")

    with _col_status:
        if st.session_state.cb_item_id:
            _status_label = st.session_state.get("cb_chart_title") or st.session_state.get("cb_card_title") or st.session_state.cb_item_id
            st.info(f"Editing: **{_status_label}**")
            if st.button("New (clear)", key="cb_new_btn"):
                st.session_state.cb_item_id = None
                st.session_state.cb_series = []
                st.session_state.cb_data = {}
                st.session_state.cb_card_feed_id = None
                st.session_state.cb_card_title = ""
                st.session_state.cb_card_delta_type = "none"
                st.rerun()
        else:
            st.caption("Unsaved item")

    # ── Item type radio ───────────────────────────────────────────────────
    st.session_state.cb_item_type = st.radio(
        "Item type",
        ["Chart", "Card"],
        index=0 if st.session_state.cb_item_type == "Chart" else 1,
        horizontal=True,
        key="cb_item_type_radio",
    )
    _cb_item_type = st.session_state.cb_item_type

    st.markdown("---")

    # ─────────────────────────────────────────────────────────────────────
    # CHART BUILDER
    # ─────────────────────────────────────────────────────────────────────
    if _cb_item_type == "Chart":
        chart_type = st.selectbox(
            "Chart type",
            ["Time Series", "Correlation Heatmap", "Scatter Plot"],
            key="chart_type",
        )

        st.markdown("---")

    # ── Time Series ──────────────────────────────────────────────────────
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

        # ── Current Series list ──────────────────────────────────────────
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
                                if st.session_state.cb_item_id:
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
                                    upsert_item(_autosave_item)
                                st.session_state.cb_editing_idx = None
                                st.rerun()
                        with _ed_cancel:
                            if st.button("Cancel", key=f"cb_ed_cancel_{idx}"):
                                st.session_state.cb_editing_idx = None
                                st.rerun()
        else:
            st.info("Add series below to begin")

        st.markdown("---")

        # ── Add Series / Computed Series tabs ─────────────────────────────
        tab_add, tab_computed = st.tabs(["Add Series", "Computed"])

        with tab_add:
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
                                from services.data_resolver import resolve_feed_data as _cb_rfd
                                _f_df = _cb_rfd(_fp_sel)
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

        # ── Chart Settings ────────────────────────────────────────────────
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

        # ── Annotations ──────────────────────────────────────────────────
        cb_annotations = st.session_state.cb_annotations
        with st.expander(f"Annotations ({len(cb_annotations)})", expanded=False):
            _ann_type_opts = ["Point", "Horizontal Line", "Vertical Line", "Date Range"]
            _ann_type_map = {"Point": "point", "Horizontal Line": "hline", "Vertical Line": "vline", "Date Range": "range"}

            _ann_new_type = st.selectbox("Type", _ann_type_opts, key="cb_ann_new_type")

            if _ann_type_map[_ann_new_type] == "point":
                _ann_c1, _ann_c2 = st.columns(2)
                with _ann_c1:
                    _ann_date = st.date_input("Date", key="cb_ann_point_date")
                with _ann_c2:
                    _ann_text = st.text_input("Text", key="cb_ann_point_text")
                _ann_use_val = st.checkbox("Set value (y-position)", key="cb_ann_point_use_val")
                _ann_val = st.number_input("Value", value=0.0, key="cb_ann_point_val") if _ann_use_val else None
                if st.button("Add Point Annotation", key="cb_ann_add_point"):
                    st.session_state.cb_annotations.append({
                        "type": "point",
                        "date": str(_ann_date),
                        "text": _ann_text,
                        "value": _ann_val,
                        "label": _ann_text,
                        "style": {},
                    })
                    st.rerun()

            elif _ann_type_map[_ann_new_type] == "hline":
                _ann_c1, _ann_c2 = st.columns(2)
                with _ann_c1:
                    _ann_hval = st.number_input("Y value", value=0.0, key="cb_ann_hline_val")
                with _ann_c2:
                    _ann_haxis = st.selectbox("Axis", ["Left (y)", "Right (y2)"], key="cb_ann_hline_axis")
                _ann_hlabel = st.text_input("Label (optional)", key="cb_ann_hline_label")
                if st.button("Add Horizontal Line", key="cb_ann_add_hline"):
                    st.session_state.cb_annotations.append({
                        "type": "hline",
                        "value": _ann_hval,
                        "yref": "y2" if "y2" in _ann_haxis else "y",
                        "label": _ann_hlabel,
                        "style": {},
                    })
                    st.rerun()

            elif _ann_type_map[_ann_new_type] == "vline":
                _ann_vdate = st.date_input("Date", key="cb_ann_vline_date")
                _ann_vlabel = st.text_input("Label (optional)", key="cb_ann_vline_label")
                if st.button("Add Vertical Line", key="cb_ann_add_vline"):
                    st.session_state.cb_annotations.append({
                        "type": "vline",
                        "date": str(_ann_vdate),
                        "label": _ann_vlabel,
                        "style": {},
                    })
                    st.rerun()

            elif _ann_type_map[_ann_new_type] == "range":
                _ann_rc1, _ann_rc2 = st.columns(2)
                with _ann_rc1:
                    _ann_rstart = st.date_input("Start date", key="cb_ann_range_start")
                with _ann_rc2:
                    _ann_rend = st.date_input("End date", key="cb_ann_range_end")
                _ann_rlabel = st.text_input("Label (optional)", key="cb_ann_range_label")
                if st.button("Add Date Range", key="cb_ann_add_range"):
                    st.session_state.cb_annotations.append({
                        "type": "range",
                        "x0": str(_ann_rstart),
                        "x1": str(_ann_rend),
                        "label": _ann_rlabel,
                        "style": {},
                    })
                    st.rerun()

            # Display existing annotations with delete + style override
            if cb_annotations:
                st.markdown("---")
                st.markdown("**Current annotations**")
                for _ai, _ann in enumerate(cb_annotations):
                    _ann_desc = _ann.get("type", "?")
                    if _ann.get("label"):
                        _ann_desc += f': "{_ann["label"]}"'
                    elif _ann.get("text"):
                        _ann_desc += f': "{_ann["text"]}"'
                    if _ann.get("date"):
                        _ann_desc += f' @ {_ann["date"]}'
                    if _ann.get("value") is not None and _ann["type"] == "hline":
                        _ann_desc += f' y={_ann["value"]}'

                    _ann_col1, _ann_col2, _ann_col3 = st.columns([5, 1, 1])
                    with _ann_col1:
                        st.caption(_ann_desc)
                    with _ann_col2:
                        with st.popover("🎨", use_container_width=True, help="Style"):
                            _ast = _ann.get("style", {})
                            _ann_dash = st.selectbox(
                                "Line dash", ["dot", "solid", "dash", "dashdot"],
                                index=["dot", "solid", "dash", "dashdot"].index(_ast.get("line_dash", "dot")),
                                key=f"cb_ann_dash_{_ai}",
                            )
                            _ann_color = st.color_picker("Color", value=_ast.get("line_color", "#9EA3AB"), key=f"cb_ann_color_{_ai}")
                            _ann_lw = st.slider("Line width", 0.5, 5.0, value=float(_ast.get("line_width", 1.5)), step=0.5, key=f"cb_ann_lw_{_ai}")
                            _ann_fs = st.slider("Font size", 8, 20, value=int(_ast.get("font_size", 11)), key=f"cb_ann_fs_{_ai}")
                            _ann["style"] = {
                                "line_dash": _ann_dash,
                                "line_color": _ann_color,
                                "line_width": _ann_lw,
                                "font_size": _ann_fs,
                            }
                    with _ann_col3:
                        if st.button("🗑", key=f"cb_ann_del_{_ai}", help="Delete"):
                            st.session_state.cb_annotations.pop(_ai)
                            st.rerun()

        # ── Chart render ──────────────────────────────────────────────────
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
                apply_annotations(fig, cb_annotations)
                st.plotly_chart(fig, use_container_width=True)

        # ── Save bar (Chart) — always visible ─────────────────────────────
        st.markdown("---")
        st.markdown("**Save Chart**")

        _sv_item_title = st.text_input(
            "Chart title",
            value=st.session_state.get("cb_chart_title", ""),
            key="cb_save_item_title",
        )
        # Load existing tags when editing
        _existing_tags = []
        if st.session_state.cb_item_id:
            _existing_item = get_chart_item(st.session_state.cb_item_id)
            if _existing_item:
                _existing_tags = _existing_item.get("tags", [])
        _sv_tags = tag_picker(
            label="Tags",
            selected=_existing_tags,
            key="cb_save_chart_tags",
            allow_create=False,
        )
        _sv_can_save = bool(cb_series)
        _sv_col_save, _sv_col_saveas = st.columns(2)
        with _sv_col_save:
            if st.button(
                "Save",
                key="cb_save_chart_btn",
                type="primary",
                disabled=not _sv_can_save,
                use_container_width=True,
                help="Add at least one series first" if not _sv_can_save else "",
            ):
                _item_dict = {
                    "type": "chart",
                    "title": _sv_item_title.strip() or st.session_state.get("cb_chart_title", "Untitled"),
                    "tags": _sv_tags,
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
                    "annotations": list(st.session_state.cb_annotations),
                }
                if st.session_state.cb_item_id:
                    _item_dict["id"] = st.session_state.cb_item_id
                _saved_id = upsert_item(_item_dict)
                # Return to explorer after save
                st.session_state.cb_mode = "explore"
                st.session_state.cb_item_id = None
                st.session_state.cb_series = []
                st.session_state.cb_data = {}
                st.session_state.cb_annotations = []
                st.session_state.pop("cb_chart_title", None)
                st.toast("Chart saved")
                st.rerun()

        with _sv_col_saveas:
            # Save As New (only when editing an existing item)
            if st.session_state.cb_item_id and _sv_can_save:
                if st.button(
                    "Save As New",
                    key="cb_saveas_chart_btn",
                    use_container_width=True,
                    help="Save a copy without overwriting the original",
                ):
                    _item_dict_new = {
                        "type": "chart",
                        "title": _sv_item_title.strip() or st.session_state.get("cb_chart_title", "Untitled"),
                        "tags": _sv_tags,
                        "chart_subtype": "Time Series",
                        "y_axis": {"min": y_min, "max": y_max},
                        "y_axis2": {"min": y_min2, "max": y_max2},
                        "show_legend": st.session_state.get("cb_show_legend", True),
                        "default_range_years": _default_range_years if _default_range_years else None,
                        "series": list(cb_series),
                        "annotations": list(st.session_state.cb_annotations),
                        # no "id" — forces upsert_item to create a new item
                    }
                    _saved_id = upsert_item(_item_dict_new)
                    # Return to explorer after save
                    st.session_state.cb_mode = "explore"
                    st.session_state.cb_item_id = None
                    st.session_state.cb_series = []
                    st.session_state.cb_data = {}
                    st.session_state.cb_annotations = []
                    st.session_state.pop("cb_chart_title", None)
                    st.toast("Saved as new chart")
                    st.rerun()

    # ── Correlation Heatmap ──────────────────────────────────────────────
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

    # ── Scatter Plot ─────────────────────────────────────────────────────
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

    # ─────────────────────────────────────────────────────────────────────
    # CARD BUILDER
    # ─────────────────────────────────────────────────────────────────────
    elif _cb_item_type == "Card":
        st.subheader("Card Builder")

        # ── Data source (feed picker) ────────────────────────────────────
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

        # ── Card settings ─────────────────────────────────────────────
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

        # ── Live preview ──────────────────────────────────────────────
        _prev_s = None
        if _card_feed:
            try:
                from services.data_resolver import resolve_feed_data as _card_rfd
                _cdf = _card_rfd(_card_feed)
                if not _cdf.empty:
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

        # ── Save bar (Card) ───────────────────────────────────────────
        st.markdown("---")
        st.markdown("**Save Card**")

        _svc_item_title = st.text_input(
            "Card title",
            value=_card_title or _card_feed_name or "",
            key="cb_save_card_item_title",
        )
        # Load existing tags when editing a card
        _card_existing_tags = []
        if st.session_state.cb_item_id:
            _card_existing_item = get_chart_item(st.session_state.cb_item_id)
            if _card_existing_item:
                _card_existing_tags = _card_existing_item.get("tags", [])
        _svc_tags = tag_picker(
            label="Tags",
            selected=_card_existing_tags,
            key="cb_save_card_tags",
            allow_create=False,
        )
        _svc_can_save = bool(_card_feed_id)
        _svc_col_save, _svc_col_saveas = st.columns(2)
        with _svc_col_save:
            if st.button(
                "Save",
                key="cb_save_card_btn",
                type="primary",
                disabled=not _svc_can_save,
                use_container_width=True,
                help="Select a feed first" if not _svc_can_save else "",
            ):
                _card_item = {
                    "type": "card",
                    "title": _svc_item_title.strip() or _card_title or _card_feed_name,
                    "tags": _svc_tags,
                    "feed_id": _card_feed_id,
                    "value_format": _card_fmt or ",.2f",
                    "value_suffix": _card_sfx,
                    "delta_type": _card_delta,
                }
                if st.session_state.cb_item_id:
                    _card_item["id"] = st.session_state.cb_item_id
                _saved_card_id = upsert_item(_card_item)
                # Return to explorer after save
                st.session_state.cb_mode = "explore"
                st.session_state.cb_item_id = None
                st.session_state.cb_card_feed_id = None
                st.session_state.cb_card_title = ""
                st.session_state.cb_card_value_format = ",.2f"
                st.session_state.cb_card_value_suffix = ""
                st.session_state.cb_card_delta_type = "none"
                st.toast("Card saved")
                st.rerun()
        with _svc_col_saveas:
            if st.session_state.cb_item_id and _svc_can_save:
                if st.button(
                    "Save As New",
                    key="cb_saveas_card_btn",
                    use_container_width=True,
                    help="Save a copy without overwriting the original",
                ):
                    _card_item_new = {
                        "type": "card",
                        "title": _svc_item_title.strip() or _card_title or _card_feed_name,
                        "tags": _svc_tags,
                        "feed_id": _card_feed_id,
                        "value_format": _card_fmt or ",.2f",
                        "value_suffix": _card_sfx,
                        "delta_type": _card_delta,
                        # no "id" — forces upsert_item to create a new item
                    }
                    _saved_card_id = upsert_item(_card_item_new)
                    # Return to explorer after save
                    st.session_state.cb_mode = "explore"
                    st.session_state.cb_item_id = None
                    st.session_state.cb_card_feed_id = None
                    st.session_state.cb_card_title = ""
                    st.session_state.cb_card_value_format = ",.2f"
                    st.session_state.cb_card_value_suffix = ""
                    st.session_state.cb_card_delta_type = "none"
                    st.toast("Saved as new card")
                    st.rerun()
