"""
Content Chart Picker — reusable component for selecting charts from
both News Reader (catalogs/news.json chart_images) and Dashboard
(catalogs/charts.json) sources.

Returns a list of selected chart references:
  [{chart_ref, source, caption, position}, ...]
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

from modules.config.news_catalog import list_chart_images
from modules.config.chart_config import list_items


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _news_source_options() -> List[str]:
    """Unique source values across all news chart images."""
    sources = set()
    for c in list_chart_images():
        src = c.get("source", "")
        if src:
            sources.add(src)
    return sorted(sources)


def _all_news_tags() -> List[str]:
    tags = set()
    for c in list_chart_images():
        tags.update(c.get("tags", []))
    return sorted(tags)


def _all_dashboard_tags() -> List[str]:
    tags = set()
    for c in list_items(item_type="chart"):
        tags.update(c.get("tags", []))
    return sorted(tags)


# ---------------------------------------------------------------------------
# Main component
# ---------------------------------------------------------------------------


def content_chart_picker(
    key_prefix: str = "ccp",
    pre_selected: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Render a chart picker with two tabs (Research Charts, Dashboard Charts).

    Parameters
    ----------
    key_prefix   : unique prefix for all widget keys
    pre_selected : optional list of already-selected chart refs for editing

    Returns
    -------
    List of selected chart references (chart_ref, source, caption, position).
    """
    # Session key for selections
    sel_key = f"{key_prefix}_selections"
    if sel_key not in st.session_state:
        st.session_state[sel_key] = list(pre_selected) if pre_selected else []

    selections: List[Dict[str, Any]] = st.session_state[sel_key]

    selected_ids = {s["chart_ref"] for s in selections}

    tab_news, tab_dash = st.tabs(["Research Charts", "Dashboard Charts"])

    # ── Research Charts tab ───────────────────────────────────────────────
    with tab_news:
        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1:
            src_options = _news_source_options()
            src_filter = st.selectbox(
                "Source", ["All"] + src_options, key=f"{key_prefix}_ns"
            )
        with fc2:
            tag_options = _all_news_tags()
            tag_filter = st.multiselect("Tags", tag_options, key=f"{key_prefix}_nt")
        with fc3:
            from datetime import date, timedelta
            date_from = st.date_input(
                "From",
                value=date.today() - timedelta(days=90),
                key=f"{key_prefix}_ndate_from",
            )
        with fc4:
            search = st.text_input(
                "Search", key=f"{key_prefix}_nsearch", placeholder="Caption..."
            )

        # Fetch charts
        news_charts = list_chart_images(
            source=src_filter if src_filter != "All" else None,
            tags=tag_filter if tag_filter else None,
        )

        # Date range filter
        if date_from:
            from datetime import datetime as _dt
            cutoff = _dt.combine(date_from, _dt.min.time()).isoformat()
            news_charts = [
                c for c in news_charts
                if (c.get("extracted_at") or "") >= cutoff
            ]

        if search:
            sl = search.lower()
            news_charts = [
                c for c in news_charts
                if sl in (c.get("caption") or "").lower()
                or sl in (c.get("ai_description") or "").lower()
            ]

        # Sort: flagged_for_content first
        news_charts.sort(
            key=lambda c: (not c.get("flagged_for_content", False), c.get("extracted_at", "")),
        )

        st.caption(f"{len(news_charts)} charts")

        cols_per_row = 4
        for row_start in range(0, len(news_charts), cols_per_row):
            row = news_charts[row_start : row_start + cols_per_row]
            cols = st.columns(cols_per_row)
            for j, chart in enumerate(row):
                with cols[j]:
                    cid = chart.get("id", "")
                    img = chart.get("image_path", "")
                    is_selected = cid in selected_ids

                    # Highlight border if selected
                    if is_selected:
                        st.markdown(
                            "<div style='border:3px solid #44ADE2;border-radius:6px;padding:2px'>",
                            unsafe_allow_html=True,
                        )

                    if img and Path(img).exists():
                        st.image(img, use_container_width=True)
                    else:
                        st.markdown(
                            "<div style='height:100px;background:#E1DBD4;display:flex;"
                            "align-items:center;justify-content:center;border-radius:4px'>"
                            "<span style='color:#888'>No image</span></div>",
                            unsafe_allow_html=True,
                        )

                    cap = (chart.get("caption") or "")[:70]
                    if len(chart.get("caption") or "") > 70:
                        cap += "..."
                    st.caption(cap)

                    # Source badge + date + flagged badge
                    extracted = chart.get("extracted_at", "")
                    date_str = extracted[:10] if extracted else ""
                    badges = f"<span style='background:#44ADE2;color:white;padding:1px 6px;border-radius:8px;font-size:0.7rem'>{chart.get('source', 'News')}</span>"
                    if date_str:
                        badges += f" <span style='color:#888;font-size:0.7rem'>{date_str}</span>"
                    if chart.get("flagged_for_content"):
                        badges += " <span style='background:#d62728;color:white;padding:1px 6px;border-radius:8px;font-size:0.7rem'>Flagged</span>"
                    st.markdown(badges, unsafe_allow_html=True)

                    if is_selected:
                        st.markdown("</div>", unsafe_allow_html=True)

                    # Toggle button
                    btn_label = "Remove" if is_selected else "Select"
                    if st.button(
                        btn_label, key=f"{key_prefix}_nsel_{cid}", use_container_width=True
                    ):
                        if is_selected:
                            st.session_state[sel_key] = [
                                s for s in selections if s["chart_ref"] != cid
                            ]
                        else:
                            st.session_state[sel_key].append({
                                "chart_ref": cid,
                                "source": "news_reader",
                                "caption": chart.get("caption") or "",
                                "position": len(selections) + 1,
                            })
                        st.rerun()

    # ── Dashboard Charts tab ──────────────────────────────────────────────
    with tab_dash:
        dc1, dc2 = st.columns(2)
        with dc1:
            dtag_options = _all_dashboard_tags()
            dtag_filter = st.multiselect("Tags", dtag_options, key=f"{key_prefix}_dt")
        with dc2:
            dsearch = st.text_input(
                "Search", key=f"{key_prefix}_dsearch", placeholder="Title..."
            )

        dash_charts = list_items(
            item_type="chart",
            tags=dtag_filter if dtag_filter else None,
        )

        if dsearch:
            sl = dsearch.lower()
            dash_charts = [
                c for c in dash_charts
                if sl in (c.get("title") or "").lower()
            ]

        st.caption(f"{len(dash_charts)} charts")

        for row_start in range(0, len(dash_charts), cols_per_row):
            row = dash_charts[row_start : row_start + cols_per_row]
            cols = st.columns(cols_per_row)
            for j, chart in enumerate(row):
                with cols[j]:
                    cid = chart.get("id", "")
                    is_selected = cid in selected_ids

                    if is_selected:
                        st.markdown(
                            "<div style='border:3px solid #44ADE2;border-radius:6px;padding:2px'>",
                            unsafe_allow_html=True,
                        )

                    # Show chart title as placeholder (Plotly rendering is expensive)
                    title = chart.get("title", "Untitled")
                    tag_str = ", ".join(chart.get("tags", []))
                    st.markdown(
                        f"<div style='height:100px;background:#f5f3f0;display:flex;"
                        f"flex-direction:column;align-items:center;justify-content:center;"
                        f"border-radius:4px;border:1px solid #E1DBD4'>"
                        f"<span style='font-weight:600;font-size:0.85rem;text-align:center'>{title}</span>"
                        f"<span style='color:#888;font-size:0.7rem;margin-top:4px'>{tag_str}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                    if is_selected:
                        st.markdown("</div>", unsafe_allow_html=True)

                    btn_label = "Remove" if is_selected else "Select"
                    if st.button(
                        btn_label, key=f"{key_prefix}_dsel_{cid}", use_container_width=True
                    ):
                        if is_selected:
                            st.session_state[sel_key] = [
                                s for s in selections if s["chart_ref"] != cid
                            ]
                        else:
                            st.session_state[sel_key].append({
                                "chart_ref": cid,
                                "source": "dashboard",
                                "caption": chart.get("title", ""),
                                "position": len(selections) + 1,
                            })
                        st.rerun()

    # ── Selected charts strip ─────────────────────────────────────────────
    selections = st.session_state[sel_key]  # refresh
    if selections:
        st.markdown("---")
        st.markdown(f"**Selected Charts ({len(selections)})**")
        for i, sel in enumerate(selections):
            c1, c2, c3, c4 = st.columns([1, 6, 1, 1])
            with c1:
                st.markdown(f"**{i + 1}**")
            with c2:
                src_badge = "News" if sel["source"] == "news_reader" else "Dashboard"
                st.caption(f"[{src_badge}] {sel['caption'][:60]}")
            with c3:
                if i > 0 and st.button("\u2191", key=f"{key_prefix}_up_{i}"):
                    selections[i], selections[i - 1] = selections[i - 1], selections[i]
                    _renumber(selections)
                    st.rerun()
            with c4:
                if i < len(selections) - 1 and st.button(
                    "\u2193", key=f"{key_prefix}_dn_{i}"
                ):
                    selections[i], selections[i + 1] = selections[i + 1], selections[i]
                    _renumber(selections)
                    st.rerun()

    return selections


def _renumber(selections: List[Dict[str, Any]]) -> None:
    for i, s in enumerate(selections):
        s["position"] = i + 1
