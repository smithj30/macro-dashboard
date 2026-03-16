"""
House View — living macro view document organized by theme sections.

Editable inline. All changes auto-save to catalogs/house_view.json.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

from modules.config.house_view_catalog import (
    load_house_view,
    save_house_view,
    add_section,
    delete_section,
    add_bullet,
    update_bullet,
    delete_bullet,
    attach_chart_to_bullet,
    detach_chart_from_bullet,
)
from modules.config.tag_catalog import list_tags


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_date(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%b %d")
    except Exception:
        return ""


def _available_themes() -> List[Dict[str, str]]:
    """Return tag themes not already used as sections."""
    hv = load_house_view()
    existing = {s["theme"] for s in hv.get("sections", [])}
    all_tags = list_tags()
    return [
        {"name": t["name"], "color": t.get("color", "#888")}
        for t in all_tags
        if t["name"] not in existing
    ]


def _theme_title(theme: str) -> str:
    """Convert a theme slug to a display title."""
    return theme.replace("-", " ").replace("_", " ").title()


# ---------------------------------------------------------------------------
# Mini chart picker for attaching charts to bullets
# ---------------------------------------------------------------------------

def _mini_chart_picker(theme: str, bullet_idx: int, current_refs: List[str]):
    """Show a compact chart picker for attaching/detaching charts to a bullet."""
    from modules.config.news_catalog import list_chart_images, get_chart_image
    from modules.config.chart_config import list_items

    key_base = f"hv_mcp_{theme}_{bullet_idx}"

    # News charts (show first 20)
    news_charts = list_chart_images()[:20]
    dash_charts = list_items(item_type="chart")[:20]

    st.caption("Click to attach/detach charts:")

    cols_per_row = 5
    # News charts
    if news_charts:
        st.markdown("**Research Charts**", help="From News Reader")
        for row_start in range(0, min(len(news_charts), 10), cols_per_row):
            row = news_charts[row_start : row_start + cols_per_row]
            cols = st.columns(cols_per_row)
            for j, ch in enumerate(row):
                with cols[j]:
                    cid = ch.get("id", "")
                    is_attached = cid in current_refs
                    img = ch.get("image_path", "")
                    if img and Path(img).exists():
                        st.image(img, use_container_width=True)
                    cap = (ch.get("caption") or "")[:30]
                    st.caption(cap)
                    label = "Detach" if is_attached else "Attach"
                    if st.button(label, key=f"{key_base}_n_{cid}"):
                        if is_attached:
                            detach_chart_from_bullet(theme, bullet_idx, cid)
                        else:
                            attach_chart_to_bullet(theme, bullet_idx, cid)
                        st.rerun()

    # Dashboard charts
    if dash_charts:
        st.markdown("**Dashboard Charts**")
        for row_start in range(0, min(len(dash_charts), 10), cols_per_row):
            row = dash_charts[row_start : row_start + cols_per_row]
            cols = st.columns(cols_per_row)
            for j, ch in enumerate(row):
                with cols[j]:
                    cid = ch.get("id", "")
                    is_attached = cid in current_refs
                    st.caption(ch.get("title", "Untitled")[:30])
                    label = "Detach" if is_attached else "Attach"
                    if st.button(label, key=f"{key_base}_d_{cid}"):
                        if is_attached:
                            detach_chart_from_bullet(theme, bullet_idx, cid)
                        else:
                            attach_chart_to_bullet(theme, bullet_idx, cid)
                        st.rerun()


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------


def render():
    hv = load_house_view()

    # ── Header ────────────────────────────────────────────────────────────
    h1, h2 = st.columns([3, 2])
    with h1:
        st.title(hv.get("title", "House View"))
    with h2:
        last_updated = hv.get("last_updated")
        if last_updated:
            st.caption(f"Last updated: {_format_date(last_updated)}")
        ec1, ec2 = st.columns(2)
        with ec1:
            st.button("Export PDF", disabled=True, help="Coming in Phase 2", key="hv_pdf")
        with ec2:
            st.button("Export Word", disabled=True, help="Coming in Phase 2", key="hv_word")

    st.markdown("---")

    # ── Sections ──────────────────────────────────────────────────────────
    sections = hv.get("sections", [])

    for sec in sections:
        theme = sec["theme"]
        title = sec.get("title", _theme_title(theme))
        bullets = sec.get("bullets", [])

        # Section header
        sh1, sh2, sh3 = st.columns([6, 2, 1])
        with sh1:
            st.markdown(f"### {title.upper()}")
        with sh2:
            if st.button("+ Add Bullet", key=f"hv_addbul_{theme}"):
                add_bullet(theme, "")
                st.rerun()
        with sh3:
            confirm_key = f"hv_confirm_delsec_{theme}"
            if st.session_state.get(confirm_key):
                if st.button("Confirm?", key=f"hv_delsec_y_{theme}", type="primary"):
                    st.session_state[confirm_key] = False
                    delete_section(theme)
                    st.rerun()
            else:
                if st.button("Remove", key=f"hv_delsec_{theme}", help="Remove this section"):
                    st.session_state[confirm_key] = True
                    st.rerun()

        # Bullets
        if not bullets:
            st.caption("*(no bullets yet)*")
        else:
            for i, bullet in enumerate(bullets):
                text = bullet.get("text", "")
                updated = _format_date(bullet.get("updated_at"))
                charts = bullet.get("supporting_charts", [])

                bc1, bc2, bc3, bc4, bc5 = st.columns([8, 1, 1, 1, 1])

                with bc1:
                    # Inline edit
                    new_text = st.text_input(
                        f"Bullet",
                        value=text,
                        key=f"hv_bul_{theme}_{i}",
                        label_visibility="collapsed",
                    )
                    # Auto-save on change
                    if new_text != text and new_text.strip():
                        update_bullet(theme, i, new_text)

                    # Metadata line
                    meta_parts = []
                    if updated:
                        meta_parts.append(f"Updated: {updated}")
                    if charts:
                        meta_parts.append(f"Charts: {len(charts)}")
                    if meta_parts:
                        st.caption(" | ".join(meta_parts))

                    # Show supporting chart thumbnails
                    if charts:
                        thumb_cols = st.columns(min(len(charts), 4))
                        for ci, cref in enumerate(charts[:4]):
                            with thumb_cols[ci]:
                                _show_chart_thumbnail(cref)

                with bc2:
                    # Move up
                    if i > 0 and st.button("\u2191", key=f"hv_bup_{theme}_{i}"):
                        bullets[i], bullets[i - 1] = bullets[i - 1], bullets[i]
                        save_house_view(hv)
                        st.rerun()

                with bc3:
                    # Move down
                    if i < len(bullets) - 1 and st.button(
                        "\u2193", key=f"hv_bdn_{theme}_{i}"
                    ):
                        bullets[i], bullets[i + 1] = bullets[i + 1], bullets[i]
                        save_house_view(hv)
                        st.rerun()

                with bc4:
                    # Chart attach/detach
                    if st.button("\U0001F4CA", key=f"hv_bch_{theme}_{i}"):
                        picker_key = f"hv_picker_{theme}_{i}"
                        st.session_state[picker_key] = not st.session_state.get(picker_key, False)
                        st.rerun()

                with bc5:
                    # Delete with confirmation
                    del_key = f"hv_confirm_bdel_{theme}_{i}"
                    if st.session_state.get(del_key):
                        if st.button("Sure?", key=f"hv_bdel_y_{theme}_{i}", type="primary"):
                            st.session_state[del_key] = False
                            delete_bullet(theme, i)
                            st.rerun()
                    else:
                        if st.button("X", key=f"hv_bdel_{theme}_{i}"):
                            st.session_state[del_key] = True
                            st.rerun()

                # Show mini chart picker if toggled
                picker_key = f"hv_picker_{theme}_{i}"
                if st.session_state.get(picker_key, False):
                    with st.expander("Attach Charts", expanded=True):
                        _mini_chart_picker(theme, i, charts)

        st.markdown("---")

    # ── Add Section ───────────────────────────────────────────────────────
    available = _available_themes()
    if available:
        ac1, ac2, ac3 = st.columns([2, 2, 1])
        with ac1:
            new_theme = st.selectbox(
                "Add Section",
                [t["name"] for t in available],
                key="hv_new_theme",
            )
        with ac2:
            default_title = _theme_title(new_theme) if new_theme else ""
            new_title = st.text_input(
                "Section Title",
                value=default_title,
                key="hv_new_title",
            )
        with ac3:
            st.write("")  # spacer
            if st.button("Add Section", key="hv_addsec"):
                if new_theme:
                    add_section(new_theme, new_title or _theme_title(new_theme))
                    st.rerun()
    else:
        st.caption("All available themes have sections.")


def _show_chart_thumbnail(chart_ref: str):
    """Show a small thumbnail for a chart reference."""
    if chart_ref.startswith("chrt_"):
        from modules.config.news_catalog import get_chart_image
        chart_data = get_chart_image(chart_ref)
        if chart_data:
            img_path = chart_data.get("image_path", "")
            if img_path and Path(img_path).exists():
                st.image(img_path, width=60)
                return
    st.caption(f"`{chart_ref[:12]}`")
