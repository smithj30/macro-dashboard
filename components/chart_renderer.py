"""
Chart Renderer — renders a chart from a chart catalog config dict.

Encapsulates the logic for loading data, applying transforms, and
rendering charts from JSON chart definitions.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from modules.visualization.charts import (
    time_series_chart,
    correlation_heatmap,
    apply_clip_arrows,
    apply_recession_shading,
)


def render_chart(
    chart_config: Dict[str, Any],
    data: Optional[Dict[str, pd.DataFrame]] = None,
    show_recession: bool = False,
    key_prefix: str = "",
) -> None:
    """
    Render a chart from a chart catalog config.

    Parameters
    ----------
    chart_config : chart item dict from chart_catalogs/ JSON
    data         : pre-loaded data keyed by series label
    show_recession : whether to show recession shading
    key_prefix   : prefix for Streamlit widget keys
    """
    chart_subtype = chart_config.get("chart_subtype", "Time Series")
    title = chart_config.get("title", "Chart")

    if data is None or not data:
        st.warning(f"No data available for chart: {title}")
        return

    # Merge all data series into one DataFrame
    dfs = []
    for label, df in data.items():
        if isinstance(df, pd.Series):
            df = df.to_frame(name=label)
        dfs.append(df)

    if not dfs:
        st.warning(f"No data loaded for chart: {title}")
        return

    merged = dfs[0]
    for df in dfs[1:]:
        merged = merged.join(df, how="outer")

    # Determine chart type mappings
    series_types = {}
    dual_axis_col = None
    for s in chart_config.get("series", []):
        label = s.get("label", "")
        stype = s.get("chart_type", "line")
        series_types[label] = stype
        axis = s.get("axis", 1)
        if axis == 2 and dual_axis_col is None:
            dual_axis_col = label

    y_axis = chart_config.get("y_axis", {})
    y_axis2 = chart_config.get("y_axis2", {})

    fig = time_series_chart(
        merged,
        title=title,
        dual_axis_col=dual_axis_col,
        y_min=y_axis.get("min") if isinstance(y_axis, dict) else None,
        y_max=y_axis.get("max") if isinstance(y_axis, dict) else None,
        y_min2=y_axis2.get("min") if isinstance(y_axis2, dict) else None,
        y_max2=y_axis2.get("max") if isinstance(y_axis2, dict) else None,
        series_types=series_types,
        show_legend=chart_config.get("show_legend", True),
    )

    # Apply clip arrows if y-axis bounds are set
    y_min_val = y_axis.get("min") if isinstance(y_axis, dict) else None
    y_max_val = y_axis.get("max") if isinstance(y_axis, dict) else None
    if y_min_val is not None or y_max_val is not None:
        fig = apply_clip_arrows(fig, y_min_val, y_max_val)

    if show_recession:
        fig = apply_recession_shading(fig)

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_chart")
