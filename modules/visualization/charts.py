"""
Plotly chart builders for the macro dashboard.
All charts return go.Figure instances ready for st.plotly_chart().
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

COLORS = px.colors.qualitative.Plotly


def _get_color(i: int) -> str:
    return COLORS[i % len(COLORS)]


# ---------------------------------------------------------------------------
# Time Series
# ---------------------------------------------------------------------------

def time_series_chart(
    df: pd.DataFrame,
    title: str = "Time Series",
    dual_axis_col: str = None,
    height: int = 500,
) -> go.Figure:
    """
    Interactive multi-series time series chart.

    Parameters
    ----------
    df            : DataFrame with DatetimeIndex, one column per series
    title         : chart title
    dual_axis_col : if provided, this column is plotted on a secondary y-axis
    height        : figure height in pixels
    """
    cols = list(df.columns)

    has_dual = dual_axis_col and dual_axis_col in cols
    fig = make_subplots(specs=[[{"secondary_y": has_dual}]])

    for i, col in enumerate(cols):
        series = df[col].dropna()
        is_secondary = has_dual and col == dual_axis_col
        fig.add_trace(
            go.Scatter(
                x=series.index,
                y=series.values,
                name=col,
                mode="lines",
                line=dict(color=_get_color(i), width=2),
                hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.4f}<extra>" + col + "</extra>",
            ),
            secondary_y=is_secondary,
        )

    fig.update_layout(
        title=title,
        height=height,
        hovermode="x unified",
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
