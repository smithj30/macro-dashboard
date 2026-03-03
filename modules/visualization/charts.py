"""
Plotly chart builders for the macro dashboard.
All charts return go.Figure instances ready for st.plotly_chart().
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

COLORS = px.colors.qualitative.Plotly


def _get_color(i: int) -> str:
    return COLORS[i % len(COLORS)]


# ---------------------------------------------------------------------------
# NBER Recession Dates (peak → trough)
# Source: https://www.nber.org/research/data/us-business-cycle-expansions-and-contractions
# ---------------------------------------------------------------------------

NBER_RECESSIONS = [
    ("1948-11-01", "1949-10-01"),
    ("1953-07-01", "1954-05-01"),
    ("1957-08-01", "1958-04-01"),
    ("1960-04-01", "1961-02-01"),
    ("1969-12-01", "1970-11-01"),
    ("1973-11-01", "1975-03-01"),
    ("1980-01-01", "1980-07-01"),
    ("1981-07-01", "1982-11-01"),
    ("1990-07-01", "1991-03-01"),
    ("2001-03-01", "2001-11-01"),
    ("2007-12-01", "2009-06-01"),
    ("2020-02-01", "2020-04-01"),
]


def apply_recession_shading(
    fig: go.Figure,
    color: str = "rgba(200, 200, 200, 0.25)",
) -> go.Figure:
    """
    Add NBER recession shading bands to a Plotly figure.

    Only draws bands that overlap with the figure's x-axis date range.
    """
    # Determine the x-axis range from the traces
    all_dates = []
    for trace in fig.data:
        if trace.x is not None:
            try:
                dates = pd.to_datetime(list(trace.x))
                all_dates.extend([dates.min(), dates.max()])
            except Exception:
                continue

    if not all_dates:
        return fig

    x_min = min(all_dates)
    x_max = max(all_dates)

    for start, end in NBER_RECESSIONS:
        rec_start = pd.Timestamp(start)
        rec_end = pd.Timestamp(end)
        # Only add if recession overlaps with chart date range
        if rec_end < x_min or rec_start > x_max:
            continue
        fig.add_vrect(
            x0=rec_start,
            x1=rec_end,
            fillcolor=color,
            layer="below",
            line_width=0,
        )

    return fig


# ---------------------------------------------------------------------------
# Time Series
# ---------------------------------------------------------------------------

def time_series_chart(
    df: pd.DataFrame,
    title: str = "Time Series",
    dual_axis_col: Optional[str] = None,
    height: int = 500,
    y_min: Optional[float] = None,
    y_max: Optional[float] = None,
    y_min2: Optional[float] = None,
    y_max2: Optional[float] = None,
    chart_type: str = "line",
    series_types: Optional[Dict[str, str]] = None,
    show_legend: bool = True,
) -> go.Figure:
    """
    Interactive multi-series time series chart.

    Parameters
    ----------
    df            : DataFrame with DatetimeIndex, one column per series
    title         : chart title
    dual_axis_col : if provided, this column is plotted on a secondary y-axis
    height        : figure height in pixels
    y_min / y_max : primary y-axis range limits (None = auto)
    y_min2 / y_max2 : secondary y-axis range limits (None = auto)
    chart_type    : default chart type "line" | "bar" | "area"
    series_types  : per-series type overrides {col_name: type}; falls back to chart_type
    show_legend   : whether to display the legend
    """
    cols = list(df.columns)

    has_dual = bool(dual_axis_col and dual_axis_col in cols)
    fig = make_subplots(specs=[[{"secondary_y": has_dual}]])

    for i, col in enumerate(cols):
        series = df[col].dropna()
        is_secondary = has_dual and col == dual_axis_col
        color = _get_color(i)

        stype = (series_types or {}).get(col, chart_type)

        if stype == "bar":
            trace = go.Bar(
                x=series.index,
                y=series.values,
                name=col,
                marker_color=color,
                hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.4f}<extra>" + col + "</extra>",
            )
        elif stype == "area":
            trace = go.Scatter(
                x=series.index,
                y=series.values,
                name=col,
                mode="lines",
                fill="tozeroy",
                fillcolor=color.replace("rgb", "rgba").replace(")", ", 0.15)") if color.startswith("rgb") else color,
                line=dict(color=color, width=2),
                hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.4f}<extra>" + col + "</extra>",
            )
        else:  # "line" (default)
            trace = go.Scatter(
                x=series.index,
                y=series.values,
                name=col,
                mode="lines",
                line=dict(color=color, width=2),
                hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.4f}<extra>" + col + "</extra>",
            )

        fig.add_trace(trace, secondary_y=is_secondary)

    fig.update_layout(
        title=title,
        height=height,
        hovermode="x unified",
        showlegend=show_legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(
            rangeslider=dict(visible=True),
            type="date",
        ),
        template="plotly_white",
        margin=dict(l=60, r=60, t=60, b=40),
    )

    if has_dual:
        primary_cols = [c for c in cols if c != dual_axis_col]
        fig.update_yaxes(title_text=" / ".join(primary_cols), secondary_y=False)
        fig.update_yaxes(title_text=dual_axis_col, secondary_y=True)

    # Apply axis range constraints
    primary_range = [y_min, y_max] if (y_min is not None or y_max is not None) else None
    if primary_range is not None:
        if has_dual:
            fig.update_yaxes(range=primary_range, secondary_y=False)
        else:
            fig.update_layout(yaxis=dict(range=primary_range))

    if has_dual:
        secondary_range = [y_min2, y_max2] if (y_min2 is not None or y_max2 is not None) else None
        if secondary_range is not None:
            fig.update_yaxes(range=secondary_range, secondary_y=True)

    return fig


def apply_clip_arrows(
    fig: go.Figure,
    y_min: Optional[float],
    y_max: Optional[float],
    trace_indices: Optional[List[int]] = None,
) -> go.Figure:
    """
    Add triangle-marker traces to indicate where data extends beyond visible axis range.

    Parameters
    ----------
    fig           : existing Figure (modified in-place and returned)
    y_min / y_max : axis limits currently applied; None means no limit on that side
    trace_indices : which trace indices to inspect (default: all Scatter traces)
    """
    if y_min is None and y_max is None:
        return fig

    traces = fig.data
    if trace_indices is None:
        target_indices = [i for i, t in enumerate(traces) if isinstance(t, go.Scatter)]
    else:
        target_indices = trace_indices

    for idx in target_indices:
        trace = traces[idx]
        if not isinstance(trace, go.Scatter):
            continue

        xs = list(trace.x) if trace.x is not None else []
        ys = list(trace.y) if trace.y is not None else []
        if not xs or not ys:
            continue

        color = (
            trace.line.color
            if trace.line and trace.line.color
            else _get_color(idx)
        )

        above_x, below_x = [], []
        for x_val, y_val in zip(xs, ys):
            if y_val is None:
                continue
            try:
                y_float = float(y_val)
            except (TypeError, ValueError):
                continue
            if y_max is not None and y_float > y_max:
                above_x.append(x_val)
            if y_min is not None and y_float < y_min:
                below_x.append(x_val)

        if above_x:
            fig.add_trace(
                go.Scatter(
                    x=above_x,
                    y=[y_max] * len(above_x),
                    mode="markers",
                    marker=dict(symbol="triangle-up", size=10, color=color),
                    showlegend=False,
                    hovertemplate="Value exceeds axis max<extra></extra>",
                    name="_clip_above",
                )
            )

        if below_x:
            fig.add_trace(
                go.Scatter(
                    x=below_x,
                    y=[y_min] * len(below_x),
                    mode="markers",
                    marker=dict(symbol="triangle-down", size=10, color=color),
                    showlegend=False,
                    hovertemplate="Value below axis min<extra></extra>",
                    name="_clip_below",
                )
            )

    return fig


# ---------------------------------------------------------------------------
# Correlation Heatmap
# ---------------------------------------------------------------------------

def correlation_heatmap(corr_matrix: pd.DataFrame, title: str = "Correlation Matrix") -> go.Figure:
    """
    Annotated correlation heatmap using a diverging colour scale.
    """
    z = corr_matrix.values
    labels = list(corr_matrix.columns)

    # Build annotation text
    text = [[f"{z[i][j]:.2f}" for j in range(len(labels))] for i in range(len(labels))]

    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=labels,
            y=labels,
            text=text,
            texttemplate="%{text}",
            colorscale="RdBu",
            zmid=0,
            zmin=-1,
            zmax=1,
            colorbar=dict(title="r"),
            hoverongaps=False,
        )
    )

    fig.update_layout(
        title=title,
        template="plotly_white",
        height=max(400, len(labels) * 60 + 100),
        xaxis=dict(side="bottom"),
        margin=dict(l=80, r=40, t=60, b=80),
    )

    return fig


# ---------------------------------------------------------------------------
# Scatter Plot
# ---------------------------------------------------------------------------

def scatter_chart(
    x_series: pd.Series,
    y_series: pd.Series,
    title: str = None,
    add_trendline: bool = True,
    color_by_date: bool = True,
    height: int = 500,
) -> go.Figure:
    """
    Scatter plot comparing two series (aligned on date index).
    Optionally colours points by date and adds an OLS trendline.
    """
    combined = pd.concat([x_series, y_series], axis=1).dropna()
    x_col, y_col = combined.columns[0], combined.columns[1]

    x_vals = combined[x_col].values
    y_vals = combined[y_col].values
    dates = combined.index

    if color_by_date:
        # Map dates to a numeric scale for colour
        date_num = (dates - dates.min()).days
        scatter = go.Scatter(
            x=x_vals,
            y=y_vals,
            mode="markers",
            marker=dict(
                color=date_num,
                colorscale="Viridis",
                colorbar=dict(
                    title="Date",
                    tickvals=[date_num.min(), date_num.max()],
                    ticktext=[str(dates.min().date()), str(dates.max().date())],
                ),
                size=7,
                opacity=0.8,
            ),
            text=[str(d.date()) for d in dates],
            hovertemplate=(
                f"{x_col}: %{{x:,.4f}}<br>"
                f"{y_col}: %{{y:,.4f}}<br>"
                "Date: %{text}<extra></extra>"
            ),
            name="observations",
        )
    else:
        scatter = go.Scatter(
            x=x_vals,
            y=y_vals,
            mode="markers",
            marker=dict(size=7, opacity=0.7, color=COLORS[0]),
            text=[str(d.date()) for d in dates],
            hovertemplate=(
                f"{x_col}: %{{x:,.4f}}<br>"
                f"{y_col}: %{{y:,.4f}}<br>"
                "Date: %{text}<extra></extra>"
            ),
            name="observations",
        )

    fig = go.Figure(data=[scatter])

    if add_trendline and len(x_vals) > 2:
        # Simple OLS line
        coeffs = np.polyfit(x_vals, y_vals, 1)
        x_line = np.linspace(x_vals.min(), x_vals.max(), 200)
        y_line = np.polyval(coeffs, x_line)
        fig.add_trace(
            go.Scatter(
                x=x_line,
                y=y_line,
                mode="lines",
                line=dict(color="red", width=2, dash="dash"),
                name=f"Trend (slope={coeffs[0]:.4f})",
            )
        )

    if title is None:
        title = f"{x_col} vs {y_col}"

    fig.update_layout(
        title=title,
        xaxis_title=x_col,
        yaxis_title=y_col,
        template="plotly_white",
        height=height,
        margin=dict(l=60, r=40, t=60, b=60),
        hovermode="closest",
    )

    return fig


# ---------------------------------------------------------------------------
# Rolling Correlation Line Chart
# ---------------------------------------------------------------------------

def rolling_corr_chart(rolling_corr: pd.Series, title: str = None) -> go.Figure:
    """Plot a rolling correlation series with a zero reference line."""
    if title is None:
        title = rolling_corr.name or "Rolling Correlation"

    fig = go.Figure()

    fig.add_hline(y=0, line_dash="dot", line_color="grey", opacity=0.6)
    fig.add_hline(y=1, line_dash="dot", line_color="lightgrey", opacity=0.4)
    fig.add_hline(y=-1, line_dash="dot", line_color="lightgrey", opacity=0.4)

    fig.add_trace(
        go.Scatter(
            x=rolling_corr.index,
            y=rolling_corr.values,
            mode="lines",
            line=dict(color=COLORS[0], width=2),
            name="Rolling Corr",
            hovertemplate="%{x|%Y-%m-%d}<br>r = %{y:.4f}<extra></extra>",
        )
    )

    fig.update_layout(
        title=title,
        yaxis=dict(range=[-1.1, 1.1], title="Pearson r"),
        xaxis=dict(title="Date", type="date"),
        template="plotly_white",
        height=400,
        margin=dict(l=60, r=40, t=60, b=40),
    )

    return fig


# ---------------------------------------------------------------------------
# Residual Plot
# ---------------------------------------------------------------------------

def residual_plot(
    fitted: pd.Series,
    residuals: pd.Series,
    title: str = "Residuals vs Fitted",
) -> go.Figure:
    """Scatter of residuals vs fitted values with a zero line."""
    fig = go.Figure()

    fig.add_hline(y=0, line_dash="dash", line_color="red", opacity=0.7)

    fig.add_trace(
        go.Scatter(
            x=fitted.values,
            y=residuals.values,
            mode="markers",
            marker=dict(size=6, opacity=0.6, color=COLORS[1]),
            hovertemplate="Fitted: %{x:,.4f}<br>Residual: %{y:,.4f}<extra></extra>",
            name="residuals",
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Fitted Values",
        yaxis_title="Residuals",
        template="plotly_white",
        height=400,
        margin=dict(l=60, r=40, t=60, b=40),
    )

    return fig


def residual_histogram(residuals: pd.Series, title: str = "Residual Distribution") -> go.Figure:
    """Histogram of regression residuals."""
    fig = go.Figure(
        data=go.Histogram(
            x=residuals.values,
            nbinsx=30,
            marker_color=COLORS[2],
            opacity=0.8,
            name="residuals",
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Residual",
        yaxis_title="Count",
        template="plotly_white",
        height=350,
        margin=dict(l=60, r=40, t=60, b=40),
    )

    return fig
