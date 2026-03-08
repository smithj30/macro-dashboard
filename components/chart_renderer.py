"""
Chart Renderer — renders a chart from a chart catalog config dict.

Encapsulates the logic for loading data, applying transforms, and
rendering charts from JSON chart definitions. Applies the Kennedy Lewis
brand style template to every figure.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from modules.visualization.charts import (
    time_series_chart,
    correlation_heatmap,
    apply_clip_arrows,
    apply_recession_shading,
)

# ---------------------------------------------------------------------------
# Style template loading
# ---------------------------------------------------------------------------

_STYLES_PATH = Path(__file__).parent.parent / "config" / "chart_styles.json"
_style_cache: Optional[Dict[str, Any]] = None


def _load_styles() -> Dict[str, Any]:
    """Load chart styles from config/chart_styles.json (cached in-process)."""
    global _style_cache
    if _style_cache is not None:
        return _style_cache
    if _STYLES_PATH.exists():
        with open(_STYLES_PATH, "r", encoding="utf-8") as f:
            _style_cache = json.load(f)
    else:
        _style_cache = {}
    return _style_cache


def get_style_template() -> Optional[go.layout.Template]:
    """Build a Plotly Template object from the chart_styles.json config."""
    styles = _load_styles()
    tmpl_dict = styles.get("plotly_template")
    if not tmpl_dict:
        return None

    template = go.layout.Template()
    layout_dict = tmpl_dict.get("layout", {})
    template.layout = go.Layout(**layout_dict)

    # Set default scatter line width from data section
    data_dict = tmpl_dict.get("data", {})
    scatter_defaults = data_dict.get("scatter", [{}])
    if scatter_defaults:
        line_cfg = scatter_defaults[0].get("line", {})
        if line_cfg:
            template.data.scatter = [go.Scatter(line=line_cfg)]

    return template


def get_brand_colorway() -> list:
    """Return the brand color sequence."""
    styles = _load_styles()
    tmpl = styles.get("plotly_template", {})
    layout = tmpl.get("layout", {})
    return layout.get("colorway", [])


def get_recession_shading_color() -> str:
    """Return the brand recession shading color."""
    styles = _load_styles()
    return styles.get("recession_shading_color", "rgba(200, 200, 200, 0.25)")


def get_range_slider_config() -> Dict[str, Any]:
    """Return range slider style config."""
    styles = _load_styles()
    return styles.get("range_slider", {
        "thickness": 0.04,
        "bgcolor": "#f0f0f0",
        "bordercolor": "#cccccc",
        "borderwidth": 1,
    })


def apply_style(fig: go.Figure) -> go.Figure:
    """Apply the KL brand style template to a Plotly figure."""
    template = get_style_template()
    if template is not None:
        fig.update_layout(template=template)
    return fig


def apply_range_slider(fig: go.Figure, visible: bool = True) -> go.Figure:
    """Apply a thin range slider (no mini-chart) to the x-axis."""
    if not visible:
        fig.update_layout(xaxis=dict(rangeslider=dict(visible=False)))
        return fig

    rs_cfg = get_range_slider_config()
    fig.update_layout(
        xaxis=dict(
            rangeslider=dict(
                visible=True,
                thickness=rs_cfg.get("thickness", 0.04),
                bgcolor=rs_cfg.get("bgcolor", "#f0f0f0"),
                bordercolor=rs_cfg.get("bordercolor", "#cccccc"),
                borderwidth=rs_cfg.get("borderwidth", 1),
            ),
            rangeselector=None,
        )
    )
    return fig


# ---------------------------------------------------------------------------
# Main render function (chart catalog items — legacy format)
# ---------------------------------------------------------------------------


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

    # Apply brand style
    fig = apply_style(fig)

    # Apply range slider
    show_slider = chart_config.get("show_range_slider", True)
    fig = apply_range_slider(fig, visible=show_slider)

    # Apply clip arrows if y-axis bounds are set
    y_min_val = y_axis.get("min") if isinstance(y_axis, dict) else None
    y_max_val = y_axis.get("max") if isinstance(y_axis, dict) else None
    if y_min_val is not None or y_max_val is not None:
        fig = apply_clip_arrows(fig, y_min_val, y_max_val)

    if show_recession:
        recession_color = get_recession_shading_color()
        fig = apply_recession_shading(fig, color=recession_color)

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_chart")


# ---------------------------------------------------------------------------
# Render function for new v2 chart configs (catalogs/charts.json)
# ---------------------------------------------------------------------------


def render_v2_chart(
    chart_config: Dict[str, Any],
    data: Optional[Dict[str, pd.DataFrame]] = None,
    key_prefix: str = "",
    container: Any = None,
) -> Optional[go.Figure]:
    """
    Render a chart from the new v2 chart schema (catalogs/charts.json).

    Parameters
    ----------
    chart_config : chart dict with chart_id, name, chart_type, feeds[], options{}
    data         : pre-loaded data keyed by feed label
    key_prefix   : prefix for Streamlit widget keys
    container    : optional Streamlit container (st or column) to render into

    Returns the figure for further use, or None if no data.
    """
    out = container or st
    chart_type = chart_config.get("chart_type", "time_series")
    options = chart_config.get("options", {})
    title = options.get("title", chart_config.get("name", "Chart"))

    if data is None or not data:
        out.warning(f"No data available for chart: {title}")
        return None

    if chart_type == "metric_card":
        # Metric cards are rendered differently
        _render_metric_card(chart_config, data, key_prefix, out)
        return None

    if chart_type == "heatmap":
        return _render_heatmap(chart_config, data, key_prefix, out)

    # Time series / bar / table — merge data and build figure
    dfs = []
    for label, df in data.items():
        if isinstance(df, pd.Series):
            df = df.to_frame(name=label)
        dfs.append(df)

    if not dfs:
        out.warning(f"No data loaded for chart: {title}")
        return None

    merged = dfs[0]
    for df in dfs[1:]:
        merged = merged.join(df, how="outer")

    # Build series type and axis mappings from feeds config
    series_types = {}
    dual_axis_col = None
    feeds_cfg = chart_config.get("feeds", [])
    for fcfg in feeds_cfg:
        label = fcfg.get("label", "")
        if chart_type == "bar":
            series_types[label] = "bar"
        else:
            series_types[label] = "line"
        axis = fcfg.get("axis", "left")
        if axis == "right" and dual_axis_col is None:
            dual_axis_col = label

    height = options.get("height", 450)

    fig = time_series_chart(
        merged,
        title=title,
        dual_axis_col=dual_axis_col,
        height=height,
        series_types=series_types,
        show_legend=options.get("show_legend", True),
    )

    # Apply brand colors per feed if specified
    colorway = get_brand_colorway()
    for i, fcfg in enumerate(feeds_cfg):
        color = fcfg.get("color")
        if color and i < len(fig.data):
            fig.data[i].line.color = color
            if hasattr(fig.data[i], "marker"):
                fig.data[i].marker.color = color

    # Apply brand style
    fig = apply_style(fig)

    # Range slider
    show_slider = options.get("show_range_slider", True)
    fig = apply_range_slider(fig, visible=show_slider)

    # Recession shading
    if options.get("recession_shading", False):
        recession_color = get_recession_shading_color()
        fig = apply_recession_shading(fig, color=recession_color)

    out.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_v2chart")
    return fig


def _render_metric_card(
    chart_config: Dict[str, Any],
    data: Dict[str, pd.DataFrame],
    key_prefix: str,
    out: Any,
) -> None:
    """Render a metric card for a single-feed chart."""
    styles = _load_styles()
    card_styles = styles.get("metric_card_styles", {})
    options = chart_config.get("options", {})
    title = options.get("title", chart_config.get("name", "Metric"))

    # Get the first (and typically only) data series
    label = list(data.keys())[0]
    df = data[label]
    if isinstance(df, pd.Series):
        df = df.to_frame(name=label)

    if df.empty:
        out.metric(label=title, value="N/A")
        return

    col = df.columns[0]
    latest = df[col].dropna().iloc[-1]
    prev = df[col].dropna().iloc[-2] if len(df[col].dropna()) >= 2 else None
    delta = latest - prev if prev is not None else None
    delta_str = f"{delta:+,.2f}" if delta is not None else None

    out.metric(label=title, value=f"{latest:,.2f}", delta=delta_str)


def _render_heatmap(
    chart_config: Dict[str, Any],
    data: Dict[str, pd.DataFrame],
    key_prefix: str,
    out: Any,
) -> Optional[go.Figure]:
    """Render a correlation heatmap from multiple feeds."""
    options = chart_config.get("options", {})
    title = options.get("title", chart_config.get("name", "Correlation"))

    # Merge all series into a single DataFrame for correlation
    dfs = []
    for label, df in data.items():
        if isinstance(df, pd.Series):
            df = df.to_frame(name=label)
        dfs.append(df)

    if not dfs:
        out.warning(f"No data for heatmap: {title}")
        return None

    merged = dfs[0]
    for df in dfs[1:]:
        merged = merged.join(df, how="outer")

    corr = merged.corr()
    fig = correlation_heatmap(corr, title=title)
    fig = apply_style(fig)
    out.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_heatmap")
    return fig
