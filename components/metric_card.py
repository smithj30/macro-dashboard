"""
Metric Card component — renders a styled metric card with optional
prior/next release dates.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st


def metric_card(
    title: str,
    value: str,
    delta: Optional[str] = None,
    delta_color: str = "normal",
    prefix: str = "",
    suffix: str = "",
    prior_release: Optional[str] = None,
    next_release: Optional[str] = None,
):
    """
    Render a metric card using st.metric with optional release date annotations.

    Parameters
    ----------
    title       : Card title
    value       : Formatted value string
    delta       : Change from previous period
    delta_color : 'normal', 'inverse', or 'off'
    prefix      : Value prefix (e.g. '$')
    suffix      : Value suffix (e.g. '%')
    prior_release : Prior release date string
    next_release  : Next release date string
    """
    display_value = f"{prefix}{value}{suffix}"
    st.metric(label=title, value=display_value, delta=delta, delta_color=delta_color)

    if prior_release or next_release:
        parts = []
        if prior_release:
            parts.append(f"Prior: {prior_release}")
        if next_release:
            parts.append(f"Next: {next_release}")
        st.caption(" | ".join(parts))
