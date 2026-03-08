"""
Tag Manager — full CRUD UI for managing the controlled tag vocabulary.

Provides create, rename, merge, delete, and color editing for tags,
with usage counts and cascade warnings.
"""

from __future__ import annotations

import streamlit as st

from modules.config.tag_catalog import (
    list_tags,
    create_tag,
    rename_tag,
    merge_tags,
    delete_tag,
    update_tag_color,
    get_tag_usage,
)


def render_tag_manager() -> None:
    """Render the Tag Manager view."""
    st.header("Tag Manager")
    st.caption("Manage the controlled tag vocabulary. Tags created here can be applied to feeds and charts.")

    # --- Create new tag ---
    with st.expander("Create New Tag", expanded=False):
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            new_name = st.text_input("Tag name", key="tm_new_name", placeholder="e.g. energy")
        with col2:
            new_color = st.color_picker("Color", value="#888888", key="tm_new_color")
        with col3:
            st.write("")
            if st.button("Create Tag", key="tm_create_btn"):
                if new_name and new_name.strip():
                    try:
                        tag = create_tag(new_name.strip(), new_color)
                        st.success(f"Created tag: {tag['name']}")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
                else:
                    st.warning("Please enter a tag name")

    st.divider()

    # --- Tag list ---
    tags = list_tags()

    if not tags:
        st.info("No tags defined yet. Create your first tag above.")
        return

    st.subheader(f"All Tags ({len(tags)})")

    for tag in tags:
        name = tag["name"]
        color = tag.get("color", "#888888")
        usage = get_tag_usage(name)

        with st.container():
            col_color, col_name, col_usage, col_actions = st.columns([0.5, 3, 2, 3])

            with col_color:
                st.markdown(
                    f'<div style="width:24px;height:24px;border-radius:50%;'
                    f'background-color:{color};margin-top:8px;"></div>',
                    unsafe_allow_html=True,
                )

            with col_name:
                st.markdown(f"**{name}**")

            with col_usage:
                parts = []
                if usage["feeds"] > 0:
                    parts.append(f"{usage['feeds']} feed{'s' if usage['feeds'] != 1 else ''}")
                if usage["charts"] > 0:
                    parts.append(f"{usage['charts']} chart{'s' if usage['charts'] != 1 else ''}")
                usage_text = ", ".join(parts) if parts else "unused"
                st.caption(usage_text)

            with col_actions:
                btn_cols = st.columns(3)
                with btn_cols[0]:
                    if st.button("Edit", key=f"tm_edit_{name}", use_container_width=True):
                        st.session_state[f"tm_editing_{name}"] = True
                with btn_cols[1]:
                    if st.button("Merge", key=f"tm_merge_{name}", use_container_width=True):
                        st.session_state[f"tm_merging_{name}"] = True
                with btn_cols[2]:
                    if st.button("Delete", key=f"tm_del_{name}", use_container_width=True):
                        st.session_state[f"tm_confirm_del_{name}"] = True

            # --- Edit panel ---
            if st.session_state.get(f"tm_editing_{name}"):
                with st.container():
                    e_col1, e_col2, e_col3, e_col4 = st.columns([3, 1, 1, 1])
                    with e_col1:
                        new_tag_name = st.text_input(
                            "Rename", value=name, key=f"tm_rename_{name}"
                        )
                    with e_col2:
                        new_tag_color = st.color_picker(
                            "Color", value=color, key=f"tm_color_{name}"
                        )
                    with e_col3:
                        st.write("")
                        if st.button("Save", key=f"tm_save_{name}"):
                            changed = False
                            if new_tag_name.strip() and new_tag_name.strip() != name:
                                try:
                                    rename_tag(name, new_tag_name.strip())
                                    changed = True
                                except ValueError as e:
                                    st.error(str(e))
                            if new_tag_color != color:
                                update_tag_color(
                                    new_tag_name.strip() if changed else name,
                                    new_tag_color,
                                )
                                changed = True
                            if changed:
                                st.success("Tag updated!")
                                st.session_state.pop(f"tm_editing_{name}", None)
                                st.rerun()
                    with e_col4:
                        st.write("")
                        if st.button("Cancel", key=f"tm_cancel_edit_{name}"):
                            st.session_state.pop(f"tm_editing_{name}", None)
                            st.rerun()

            # --- Merge panel ---
            if st.session_state.get(f"tm_merging_{name}"):
                other_tags = [t["name"] for t in tags if t["name"] != name]
                if not other_tags:
                    st.warning("No other tags to merge into.")
                else:
                    m_col1, m_col2, m_col3 = st.columns([3, 1, 1])
                    with m_col1:
                        target = st.selectbox(
                            f"Merge '{name}' into:",
                            options=other_tags,
                            key=f"tm_merge_target_{name}",
                        )
                    with m_col2:
                        st.write("")
                        if st.button("Confirm Merge", key=f"tm_merge_confirm_{name}"):
                            if merge_tags(name, target):
                                st.success(f"Merged '{name}' into '{target}'")
                                st.session_state.pop(f"tm_merging_{name}", None)
                                st.rerun()
                    with m_col3:
                        st.write("")
                        if st.button("Cancel", key=f"tm_cancel_merge_{name}"):
                            st.session_state.pop(f"tm_merging_{name}", None)
                            st.rerun()

            # --- Delete confirmation ---
            if st.session_state.get(f"tm_confirm_del_{name}"):
                if usage["total"] > 0:
                    st.warning(
                        f"This tag is used by {usage['total']} item(s). "
                        f"Deleting it will remove the tag from all feeds and charts."
                    )
                d_col1, d_col2 = st.columns(2)
                with d_col1:
                    if st.button(
                        f"Confirm delete '{name}'",
                        key=f"tm_confirm_del_btn_{name}",
                        type="primary",
                    ):
                        delete_tag(name)
                        st.success(f"Deleted tag: {name}")
                        st.session_state.pop(f"tm_confirm_del_{name}", None)
                        st.rerun()
                with d_col2:
                    if st.button("Cancel", key=f"tm_cancel_del_{name}"):
                        st.session_state.pop(f"tm_confirm_del_{name}", None)
                        st.rerun()

        st.divider()
