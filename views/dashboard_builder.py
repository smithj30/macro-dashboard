"""
Dashboard Builder UI.

Multi-step form for creating and editing dynamic dashboards.

Session state keys used:
  builder_step      : int  0=list, 1=name/desc, 2=sections, 3=preview/save
  builder_draft     : dict  in-progress config
  builder_edit_id   : str | None  None for new, dashboard id for editing
  b_pending_series  : list  series accumulator while building a chart section
"""

from __future__ import annotations

import copy
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st

from modules.config.dashboard_config import (
    delete_config,
    list_dynamic_dashboards,
    save_config,
)
from modules.config.chart_catalog import list_catalogs, load_catalog, get_item as catalog_get_item
from modules.data_ingestion.fred_loader import search_fred


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_LAYOUT_OPTIONS = ["full", "half", "third", "quarter"]
_LAYOUT_LABELS = {"full": "Full Width", "half": "Half (1/2)", "third": "Third (1/3)", "quarter": "Quarter (1/4)"}


def _init_state() -> None:
    if "builder_step" not in st.session_state:
        st.session_state.builder_step = 0
    if "builder_draft" not in st.session_state:
        st.session_state.builder_draft = {}
    if "builder_edit_id" not in st.session_state:
        st.session_state.builder_edit_id = None
    if "b_pending_series" not in st.session_state:
        st.session_state.b_pending_series = []
    if "builder_pending_delete" not in st.session_state:
        st.session_state.builder_pending_delete = None  # dashboard id awaiting delete confirmation
    if "builder_editing_section_idx" not in st.session_state:
        st.session_state.builder_editing_section_idx = None


def _reset_builder() -> None:
    st.session_state.builder_step = 0
    st.session_state.builder_draft = {}
    st.session_state.builder_edit_id = None


def _go_step(n: int) -> None:
    st.session_state.builder_step = n
    st.rerun()


def _new_section_id() -> str:
    return f"sec_{uuid.uuid4().hex[:8]}"


def _resolve_item_title(catalog_id: str, item_id: str) -> str:
    """Look up the actual title of a chart/card item from its catalog."""
    try:
        item = catalog_get_item(catalog_id, item_id)
        if item:
            return item.get("title", item_id)
    except Exception:
        pass
    return item_id


# ---------------------------------------------------------------------------
# Step 0 — List existing dashboards
# ---------------------------------------------------------------------------


def _step_list() -> None:
    st.subheader("Your Dashboards")
    dashboards = list_dynamic_dashboards()

    if not dashboards:
        st.info("No custom dashboards yet. Create your first one below.")
    else:
        for cfg in dashboards:
            col_title, col_edit, col_clone, col_del = st.columns([4, 1, 1, 1])
            with col_title:
                st.markdown(f"**{cfg.get('title', cfg['id'])}**")
                if cfg.get("description"):
                    st.caption(cfg["description"])
            with col_edit:
                if st.button("Edit", key=f"edit_{cfg['id']}"):
                    # Warn if there's an unsaved draft in progress for a different dashboard
                    current_draft = st.session_state.builder_draft
                    current_edit_id = st.session_state.builder_edit_id
                    draft_has_content = bool(current_draft.get("title") or current_draft.get("sections"))
                    if draft_has_content and current_edit_id != cfg["id"]:
                        st.session_state.builder_draft = cfg
                        st.session_state.builder_edit_id = cfg["id"]
                        st.warning(
                            f"Unsaved changes to **{current_draft.get('title', 'another dashboard')}** "
                            f"were discarded. Use **Save Dashboard** before switching."
                        )
                    else:
                        st.session_state.builder_draft = cfg
                        st.session_state.builder_edit_id = cfg["id"]
                    _go_step(1)
            with col_clone:
                if st.button("Clone", key=f"clone_{cfg['id']}"):
                    new_cfg = copy.deepcopy(cfg)
                    new_cfg["id"] = f"{cfg['id']}_copy_{uuid.uuid4().hex[:4]}"
                    new_cfg["title"] = f"Copy of {cfg.get('title', cfg['id'])}"
                    new_cfg["created_at"] = datetime.now().isoformat()
                    save_config(new_cfg)
                    st.rerun()
            with col_del:
                if st.session_state.builder_pending_delete == cfg["id"]:
                    if st.button("Confirm", key=f"del_confirm_{cfg['id']}", type="primary"):
                        delete_config(cfg["id"])
                        st.session_state.builder_pending_delete = None
                        st.rerun()
                else:
                    if st.button("Delete", key=f"del_{cfg['id']}"):
                        st.session_state.builder_pending_delete = cfg["id"]
                        st.rerun()

    st.markdown("---")
    if st.button("+ New Dashboard", type="primary", use_container_width=True):
        _reset_builder()
        _go_step(1)


