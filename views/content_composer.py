"""
Content Composer — create and edit content pieces (email updates,
distributions, etc.) by selecting charts and adding commentary.
"""

from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

from modules.config.content_catalog import (
    get_content_pieces,
    get_content_piece,
    save_content_piece,
    delete_content_piece,
)
from components.content_chart_picker import content_chart_picker
from components.tag_picker import tag_picker


# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

_TYPE_OPTIONS = ["email_update", "email_distribution", "linkedin_post"]
_TYPE_LABELS = {
    "email_update": "Email Update",
    "email_distribution": "Email Distribution",
    "linkedin_post": "LinkedIn Post",
}
_STATUS_COLORS = {
    "draft": "#888",
    "ready": "#2ca02c",
    "sent": "#44ADE2",
    "archived": "#999",
}


def _init_state():
    if "cc_editing_id" not in st.session_state:
        st.session_state.cc_editing_id = None
    if "cc_show_picker" not in st.session_state:
        st.session_state.cc_show_picker = False
    if "cc_ai_loading" not in st.session_state:
        st.session_state.cc_ai_loading = False


# ---------------------------------------------------------------------------
# Email HTML rendering
# ---------------------------------------------------------------------------


def _render_email_html(piece: Dict[str, Any]) -> str:
    """Render a content piece as branded email HTML."""
    title = piece.get("title", "")
    bullets = piece.get("commentary", [])
    charts = piece.get("charts", [])

    bullet_html = ""
    for b in bullets:
        bullet_html += f"<li style='margin-bottom:6px;font-size:14px;color:#333'>{b['text']}</li>\n"

    chart_rows = ""
    for i in range(0, len(charts), 2):
        row_charts = charts[i : i + 2]
        cells = ""
        for ch in row_charts:
            img_tag = ""
            # Try to load image for news_reader charts
            if ch.get("source") == "news_reader":
                from modules.config.news_catalog import get_chart_image
                chart_data = get_chart_image(ch["chart_ref"])
                if chart_data:
                    img_path = chart_data.get("image_path", "")
                    if img_path and Path(img_path).exists():
                        with open(img_path, "rb") as f:
                            b64 = base64.b64encode(f.read()).decode()
                        img_tag = f"<img src='data:image/png;base64,{b64}' style='width:100%;max-width:280px;border-radius:4px' />"
            if not img_tag:
                img_tag = f"<div style='height:140px;background:#f0f0f0;border-radius:4px;display:flex;align-items:center;justify-content:center'><span style='color:#888'>{ch.get('chart_ref', 'Chart')}</span></div>"
            caption = ch.get("caption", "")
            cells += f"""
            <td style='width:50%;padding:8px;vertical-align:top'>
                {img_tag}
                <p style='font-size:12px;color:#666;margin:4px 0 0'>{caption}</p>
            </td>"""
        chart_rows += f"<tr>{cells}</tr>\n"

    html = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;font-family:Arial,Helvetica,sans-serif">
        <tr>
            <td style="background-color:#011E2F;padding:16px 24px">
                <span style="color:white;font-size:18px;font-weight:bold">Kennedy Lewis</span>
            </td>
        </tr>
        <tr>
            <td style="padding:24px">
                <h2 style="margin:0 0 16px;color:#011E2F;font-size:20px">{title}</h2>
                <ul style="padding-left:20px;margin:0 0 24px">
                    {bullet_html}
                </ul>
                <table width="100%" cellpadding="0" cellspacing="0">
                    {chart_rows}
                </table>
            </td>
        </tr>
        <tr>
            <td style="background-color:#f5f3f0;padding:12px 24px;border-top:1px solid #E1DBD4">
                <p style="font-size:11px;color:#888;margin:0">
                    Kennedy Lewis Investment Management | Confidential
                </p>
            </td>
        </tr>
    </table>
    """
    return html


# ---------------------------------------------------------------------------
# AI commentary generation
# ---------------------------------------------------------------------------


def _generate_commentary(charts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Send selected charts to Claude API and return bullet dicts."""
    try:
        import anthropic
    except ImportError:
        st.error("anthropic package not installed. Add it to requirements.txt.")
        return []

    # Build chart descriptions for the prompt
    chart_descriptions = []
    for i, ch in enumerate(charts, 1):
        caption = ch.get("caption", "Chart")
        chart_descriptions.append(f"Chart {i}: {caption}")

    charts_text = "\n".join(chart_descriptions)

    prompt = f"""You are a macro research analyst at Kennedy Lewis Investment Management.
Given the following charts and their captions, write 3-5 concise analytical
bullet points summarizing the key takeaways. Be specific about data points
visible in the charts. Use a professional but direct tone.

Charts:
{charts_text}

Return each bullet point on its own line, starting with a dash (-). No other formatting."""

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        lines = [l.strip().lstrip("- ").strip() for l in text.strip().split("\n") if l.strip().startswith("-") or l.strip().startswith("•")]
        if not lines:
            lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
        return [
            {"text": line, "ai_generated": True, "edited": False}
            for line in lines[:5]
        ]
    except Exception as e:
        st.error(f"AI generation failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------


def render():
    _init_state()
    st.title("Content Composer")

    editing_id = st.session_state.cc_editing_id

    # ── Top section: Draft management ─────────────────────────────────────
    top_col1, top_col2 = st.columns([1, 3])

    with top_col1:
        st.markdown("**New Content**")
        new_type = st.selectbox(
            "Type", _TYPE_OPTIONS,
            format_func=lambda t: _TYPE_LABELS.get(t, t),
            key="cc_new_type",
        )
        if st.button("Create New", use_container_width=True, key="cc_create"):
            piece_id = save_content_piece({
                "title": f"New {_TYPE_LABELS.get(new_type, new_type)}",
                "type": new_type,
            })
            st.session_state.cc_editing_id = piece_id
            st.session_state.cc_show_picker = False
            # Clear chart picker selections
            if "ccp_selections" in st.session_state:
                del st.session_state["ccp_selections"]
            st.rerun()

    with top_col2:
        drafts = get_content_pieces()
        if drafts:
            st.markdown("**Drafts**")
            for d in drafts[:10]:
                c1, c2, c3, c4, c5, c6 = st.columns([3, 1, 1, 1, 1, 1])
                with c1:
                    title = d.get("title", "Untitled")[:40]
                    if editing_id == d["id"]:
                        st.markdown(f"**\u2192 {title}**")
                    else:
                        st.markdown(title)
                with c2:
                    t = d.get("type", "")
                    st.caption(_TYPE_LABELS.get(t, t))
                with c3:
                    updated = d.get("updated_at", "")[:10]
                    st.caption(updated)
                with c4:
                    n_charts = len(d.get("charts", []))
                    st.caption(f"{n_charts} charts")
                with c5:
                    status = d.get("status", "draft")
                    color = _STATUS_COLORS.get(status, "#888")
                    st.markdown(
                        f"<span style='color:{color};font-size:0.8rem'>{status}</span>",
                        unsafe_allow_html=True,
                    )
                with c6:
                    if st.button("Edit", key=f"cc_edit_{d['id']}"):
                        st.session_state.cc_editing_id = d["id"]
                        st.session_state.cc_show_picker = False
                        if "ccp_selections" in st.session_state:
                            del st.session_state["ccp_selections"]
                        st.rerun()
        else:
            st.info("No drafts yet. Create a new content piece to get started.")

    # ── Main editor ───────────────────────────────────────────────────────
    if not editing_id:
        return

    piece = get_content_piece(editing_id)
    if not piece:
        st.error("Content piece not found.")
        st.session_state.cc_editing_id = None
        return

    st.markdown("---")

    # Title + tags
    title = st.text_input("Title", value=piece.get("title", ""), key="cc_title")
    tags = tag_picker(
        label="Tags",
        selected=piece.get("tags", []),
        key="cc_tags",
        allow_create=False,
    )

    # ── Chart picker toggle ───────────────────────────────────────────────
    if st.session_state.cc_show_picker:
        st.markdown("### Select Charts")
        # Initialize picker with existing charts
        if "ccp_selections" not in st.session_state:
            st.session_state["ccp_selections"] = list(piece.get("charts", []))
        selections = content_chart_picker(
            key_prefix="ccp",
            pre_selected=piece.get("charts", []),
        )
        if st.button("Done Selecting", key="cc_done_pick", use_container_width=True):
            st.session_state.cc_show_picker = False
            # Save selections to piece
            piece["charts"] = selections
            piece["title"] = title
            piece["tags"] = tags
            save_content_piece(piece)
            st.rerun()
        return  # Don't show editor while picker is open

    # ── Two-column layout: charts left, commentary right ──────────────────
    left_col, right_col = st.columns([3, 2])

    with left_col:
        st.markdown("### Charts")
        charts = piece.get("charts", [])

        if st.button("Add Charts", key="cc_add_charts", use_container_width=True):
            st.session_state.cc_show_picker = True
            st.rerun()

        if not charts:
            st.info("No charts selected. Click 'Add Charts' to start.")
        else:
            # Display charts in 2-column grid with editable captions
            for i in range(0, len(charts), 2):
                row = charts[i : i + 2]
                cols = st.columns(2)
                for j, ch in enumerate(row):
                    with cols[j]:
                        idx = i + j
                        _render_chart_card(ch, idx, key_prefix="cc")
                        # Reorder + remove buttons
                        rc1, rc2, rc3 = st.columns(3)
                        with rc1:
                            if idx > 0 and st.button("\u2191", key=f"cc_chup_{idx}"):
                                charts[idx], charts[idx - 1] = charts[idx - 1], charts[idx]
                                for ci, c in enumerate(charts):
                                    c["position"] = ci + 1
                                piece["charts"] = charts
                                save_content_piece(piece)
                                st.rerun()
                        with rc2:
                            if idx < len(charts) - 1 and st.button("\u2193", key=f"cc_chdn_{idx}"):
                                charts[idx], charts[idx + 1] = charts[idx + 1], charts[idx]
                                for ci, c in enumerate(charts):
                                    c["position"] = ci + 1
                                piece["charts"] = charts
                                save_content_piece(piece)
                                st.rerun()
                        with rc3:
                            if st.button("X", key=f"cc_chrm_{idx}"):
                                charts.pop(idx)
                                for ci, c in enumerate(charts):
                                    c["position"] = ci + 1
                                piece["charts"] = charts
                                save_content_piece(piece)
                                st.rerun()

    with right_col:
        st.markdown("### Commentary")

        # Generate button
        if st.button("Generate Draft", key="cc_gen", use_container_width=True):
            if not charts:
                st.warning("Select charts first.")
            else:
                with st.spinner("Generating commentary..."):
                    bullets = _generate_commentary(charts)
                    if bullets:
                        piece["commentary"] = bullets
                        piece["title"] = title
                        piece["tags"] = tags
                        save_content_piece(piece)
                        st.rerun()

        commentary = piece.get("commentary", [])
        updated_commentary = []
        for i, bullet in enumerate(commentary):
            bc1, bc2, bc3 = st.columns([8, 1, 1])
            with bc1:
                ai_badge = " (AI)" if bullet.get("ai_generated") and not bullet.get("edited") else ""
                new_text = st.text_area(
                    f"Bullet {i + 1}{ai_badge}",
                    value=bullet.get("text", ""),
                    key=f"cc_bullet_{i}",
                    height=68,
                )
                was_edited = new_text != bullet.get("text", "")
                updated_commentary.append({
                    "text": new_text,
                    "ai_generated": bullet.get("ai_generated", False),
                    "edited": bullet.get("edited", False) or was_edited,
                })
            with bc2:
                if i > 0 and st.button("\u2191", key=f"cc_bup_{i}"):
                    commentary[i], commentary[i - 1] = commentary[i - 1], commentary[i]
                    piece["commentary"] = commentary
                    save_content_piece(piece)
                    st.rerun()
            with bc3:
                if st.button("X", key=f"cc_bdel_{i}"):
                    commentary.pop(i)
                    piece["commentary"] = commentary
                    save_content_piece(piece)
                    st.rerun()

        if st.button("+ Add Bullet", key="cc_add_bullet"):
            commentary.append({"text": "", "ai_generated": False, "edited": False})
            piece["commentary"] = commentary
            save_content_piece(piece)
            st.rerun()

    # ── Bottom toolbar ────────────────────────────────────────────────────
    st.markdown("---")
    tb1, tb2, tb3, tb4 = st.columns(4)

    with tb1:
        if st.button("Save Draft", key="cc_save", use_container_width=True):
            piece["title"] = title
            piece["tags"] = tags
            piece["commentary"] = updated_commentary
            save_content_piece(piece)
            st.success(f"Draft saved at {datetime.now().strftime('%H:%M')}")

    with tb2:
        with st.expander("Preview"):
            preview_piece = dict(piece)
            preview_piece["title"] = title
            preview_piece["commentary"] = updated_commentary
            html = _render_email_html(preview_piece)
            st.markdown(html, unsafe_allow_html=True)

    with tb3:
        preview_piece = dict(piece)
        preview_piece["title"] = title
        preview_piece["commentary"] = updated_commentary
        html = _render_email_html(preview_piece)
        st.code(html, language="html")

    with tb4:
        if st.button("Delete Draft", key="cc_delete", type="secondary", use_container_width=True):
            st.session_state["cc_confirm_delete"] = True
            st.rerun()

    if st.session_state.get("cc_confirm_delete"):
        st.warning("Are you sure you want to delete this draft?")
        dc1, dc2, _ = st.columns([1, 1, 4])
        with dc1:
            if st.button("Yes, delete", key="cc_confirm_yes"):
                delete_content_piece(editing_id)
                st.session_state.cc_editing_id = None
                st.session_state["cc_confirm_delete"] = False
                st.rerun()
        with dc2:
            if st.button("Cancel", key="cc_confirm_no"):
                st.session_state["cc_confirm_delete"] = False
                st.rerun()


def _render_chart_card(chart: Dict[str, Any], idx: int, key_prefix: str = "cc"):
    """Render a chart card with image, caption, and position."""
    chart_ref = chart.get("chart_ref", "")
    source = chart.get("source", "")

    # Display image
    if source == "news_reader":
        from modules.config.news_catalog import get_chart_image
        chart_data = get_chart_image(chart_ref)
        if chart_data:
            img_path = chart_data.get("image_path", "")
            if img_path and Path(img_path).exists():
                st.image(img_path, use_container_width=True)
            else:
                st.markdown(
                    "<div style='height:100px;background:#E1DBD4;border-radius:4px;"
                    "display:flex;align-items:center;justify-content:center'>"
                    "<span style='color:#888'>Image unavailable</span></div>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                "<div style='height:100px;background:#E1DBD4;border-radius:4px;"
                "display:flex;align-items:center;justify-content:center'>"
                "<span style='color:#888'>Chart unavailable</span></div>",
                unsafe_allow_html=True,
            )
    else:
        # Dashboard chart — show title placeholder
        st.markdown(
            f"<div style='height:100px;background:#f5f3f0;border:1px solid #E1DBD4;"
            f"border-radius:4px;display:flex;align-items:center;justify-content:center'>"
            f"<span style='font-weight:600;font-size:0.85rem'>{chart.get('caption', chart_ref)}</span></div>",
            unsafe_allow_html=True,
        )

    # Position badge + source badge
    src_label = "News" if source == "news_reader" else "Dashboard"
    src_color = "#44ADE2" if source == "news_reader" else "#2ca02c"
    st.markdown(
        f"<span style='font-weight:600;margin-right:8px'>#{idx + 1}</span>"
        f"<span style='background:{src_color};color:white;padding:1px 6px;"
        f"border-radius:8px;font-size:0.7rem'>{src_label}</span>",
        unsafe_allow_html=True,
    )

    # Editable caption
    st.text_input(
        "Caption",
        value=chart.get("caption", ""),
        key=f"{key_prefix}_cap_{idx}",
        label_visibility="collapsed",
    )
