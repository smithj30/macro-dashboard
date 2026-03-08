"""
Tag Picker — reusable Streamlit widget for selecting tags from the controlled vocabulary.

Shows only tags that exist in config/tags.json. Includes an inline
"Create new tag" option so users don't have to leave their current view.
"""

from __future__ import annotations

from typing import List, Optional

import streamlit as st

from modules.config.tag_catalog import list_tags, create_tag, tag_names


def tag_picker(
    label: str = "Tags",
    selected: Optional[List[str]] = None,
    key: str = "tag_picker",
    help_text: str = "Select from the controlled tag vocabulary",
    allow_create: bool = True,
) -> List[str]:
    """
    Multi-select tag picker that only shows tags from the controlled vocabulary.

    Parameters
    ----------
    label       : widget label
    selected    : pre-selected tag names
    key         : Streamlit widget key
    help_text   : help tooltip text
    allow_create : show inline "Create new tag" option

    Returns
    -------
    List of selected tag names.
    """
    all_tags = list_tags()
    tag_options = [t["name"] for t in all_tags]

    # Ensure selected values are valid
    if selected:
        selected = [s for s in selected if s in tag_options]
    else:
        selected = []

    chosen = st.multiselect(
        label,
        options=tag_options,
        default=selected,
        key=key,
        help=help_text,
    )

    # Inline create new tag
    if allow_create:
        with st.expander("Create new tag", expanded=False):
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                new_name = st.text_input(
                    "Tag name",
                    key=f"{key}_new_name",
                    placeholder="e.g. energy",
                )
            with col2:
                new_color = st.color_picker(
                    "Color",
                    value="#888888",
                    key=f"{key}_new_color",
                )
            with col3:
                st.write("")  # spacer
                if st.button("Add", key=f"{key}_create_btn"):
                    if new_name and new_name.strip():
                        try:
                            create_tag(new_name.strip(), new_color)
                            st.success(f"Tag '{new_name.strip().lower().replace(' ', '-')}' created!")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))

    return chosen


def tag_display(tags: List[str], key_prefix: str = "td") -> None:
    """
    Display tags as colored pills/badges.

    Parameters
    ----------
    tags       : list of tag names to display
    key_prefix : unique prefix for rendering
    """
    if not tags:
        return

    all_tags = {t["name"]: t.get("color", "#888888") for t in list_tags()}

    pills_html = " ".join(
        f'<span style="background-color: {all_tags.get(t, "#888888")}22; '
        f'color: {all_tags.get(t, "#888888")}; '
        f'border: 1px solid {all_tags.get(t, "#888888")}44; '
        f'padding: 2px 8px; border-radius: 12px; font-size: 0.8em; '
        f'margin-right: 4px;">{t}</span>'
        for t in tags
    )

    st.markdown(pills_html, unsafe_allow_html=True)