# ---------------------------------------------------------------------------
# Step 1 — Name, description, news query
# ---------------------------------------------------------------------------


def _step_name() -> None:
    st.subheader("1. Dashboard Details")

    draft = st.session_state.builder_draft
    is_edit = st.session_state.builder_edit_id is not None

    title = st.text_input(
        "Dashboard title *",
        value=draft.get("title", ""),
        placeholder="e.g. US Housing Market",
        key="b_title",
    )
    description = st.text_area(
        "Description (optional)",
        value=draft.get("description", ""),
        placeholder="Brief description of what this dashboard covers",
        key="b_desc",
        height=80,
    )
    news_query = st.text_input(
        "News search query (optional)",
        value=draft.get("news_query", ""),
        placeholder="e.g. US housing real estate mortgage rates",
        help="Headlines will be fetched from Reuters for this query.",
        key="b_news_query",
    )

    col_back, col_next = st.columns([1, 3])
    with col_back:
        if st.button("Back", use_container_width=True):
            _reset_builder()
            _go_step(0)
    with col_next:
        if st.button("Next: Add Sections →", type="primary", use_container_width=True):
            if not title.strip():
                st.warning("Please enter a dashboard title.")
                return

            # Build or update draft
            dashboard_id = draft.get("id") or title.strip().lower().replace(" ", "_").replace("-", "_")
            draft.update(
                {
                    "id": dashboard_id,
                    "title": title.strip(),
                    "description": description.strip(),
                    "type": "dynamic",
                    "news_query": news_query.strip(),
                    "created_at": draft.get("created_at", datetime.now().isoformat()),
                    "sections": draft.get("sections", []),
                }
            )
            st.session_state.builder_draft = draft
            _go_step(2)


# ---------------------------------------------------------------------------
# Step 2 — Add / reorder sections
# ---------------------------------------------------------------------------


def _step_sections() -> None:
    st.subheader("2. Sections")

    draft = st.session_state.builder_draft
    sections: List[Dict[str, Any]] = draft.get("sections", [])

    # ── Current sections list ──────────────────────────────────────────────
    if sections:
        st.markdown("**Current sections** (drag via ↑/↓ to reorder):")
        for idx, sec in enumerate(sections):
            _stype = sec.get("type", "chart")
            _icon = {"chart": "📊", "news": "📰", "catalog_chart": "📊", "card_row": "🃏"}.get(_stype, "❓")
            layout = sec.get("layout", "full")

            # Resolve display label
            if _stype == "card_row":
                _card_names = []
                for card in sec.get("cards", []):
                    _card_names.append(_resolve_item_title(card.get("catalog_id", ""), card.get("item_id", "")))
                _label = "Cards: " + ", ".join(_card_names) if _card_names else "Card Row (empty)"
            elif _stype == "catalog_chart":
                if sec.get("title_override"):
                    _label = sec["title_override"]
                else:
                    _label = _resolve_item_title(sec.get("catalog_id", ""), sec.get("item_id", ""))
            else:
                _label = sec.get("title", "Untitled")

            # Determine if this section has an editable chart/card item
            _has_open = _stype in ("catalog_chart", "card_row")

            col_info, col_settings, col_open, col_up, col_dn, col_rm = st.columns([4, 1, 1, 1, 1, 1])

            with col_info:
                st.markdown(f"{_icon} **{_label}** `{layout}`")

            with col_settings:
                if st.button("⚙", key=f"sec_settings_{idx}", use_container_width=True, help="Edit section properties"):
                    st.session_state.builder_editing_section_idx = idx
                    st.rerun()

            with col_open:
                if _stype == "catalog_chart":
                    if st.button("Open", key=f"sec_edit_{idx}", use_container_width=True, help="Open in Chart Builder"):
                        st.session_state.cb_edit_request = {
                            "catalog_id": sec.get("catalog_id", ""),
                            "item_id": sec.get("item_id", ""),
                        }
                        st.session_state.page = "Chart Builder"
                        st.rerun()
                elif _stype == "card_row":
                    cards = sec.get("cards", [])
                    if cards:
                        if st.button("Open", key=f"sec_edit_{idx}", use_container_width=True, help="Open in Chart Builder"):
                            st.session_state.cb_edit_request = {
                                "catalog_id": cards[0].get("catalog_id", ""),
                                "item_id": cards[0].get("item_id", ""),
                            }
                            st.session_state.page = "Chart Builder"
                            st.rerun()

            with col_up:
                if idx > 0 and st.button("↑", key=f"up_{idx}"):
                    sections[idx - 1], sections[idx] = sections[idx], sections[idx - 1]
                    draft["sections"] = sections
                    st.session_state.builder_draft = draft
                    st.rerun()
            with col_dn:
                if idx < len(sections) - 1 and st.button("↓", key=f"dn_{idx}"):
                    sections[idx], sections[idx + 1] = sections[idx + 1], sections[idx]
                    draft["sections"] = sections
                    st.session_state.builder_draft = draft
                    st.rerun()
            with col_rm:
                if st.button("✕", key=f"rm_{idx}"):
                    sections.pop(idx)
                    draft["sections"] = sections
                    st.session_state.builder_draft = draft
                    st.session_state.builder_editing_section_idx = None
                    st.rerun()

            # ── Inline section editing form ──────────────────────────
            if st.session_state.builder_editing_section_idx == idx:
                with st.container():
                    st.markdown(f"**Edit Section Properties**")
                    _ed_layout = st.selectbox(
                        "Layout",
                        options=_LAYOUT_OPTIONS,
                        index=_LAYOUT_OPTIONS.index(layout) if layout in _LAYOUT_OPTIONS else 0,
                        format_func=lambda x: _LAYOUT_LABELS.get(x, x),
                        key=f"sec_ed_layout_{idx}",
                    )
                    _ed_title_override = None
                    if _stype == "catalog_chart":
                        _ed_title_override = st.text_input(
                            "Title override (blank = use item title)",
                            value=sec.get("title_override") or "",
                            key=f"sec_ed_title_{idx}",
                        )
                    elif _stype in ("chart", "news"):
                        _ed_title_override = st.text_input(
                            "Title",
                            value=sec.get("title", ""),
                            key=f"sec_ed_title_{idx}",
                        )
                    _ed_apply, _ed_cancel = st.columns(2)
                    with _ed_apply:
                        if st.button("Apply", key=f"sec_ed_apply_{idx}", type="primary"):
                            sections[idx]["layout"] = _ed_layout
                            if _ed_title_override is not None:
                                if _stype == "catalog_chart":
                                    sections[idx]["title_override"] = _ed_title_override.strip() or None
                                else:
                                    sections[idx]["title"] = _ed_title_override.strip()
                            draft["sections"] = sections
                            st.session_state.builder_draft = draft
                            # Auto-save to disk when editing an existing dashboard
                            if st.session_state.builder_edit_id is not None:
                                save_config(draft)
                            st.session_state.builder_editing_section_idx = None
                            st.rerun()
                    with _ed_cancel:
                        if st.button("Cancel", key=f"sec_ed_cancel_{idx}"):
                            st.session_state.builder_editing_section_idx = None
                            st.rerun()
    else:
        st.info("No sections yet. Add one below.")

    st.markdown("---")

    # ── Add new section ────────────────────────────────────────────────────
    add_type = st.radio(
        "Add section type:",
        ["Catalog Chart", "Card Row", "News"],
        horizontal=True,
        key="b_add_type",
    )

    if add_type == "Catalog Chart":
        _catalog_chart_section_form(draft, sections)
    elif add_type == "Card Row":
        _card_row_section_form(draft, sections)
    else:
        _news_section_form(draft, sections)

    st.markdown("---")

    col_back, col_next = st.columns([1, 3])
    with col_back:
        if st.button("Back", key="s2_back", use_container_width=True):
            _go_step(1)
    with col_next:
        if st.button("Next: Preview & Save →", type="primary", use_container_width=True, key="s2_next"):
            if not sections:
                st.warning("Add at least one section before continuing.")
                return
            draft["sections"] = sections
            st.session_state.builder_draft = draft
            _go_step(3)


def _chart_section_form(draft: Dict[str, Any], sections: List[Dict[str, Any]]) -> None:
    st.markdown("**New Chart Section**")

    sec_title = st.text_input("Section title", placeholder="e.g. Industrial Production", key="b_sec_title")
    layout = st.selectbox("Layout", ["full", "left", "right"], key="b_sec_layout")

    # FRED series search
    st.markdown("**Add FRED series**")
    col_search, col_btn = st.columns([4, 1])
    with col_search:
        search_q = st.text_input("Search FRED", placeholder="unemployment, CPI, GDP…", key="b_fred_search")
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        do_search = st.button("Search", key="b_fred_search_btn")

    if do_search and search_q:
        with st.spinner("Searching FRED…"):
            try:
                results = search_fred(search_q, limit=20)
                if not results.empty:
                    st.session_state["b_fred_results"] = results
                else:
                    st.info("No results.")
            except Exception as e:
                st.warning(f"Search failed: {e}")

    if "b_fred_results" in st.session_state:
        results = st.session_state["b_fred_results"]
        st.dataframe(results[["id", "title", "units", "frequency"]].head(15), use_container_width=True, height=180)

    # Series definition inputs
    col_a, col_b, col_c = st.columns([2, 3, 2])
    with col_a:
        series_id = st.text_input("Series ID", placeholder="INDPRO", key="b_series_id").strip().upper()
    with col_b:
        series_label = st.text_input("Label", placeholder="Industrial Production", key="b_series_label").strip()
    with col_c:
        transform = st.selectbox("Transform", ["none", "yoy", "mom", "rolling_12"], key="b_series_transform")

    col_d, col_e = st.columns(2)
    with col_d:
        years_back = st.number_input("Years of history", min_value=1, max_value=50, value=10, key="b_series_years")
    with col_e:
        axis = st.selectbox("Axis", [1, 2], key="b_series_axis", help="2 = secondary y-axis")

    if st.button("+ Add Series", key="b_add_series"):
        if not series_id:
            st.warning("Enter a Series ID.")
        else:
            label = series_label or series_id
            st.session_state.b_pending_series.append(
                {
                    "source": "fred",
                    "series_id": series_id,
                    "label": label,
                    "transform": transform,
                    "years_back": int(years_back),
                    "axis": int(axis),
                }
            )

    pending = st.session_state.b_pending_series
    if pending:
        st.markdown(f"**Series queued ({len(pending)}):**")
        for s in pending:
            st.caption(f"  {s['label']} ({s['series_id']}) — {s['transform']}, {s['years_back']}yr, axis {s['axis']}")

    # Y-axis options
    with st.expander("Y-axis options (optional)"):
        has_secondary = any(s.get("axis") == 2 for s in pending)
        col_ya, col_yb = st.columns(2)
        with col_ya:
            en_ymin = st.checkbox("Set Y min", key="b_ymin_en")
            y_min_v = st.number_input("Y min", value=0.0, key="b_ymin_v", disabled=not en_ymin)
        with col_yb:
            en_ymax = st.checkbox("Set Y max", key="b_ymax_en")
            y_max_v = st.number_input("Y max", value=100.0, key="b_ymax_v", disabled=not en_ymax)

        if has_secondary:
            col_yc, col_yd = st.columns(2)
            with col_yc:
                en_ymin2 = st.checkbox("Set Y2 min", key="b_ymin2_en")
                y_min2_v = st.number_input("Y2 min", value=0.0, key="b_ymin2_v", disabled=not en_ymin2)
            with col_yd:
                en_ymax2 = st.checkbox("Set Y2 max", key="b_ymax2_en")
                y_max2_v = st.number_input("Y2 max", value=100.0, key="b_ymax2_v", disabled=not en_ymax2)
        else:
            en_ymin2 = en_ymax2 = False
            y_min2_v = y_max2_v = 0.0

    chart_type = st.selectbox("Chart type", ["line", "bar", "area"], key="b_chart_type_sel")

    if st.button("Add This Section", key="b_add_chart_section", type="primary"):
        if not pending:
            st.warning("Add at least one series first.")
            return
        if not sec_title.strip():
            st.warning("Enter a section title.")
            return

        new_sec: Dict[str, Any] = {
            "id": _new_section_id(),
            "type": "chart",
            "title": sec_title.strip(),
            "layout": layout,
            "chart_type": chart_type,
            "series": pending[:],
            "y_axis": {
                "min": float(y_min_v) if en_ymin else None,
                "max": float(y_max_v) if en_ymax else None,
            },
        }
        if has_secondary:
            new_sec["y_axis2"] = {
                "min": float(y_min2_v) if en_ymin2 else None,
                "max": float(y_max2_v) if en_ymax2 else None,
            }

        sections.append(new_sec)
        draft["sections"] = sections
        st.session_state.builder_draft = draft
        st.session_state.b_pending_series = []
        # Clear search results
        st.session_state.pop("b_fred_results", None)
        st.rerun()


def _news_section_form(draft: Dict[str, Any], sections: List[Dict[str, Any]]) -> None:
    st.markdown("**New News Section**")

    news_title = st.text_input("Section title", value="Latest Headlines", key="b_news_title")
    news_layout = st.selectbox(
        "Layout",
        options=_LAYOUT_OPTIONS,
        format_func=lambda x: _LAYOUT_LABELS.get(x, x),
        key="b_news_layout",
    )
    news_query = st.text_input(
        "News query (leave blank to use dashboard-level query)",
        placeholder="e.g. US housing mortgage",
        key="b_news_sec_query",
    )

    if st.button("Add This News Section", key="b_add_news_section", type="primary"):
        new_sec = {
            "id": _new_section_id(),
            "type": "news",
            "title": news_title.strip() or "Latest Headlines",
            "layout": news_layout,
            "query": news_query.strip(),
        }
        sections.append(new_sec)
        draft["sections"] = sections
        st.session_state.builder_draft = draft
        st.rerun()


# ---------------------------------------------------------------------------
# Catalog Chart section form
# ---------------------------------------------------------------------------


def _catalog_chart_section_form(draft: Dict[str, Any], sections: List[Dict[str, Any]]) -> None:
    st.markdown("**New Catalog Chart Section**")

    catalogs = list_catalogs()
    if not catalogs:
        st.info("No chart catalogs yet. Create one in the Chart Builder.")
        return

    cat_options = {c["title"]: c["id"] for c in catalogs}
    cat_sel = st.selectbox("Catalog", options=list(cat_options.keys()), key="b_cc_catalog")
    cat_id = cat_options.get(cat_sel, "")

    if cat_id:
        cat_data = load_catalog(cat_id)
        chart_items = [it for it in (cat_data.get("items", []) if cat_data else []) if it.get("type") == "chart"]
        if not chart_items:
            st.info("No chart items in this catalog.")
            return

        item_options = {f"{it.get('title', it['id'])}": it["id"] for it in chart_items}
        item_sel = st.selectbox("Chart item", options=list(item_options.keys()), key="b_cc_item")
        item_id = item_options.get(item_sel, "")

        layout = st.selectbox(
            "Layout",
            options=_LAYOUT_OPTIONS,
            format_func=lambda x: _LAYOUT_LABELS.get(x, x),
            key="b_cc_layout",
        )
        title_override = st.text_input(
            "Title override (blank = use item title)",
            placeholder="Leave blank to use saved title",
            key="b_cc_title_override",
        )

        if st.button("Add Catalog Chart Section", key="b_add_cc_section", type="primary"):
            if not item_id:
                st.warning("Select a chart item.")
                return
            new_sec: Dict[str, Any] = {
                "id": _new_section_id(),
                "type": "catalog_chart",
                "layout": layout,
                "catalog_id": cat_id,
                "item_id": item_id,
                "title_override": title_override.strip() or None,
            }
            sections.append(new_sec)
            draft["sections"] = sections
            st.session_state.builder_draft = draft
            st.rerun()


# ---------------------------------------------------------------------------
# Card Row section form
# ---------------------------------------------------------------------------


def _card_row_section_form(draft: Dict[str, Any], sections: List[Dict[str, Any]]) -> None:
    st.markdown("**New Card Row Section**")

    catalogs = list_catalogs()
    if not catalogs:
        st.info("No chart catalogs yet. Create one in the Chart Builder.")
        return

    cat_options = {c["title"]: c["id"] for c in catalogs}
    cat_sel = st.selectbox("Catalog", options=list(cat_options.keys()), key="b_cr_catalog")
    cat_id = cat_options.get(cat_sel, "")

    if cat_id:
        cat_data = load_catalog(cat_id)
        card_items = [it for it in (cat_data.get("items", []) if cat_data else []) if it.get("type") == "card"]
        if not card_items:
            st.info("No card items in this catalog. Create card items in the Chart Builder (Card tab).")
            return

        item_options = {f"{it.get('title', it['id'])} ({it.get('series_id','')})": it["id"] for it in card_items}
        selected_items = st.multiselect(
            "Card items (select 1–4)",
            options=list(item_options.keys()),
            max_selections=4,
            key="b_cr_items",
        )

        if st.button("Add Card Row Section", key="b_add_cr_section", type="primary"):
            if not selected_items:
                st.warning("Select at least one card item.")
                return
            cards_payload = [
                {"catalog_id": cat_id, "item_id": item_options[label]}
                for label in selected_items
            ]
            new_sec = {
                "id": _new_section_id(),
                "type": "card_row",
                "layout": "full",
                "cards": cards_payload,
            }
            sections.append(new_sec)
            draft["sections"] = sections
            st.session_state.builder_draft = draft
            st.rerun()


# ---------------------------------------------------------------------------
# Step 3 — Preview & Save
# ---------------------------------------------------------------------------


def _step_preview() -> None:
    st.subheader("3. Preview & Save")

    draft = st.session_state.builder_draft
    st.markdown(f"**Title:** {draft.get('title', '')}  \n**Description:** {draft.get('description', '')}  \n**News query:** {draft.get('news_query', '') or '(none)'}")

    sections = draft.get("sections", [])
    if sections:
        st.markdown(f"**Sections ({len(sections)}):**")
        for sec in sections:
            stype = sec.get("type", "chart")
            if stype == "chart":
                icon = "📊"
                detail = f"{len(sec.get('series', []))} series"
                label = sec.get("title", "Untitled")
            elif stype == "news":
                icon = "📰"
                detail = sec.get("query", "")
                label = sec.get("title", "News")
            elif stype == "catalog_chart":
                icon = "📊"
                label = sec.get("title_override") or _resolve_item_title(sec.get("catalog_id", ""), sec.get("item_id", ""))
                detail = f"`{sec.get('layout', 'full')}`"
            elif stype == "card_row":
                icon = "🃏"
                _card_names = [_resolve_item_title(c.get("catalog_id", ""), c.get("item_id", "")) for c in sec.get("cards", [])]
                label = "Cards: " + ", ".join(_card_names) if _card_names else "Card Row (empty)"
                detail = f"{len(sec.get('cards', []))} card(s)"
            else:
                icon = "❓"
                detail = ""
                label = stype
            st.markdown(f"- {icon} **{label}** `{sec.get('layout', 'full')}` — {detail}")

    with st.expander("View raw config JSON"):
        st.json(draft)

    # Live dashboard preview
    if sections:
        st.markdown("---")
        st.markdown("**Live Preview**")
        try:
            from views.dynamic_dashboard import render as _render_preview
            _render_preview(draft, preview=True)
        except Exception as exc:
            st.warning(f"Preview could not be rendered: {exc}")

    col_back, col_save = st.columns([1, 3])
    with col_back:
        if st.button("Back", key="s3_back", use_container_width=True):
            _go_step(2)
    with col_save:
        if st.button("Save Dashboard", type="primary", use_container_width=True, key="s3_save"):
            save_config(draft)
            st.success(f"Dashboard **{draft.get('title')}** saved!")
            _reset_builder()
            st.rerun()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def _draft_has_content() -> bool:
    """Check if the current builder draft has meaningful content."""
    draft = st.session_state.get("builder_draft", {})
    return bool(draft.get("title") or draft.get("sections"))


def render() -> None:
    st.title("Dashboard Builder")
    _init_state()

    # Track page entry: if we're coming from a different page, decide whether
    # to reset or offer to resume an in-progress draft.
    prev_page = st.session_state.get("_builder_prev_page")
    current_page = st.session_state.get("page", "")
    st.session_state._builder_prev_page = current_page

    step = st.session_state.builder_step

    if prev_page != current_page:
        # Just arrived from a different page
        if step != 0 and _draft_has_content():
            # There's an in-progress draft — show resume/discard banner
            draft_title = st.session_state.builder_draft.get("title", "Untitled")
            st.info(f"You have an unsaved draft: **{draft_title}**")
            col_resume, col_discard = st.columns(2)
            with col_resume:
                if st.button("Resume Editing", type="primary", use_container_width=True, key="builder_resume"):
                    pass  # Continue below with current step
                else:
                    return  # Wait for user action
            with col_discard:
                if st.button("Discard & Start Over", use_container_width=True, key="builder_discard"):
                    _reset_builder()
                    st.rerun()
                else:
                    return  # Wait for user action
        elif step != 0:
            # No meaningful draft, just reset silently
            _reset_builder()
            step = 0

    # Show dashboard title when editing (steps 1+)
    if step > 0:
        draft = st.session_state.builder_draft
        draft_title = draft.get("title", "")
        is_edit = st.session_state.builder_edit_id is not None
        if draft_title:
            prefix = "Editing" if is_edit else "Creating"
            st.markdown(f"#### {prefix}: {draft_title}")
        elif not is_edit:
            st.markdown("#### New Dashboard")

    # Progress indicator
    steps = ["My Dashboards", "Details", "Sections", "Preview & Save"]
    progress_text = " → ".join(
        f"**{s}**" if i == step else s for i, s in enumerate(steps)
    )
    st.caption(progress_text)
    st.markdown("---")

    if step == 0:
        _step_list()
    elif step == 1:
        _step_name()
    elif step == 2:
        _step_sections()
    elif step == 3:
        _step_preview()
    else:
        _reset_builder()
        st.rerun()
