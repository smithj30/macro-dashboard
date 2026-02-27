"""
US Reindustrialization Dashboard view.

Covers: industrial production, manufacturing investment, regional Fed surveys,
forward indicators, employment trends, and reshoring tracker.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from modules.config.dashboard_config import load_config, save_section_override
from modules.data_ingestion.bea_loader import fetch_manufacturing_investment
from modules.data_ingestion.fred_loader import load_fred_series
from modules.visualization.charts import apply_clip_arrows
from modules.visualization.news_widget import render_news_section

# ── Static / manual data ───────────────────────────────────────────────────────

_RESHORING_JOBS = pd.DataFrame(
    [
        {"Year": "2019", "Jobs Announced": 159_000},
        {"Year": "2020", "Jobs Announced": 109_000},
        {"Year": "2021", "Jobs Announced": 265_000},
        {"Year": "2022", "Jobs Announced": 350_000},
        {"Year": "2023", "Jobs Announced": 287_000},
    ]
)

_RESHORING_TABLE = pd.DataFrame(
    [
        {"Company": "Micron", "Jobs": "9,000", "Location": "New York", "Industry": "Semiconductors"},
        {"Company": "Intel", "Jobs": "3,000", "Location": "Ohio", "Industry": "Semiconductors"},
        {"Company": "TSMC", "Jobs": "2,000", "Location": "Arizona", "Industry": "Semiconductors"},
        {"Company": "Samsung", "Jobs": "2,000", "Location": "Texas", "Industry": "Semiconductors"},
        {"Company": "GM", "Jobs": "4,000", "Location": "Michigan", "Industry": "EV Manufacturing"},
        {"Company": "Ford", "Jobs": "2,500", "Location": "Tennessee", "Industry": "EV Batteries"},
        {"Company": "Toyota", "Jobs": "2,100", "Location": "N. Carolina", "Industry": "EV Batteries"},
        {"Company": "Rivian", "Jobs": "7,500", "Location": "Georgia", "Industry": "EV Manufacturing"},
    ]
)

# ── Cached data loaders ────────────────────────────────────────────────────────


@st.cache_data(ttl=1800, show_spinner=False)
def _fred(series_id: str, years_back: int) -> pd.DataFrame:
    start = (datetime.today() - timedelta(days=years_back * 365)).strftime("%Y-%m-%d")
    return load_fred_series(series_id, start_date=start)


@st.cache_data(ttl=3600, show_spinner=False)
def _bea() -> pd.DataFrame:
    return fetch_manufacturing_investment()


# ── Metric helpers ─────────────────────────────────────────────────────────────


def _yoy(series: pd.Series) -> Optional[float]:
    """YoY % change using the value 12 observations back."""
    s = series.dropna()
    if len(s) < 13:
        return None
    return (s.iloc[-1] - s.iloc[-13]) / abs(s.iloc[-13]) * 100


def _delta_label(pct: Optional[float]) -> Optional[str]:
    if pct is None or np.isnan(pct):
        return None
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}% YoY"


# ── Shared chart layout defaults ───────────────────────────────────────────────

_BASE = dict(
    height=340,
    margin=dict(t=44, b=30, l=55, r=20),
    hovermode="x unified",
    plot_bgcolor="white",
    paper_bgcolor="white",
    font=dict(size=11),
    xaxis=dict(showgrid=False),
    yaxis=dict(gridcolor="#f0f0f0"),
)


def _nearest_y(df: pd.DataFrame, date_str: str) -> float:
    idx = pd.Timestamp(date_str)
    pos = df.index.searchsorted(idx)
    pos = min(pos, len(df) - 1)
    return float(df.iloc[pos, 0])


def _cutoff(years: int) -> pd.Timestamp:
    return pd.Timestamp(datetime.today() - timedelta(days=years * 365))


# ── Section controls helper ────────────────────────────────────────────────────


def _section_controls(
    section_id: str,
    current_overrides: Dict[str, Any],
    allowed_chart_types: List[str],
    has_secondary_y: bool = False,
) -> Dict[str, Any]:
    """
    Render a collapsible settings expander for one chart section.
    Returns the current (potentially just-saved) overrides dict.
    Calls save_section_override + st.rerun() when user clicks Save.
    """
    with st.expander("⚙ Chart Settings", expanded=False):
        current_chart_type = current_overrides.get("chart_type", allowed_chart_types[0])
        if current_chart_type not in allowed_chart_types:
            current_chart_type = allowed_chart_types[0]

        new_chart_type = st.selectbox(
            "Chart type",
            options=allowed_chart_types,
            index=allowed_chart_types.index(current_chart_type),
            key=f"ct_{section_id}",
        )

        y_axis_cfg = current_overrides.get("y_axis", {}) or {}
        y_axis2_cfg = current_overrides.get("y_axis2", {}) or {}

        col_a, col_b = st.columns(2)
        with col_a:
            enable_ymin = st.checkbox(
                "Set Y min",
                value=y_axis_cfg.get("min") is not None,
                key=f"en_ymin_{section_id}",
            )
            y_min_val = st.number_input(
                "Y min",
                value=float(y_axis_cfg["min"]) if y_axis_cfg.get("min") is not None else 0.0,
                key=f"ymin_{section_id}",
                disabled=not enable_ymin,
            )
        with col_b:
            enable_ymax = st.checkbox(
                "Set Y max",
                value=y_axis_cfg.get("max") is not None,
                key=f"en_ymax_{section_id}",
            )
            y_max_val = st.number_input(
                "Y max",
                value=float(y_axis_cfg["max"]) if y_axis_cfg.get("max") is not None else 100.0,
                key=f"ymax_{section_id}",
                disabled=not enable_ymax,
            )

        if has_secondary_y:
            col_c, col_d = st.columns(2)
            with col_c:
                enable_ymin2 = st.checkbox(
                    "Set Y2 min",
                    value=y_axis2_cfg.get("min") is not None,
                    key=f"en_ymin2_{section_id}",
                )
                y_min2_val = st.number_input(
                    "Y2 min",
                    value=float(y_axis2_cfg["min"]) if y_axis2_cfg.get("min") is not None else 0.0,
                    key=f"ymin2_{section_id}",
                    disabled=not enable_ymin2,
                )
            with col_d:
                enable_ymax2 = st.checkbox(
                    "Set Y2 max",
                    value=y_axis2_cfg.get("max") is not None,
                    key=f"en_ymax2_{section_id}",
                )
                y_max2_val = st.number_input(
                    "Y2 max",
                    value=float(y_axis2_cfg["max"]) if y_axis2_cfg.get("max") is not None else 100.0,
                    key=f"ymax2_{section_id}",
                    disabled=not enable_ymax2,
                )
        else:
            enable_ymin2 = enable_ymax2 = False
            y_min2_val = y_max2_val = 0.0

        if st.button("Save settings", key=f"save_{section_id}"):
            overrides: Dict[str, Any] = {
                "chart_type": new_chart_type,
                "y_axis": {
                    "min": float(y_min_val) if enable_ymin else None,
                    "max": float(y_max_val) if enable_ymax else None,
                },
            }
            if has_secondary_y:
                overrides["y_axis2"] = {
                    "min": float(y_min2_val) if enable_ymin2 else None,
                    "max": float(y_max2_val) if enable_ymax2 else None,
                }
            save_section_override("reindustrialization", section_id, overrides)
            st.rerun()

    return current_overrides


# ── Chart builders ─────────────────────────────────────────────────────────────


def _indpro_chart(df: pd.DataFrame, chart_type: str = "line") -> go.Figure:
    col = df.columns[0]
    color = "#1976D2"

    if chart_type == "bar":
        trace = go.Bar(
            x=df.index,
            y=df[col],
            name="INDPRO",
            marker_color=color,
            hovertemplate="%{x|%b %Y}  %{y:.1f}<extra></extra>",
        )
    elif chart_type == "area":
        trace = go.Scatter(
            x=df.index,
            y=df[col],
            mode="lines",
            fill="tozeroy",
            fillcolor="rgba(25, 118, 210, 0.12)",
            line=dict(color=color, width=2),
            name="INDPRO",
            hovertemplate="%{x|%b %Y}  %{y:.1f}<extra></extra>",
        )
    else:
        trace = go.Scatter(
            x=df.index,
            y=df[col],
            mode="lines",
            line=dict(color=color, width=2),
            name="INDPRO",
            hovertemplate="%{x|%b %Y}  %{y:.1f}<extra></extra>",
        )

    fig = go.Figure(trace)
    annotations = [
        ("2020-04-01", "COVID Drop", 40, -50),
        ("2023-01-01", "Reindustrialization Era", 0, -42),
    ]
    for date_str, label, ax, ay in annotations:
        ts = pd.Timestamp(date_str)
        if ts >= df.index.min() and ts <= df.index.max():
            fig.add_annotation(
                x=date_str,
                y=_nearest_y(df, date_str),
                text=label,
                showarrow=True,
                arrowhead=2,
                ax=ax,
                ay=ay,
                font=dict(size=9),
            )
    fig.update_layout(
        title="Industrial Production Index",
        yaxis_title="Index (2017=100)",
        **_BASE,
    )
    return fig


def _investment_chart(bea_df: pd.DataFrame, construction_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    if not bea_df.empty:
        bea_5yr = bea_df[bea_df.index >= _cutoff(5)]
        colors = ["#FF6B35", "#004E89", "#686963"]
        for i, col in enumerate(bea_5yr.columns):
            fig.add_trace(
                go.Bar(
                    x=bea_5yr.index,
                    y=bea_5yr[col],
                    name=col,
                    marker_color=colors[i % len(colors)],
                    hovertemplate=f"{col}<br>%{{x|%Y-Q%{{customdata}}}}<br>${{y:,.0f}}B<extra></extra>",
                )
            )

    if not construction_df.empty:
        mfg_const = construction_df.copy()
        if not bea_df.empty:
            mfg_const = mfg_const[mfg_const.index >= bea_df[bea_df.index >= _cutoff(5)].index.min()]
        fig.add_trace(
            go.Scatter(
                x=mfg_const.index,
                y=mfg_const.iloc[:, 0] / 1000,  # millions → billions
                mode="lines",
                name="Mfg Construction (FRED)",
                line=dict(color="#686963", width=2, dash="dot"),
                yaxis="y2",
                hovertemplate="Mfg Construction<br>%{x|%b %Y}<br>$%{y:.1f}B<extra></extra>",
            )
        )

    layout = dict(**_BASE)
    layout.update(
        title="Manufacturing Investment & Construction",
        barmode="stack",
        yaxis_title="Bil. Chained 2017$ (BEA)",
        yaxis2=dict(
            title="Bil. Nominal$ (FRED)",
            overlaying="y",
            side="right",
            showgrid=False,
        ),
        legend=dict(orientation="h", y=-0.18, x=0, font=dict(size=10)),
    )
    fig.update_layout(**layout)
    return fig


def _surveys_chart(
    philly_current: pd.DataFrame,
    philly_future: pd.DataFrame,
    ism_df: Optional[pd.DataFrame],
) -> go.Figure:
    fig = go.Figure()
    cut = _cutoff(3)

    if not philly_current.empty:
        pc = philly_current[philly_current.index >= cut]
        fig.add_trace(
            go.Scatter(
                x=pc.index,
                y=pc.iloc[:, 0],
                mode="lines",
                name="Philly Fed (Current)",
                line=dict(color="#E91E63", width=2),
                hovertemplate="%{x|%b %Y}  %{y:.1f}<extra></extra>",
            )
        )

    if not philly_future.empty:
        pf = philly_future[philly_future.index >= cut]
        fig.add_trace(
            go.Scatter(
                x=pf.index,
                y=pf.iloc[:, 0],
                mode="lines",
                name="Philly Fed (Future)",
                line=dict(color="#9C27B0", width=2, dash="dash"),
                hovertemplate="%{x|%b %Y}  %{y:.1f}<extra></extra>",
            )
        )

    if ism_df is not None and not ism_df.empty:
        ism_trim = ism_df[ism_df.index >= cut]
        fig.add_trace(
            go.Scatter(
                x=ism_trim.index,
                y=ism_trim.iloc[:, 0],
                mode="lines",
                name="ISM Mfg PMI",
                line=dict(color="#FF9800", width=2),
                hovertemplate="%{x|%b %Y}  %{y:.1f}<extra></extra>",
            )
        )

    fig.add_hline(y=0, line_color="#aaaaaa", line_width=1, line_dash="dot")
    layout = dict(**_BASE)
    layout.update(
        title="Regional Fed & Manufacturing Surveys",
        yaxis_title="Diffusion Index",
        legend=dict(orientation="h", y=-0.18, x=0, font=dict(size=10)),
    )
    fig.update_layout(**layout)
    return fig


def _forward_chart(new_orders: pd.DataFrame, philly_future: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    cut = _cutoff(3)

    if not new_orders.empty:
        s = new_orders.iloc[:, 0].dropna()
        yoy_s = s.pct_change(12) * 100
        yoy_s = yoy_s[yoy_s.index >= cut]
        fig.add_trace(
            go.Scatter(
                x=yoy_s.index,
                y=yoy_s,
                mode="lines",
                name="New Orders YoY %",
                line=dict(color="#4CAF50", width=2),
                hovertemplate="%{x|%b %Y}  %{y:.1f}%<extra></extra>",
            ),
            secondary_y=False,
        )

    if not philly_future.empty:
        pf = philly_future[philly_future.index >= cut]
        fig.add_trace(
            go.Bar(
                x=pf.index,
                y=pf.iloc[:, 0],
                name="Philly Fed Future Orders",
                marker_color="#FF9800",
                opacity=0.55,
                hovertemplate="%{x|%b %Y}  %{y:.1f}<extra></extra>",
            ),
            secondary_y=True,
        )

    fig.add_hline(y=0, line_color="#aaaaaa", line_width=1, line_dash="dot")
    fig.update_yaxes(title_text="YoY Growth (%)", secondary_y=False, gridcolor="#f0f0f0")
    fig.update_yaxes(title_text="Diffusion Index", secondary_y=True, showgrid=False)
    fig.update_layout(
        title="Forward-Looking Indicators",
        height=340,
        margin=dict(t=44, b=30, l=55, r=55),
        hovermode="x unified",
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(size=11),
        xaxis=dict(showgrid=False),
        legend=dict(orientation="h", y=-0.18, x=0, font=dict(size=10)),
    )
    return fig


def _employment_chart(df: pd.DataFrame, chart_type: str = "line") -> go.Figure:
    col = df.columns[0]
    color = "#3F51B5"

    if chart_type == "bar":
        trace = go.Bar(
            x=df.index,
            y=df[col],
            name="Mfg Employment",
            marker_color=color,
            hovertemplate="%{x|%b %Y}  %{y:,.0f}K<extra></extra>",
        )
    else:
        trace = go.Scatter(
            x=df.index,
            y=df[col],
            mode="lines",
            fill="tozeroy" if chart_type == "area" else None,
            fillcolor="rgba(63, 81, 181, 0.12)" if chart_type == "area" else None,
            line=dict(color=color, width=2),
            name="Mfg Employment",
            hovertemplate="%{x|%b %Y}  %{y:,.0f}K<extra></extra>",
        )

    fig = go.Figure(trace)
    annotations = [
        ("2009-01-01", "GFC Trough", 40, -50),
        ("2020-04-01", "COVID Low", 40, -50),
    ]
    for date_str, label, ax, ay in annotations:
        ts = pd.Timestamp(date_str)
        if ts >= df.index.min() and ts <= df.index.max():
            fig.add_annotation(
                x=date_str,
                y=_nearest_y(df, date_str),
                text=label,
                showarrow=True,
                arrowhead=2,
                ax=ax,
                ay=ay,
                font=dict(size=9),
            )
    fig.update_layout(
        title="Manufacturing Employment",
        yaxis_title="Thousands of Jobs",
        **_BASE,
    )
    return fig


def _reshoring_chart(chart_type: str = "bar") -> go.Figure:
    if chart_type == "line":
        trace = go.Scatter(
            x=_RESHORING_JOBS["Year"],
            y=_RESHORING_JOBS["Jobs Announced"] / 1000,
            mode="lines+markers",
            line=dict(color="#2E7D32", width=2),
            marker=dict(size=8),
            hovertemplate="%{x}<br>%{y:.0f}K jobs<extra></extra>",
        )
    else:
        trace = go.Bar(
            x=_RESHORING_JOBS["Year"],
            y=_RESHORING_JOBS["Jobs Announced"] / 1000,
            marker_color="#2E7D32",
            hovertemplate="%{x}<br>%{y:.0f}K jobs<extra></extra>",
        )
    fig = go.Figure(trace)
    fig.update_layout(
        title="Reshoring & FDI Jobs Announced",
        yaxis_title="Jobs (Thousands)",
        height=310,
        margin=dict(t=44, b=30, l=55, r=20),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(size=11),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor="#f0f0f0"),
        showlegend=False,
    )
    return fig


# ── ISM upload helpers ─────────────────────────────────────────────────────────


def _try_parse_ism(file_obj) -> Optional[pd.DataFrame]:
    """Auto-detect date and value columns; return None if ambiguous."""
    if file_obj.name.lower().endswith(".csv"):
        df = pd.read_csv(file_obj)
    else:
        df = pd.read_excel(file_obj)

    date_col = None
    val_col = None

    for col in df.columns:
        if date_col is None:
            parsed = pd.to_datetime(df[col], errors="coerce")
            if parsed.notna().sum() > len(df) * 0.8:
                date_col = col
                continue
        if val_col is None and pd.api.types.is_numeric_dtype(df[col]):
            val_col = col

    if date_col is None or val_col is None:
        return None

    out = df[[date_col, val_col]].copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
    out = out.dropna(subset=[date_col])
    out = out.set_index(date_col).sort_index()
    out.columns = ["ISM PMI"]
    out["ISM PMI"] = pd.to_numeric(out["ISM PMI"], errors="coerce")
    return out.dropna()


def _parse_ism_with_selectors(file_obj) -> Optional[pd.DataFrame]:
    """Parse ISM file, showing column pickers if auto-detect fails."""
    if file_obj.name.lower().endswith(".csv"):
        df = pd.read_csv(file_obj)
    else:
        df = pd.read_excel(file_obj)

    cols = df.columns.tolist()

    result = _try_parse_ism(file_obj)
    if result is not None:
        return result

    # Auto-detect failed — let user pick
    st.warning("Could not auto-detect columns. Please select below.")
    date_col = st.selectbox("Date column", cols, key="ism_date_col")
    val_options = [c for c in cols if c != date_col]
    val_col = st.selectbox("Value column", val_options, key="ism_val_col")

    try:
        out = df[[date_col, val_col]].copy()
        out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
        out = out.dropna(subset=[date_col])
        out = out.set_index(date_col).sort_index()
        out.columns = ["ISM PMI"]
        out["ISM PMI"] = pd.to_numeric(out["ISM PMI"], errors="coerce")
        return out.dropna()
    except Exception as e:
        st.error(f"Parse error: {e}")
        return None


# ── Main render ────────────────────────────────────────────────────────────────


def render() -> None:
    st.title("US Reindustrialization")
    st.caption(
        f"FRED data refreshes every 30 min · BEA data refreshes every 60 min · "
        f"Last load: {datetime.now().strftime('%b %d, %Y %H:%M')}"
    )

    # Load per-section config overrides
    _cfg = load_config("reindustrialization") or {"sections": {}}
    _sections = _cfg.get("sections", {}) or {}

    # ── ISM upload in sidebar ──────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("---")
        st.markdown("**ISM Data (Stopgap)**")
        ism_file = st.file_uploader(
            "Upload Bloomberg Excel/CSV",
            type=["xlsx", "xls", "csv"],
            key="ism_uploader",
            help="Expects a date column and ISM PMI value column.",
        )
        if ism_file is not None:
            file_key = f"{ism_file.name}_{ism_file.size}"
            if st.session_state.get("_ism_file_key") != file_key:
                ism_df = _parse_ism_with_selectors(ism_file)
                if ism_df is not None:
                    st.session_state["_ism_data"] = ism_df
                    st.session_state["_ism_file_key"] = file_key
                    st.success(f"Loaded {len(ism_df)} ISM observations.")
        elif "_ism_data" in st.session_state:
            if st.button("Clear ISM data", key="ism_clear"):
                del st.session_state["_ism_data"]
                del st.session_state["_ism_file_key"]
                st.rerun()

    ism_df: Optional[pd.DataFrame] = st.session_state.get("_ism_data")

    # ── Load FRED & BEA data ───────────────────────────────────────────────────
    load_errors: dict = {}

    with st.spinner("Loading economic data…"):
        try:
            indpro = _fred("INDPRO", 10)
        except Exception as e:
            indpro = pd.DataFrame()
            load_errors["INDPRO"] = str(e)

        try:
            manemp = _fred("MANEMP", 15)
        except Exception as e:
            manemp = pd.DataFrame()
            load_errors["MANEMP"] = str(e)

        try:
            new_orders = _fred("AMTMNO", 5)
        except Exception as e:
            new_orders = pd.DataFrame()
            load_errors["AMTMNO"] = str(e)

        try:
            cap_util = _fred("TCU", 5)
        except Exception as e:
            cap_util = pd.DataFrame()
            load_errors["TCU"] = str(e)

        try:
            mfg_const = _fred("TLMFGCONS", 5)
        except Exception as e:
            mfg_const = pd.DataFrame()
            load_errors["TLMFGCONS"] = str(e)

        try:
            philly_current = _fred("GACDFSA066MSFRBPHI", 3)
        except Exception as e:
            philly_current = pd.DataFrame()
            load_errors["Philly Fed Current"] = str(e)

        try:
            philly_future = _fred("NOFDFSA066MSFRBPHI", 3)
        except Exception as e:
            philly_future = pd.DataFrame()
            load_errors["Philly Fed Future"] = str(e)

        try:
            bea_inv = _bea()
        except Exception as e:
            bea_inv = pd.DataFrame()
            load_errors["BEA Investment"] = str(e)

    if load_errors:
        with st.expander(f"⚠️ {len(load_errors)} data source(s) unavailable"):
            for src, msg in load_errors.items():
                st.warning(f"**{src}:** {msg}")

    # ── ROW 1: KPI Metrics ─────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)

    with k1:
        if not indpro.empty:
            val = indpro.iloc[-1, 0]
            st.metric("Industrial Production", f"{val:.1f}", _delta_label(_yoy(indpro.iloc[:, 0])))
        else:
            st.metric("Industrial Production", "N/A")

    with k2:
        if not manemp.empty:
            val = manemp.iloc[-1, 0]
            st.metric("Mfg Employment", f"{val/1000:.2f}M jobs", _delta_label(_yoy(manemp.iloc[:, 0])))
        else:
            st.metric("Mfg Employment", "N/A")

    with k3:
        if not new_orders.empty:
            yoy_pct = _yoy(new_orders.iloc[:, 0])
            label = f"{yoy_pct:+.1f}%" if yoy_pct is not None else "N/A"
            st.metric("New Orders (YoY)", label)
        else:
            st.metric("New Orders (YoY)", "N/A")

    with k4:
        if not cap_util.empty:
            val = cap_util.iloc[-1, 0]
            st.metric("Capacity Utilization", f"{val:.1f}%", _delta_label(_yoy(cap_util.iloc[:, 0])))
        else:
            st.metric("Capacity Utilization", "N/A")

    st.markdown("---")

    # ── ROW 2: Industrial Production | Investment & Construction ───────────────
    col_l, col_r = st.columns(2)

    with col_l:
        _ov = _sections.get("indpro", {}) or {}
        _section_controls("indpro", _ov, ["line", "area", "bar"])
        y_min = _ov.get("y_axis", {}).get("min") if _ov.get("y_axis") else None
        y_max = _ov.get("y_axis", {}).get("max") if _ov.get("y_axis") else None
        if not indpro.empty:
            chart_type = _ov.get("chart_type", "line")
            fig = _indpro_chart(indpro, chart_type=chart_type)
            if y_min is not None or y_max is not None:
                fig.update_yaxes(range=[y_min, y_max])
                apply_clip_arrows(fig, y_min, y_max)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Industrial Production data unavailable.")

    with col_r:
        _ov = _sections.get("investment", {}) or {}
        _section_controls("investment", _ov, ["bar"], has_secondary_y=True)
        if not bea_inv.empty or not mfg_const.empty:
            st.plotly_chart(_investment_chart(bea_inv, mfg_const), use_container_width=True)
        else:
            st.warning("Investment data unavailable. Check BEA_API_KEY.")

    # ── ROW 3: Fed Surveys | Forward Indicators ────────────────────────────────
    col_l, col_r = st.columns(2)

    with col_l:
        _ov = _sections.get("surveys", {}) or {}
        _section_controls("surveys", _ov, ["line"])
        y_min = _ov.get("y_axis", {}).get("min") if _ov.get("y_axis") else None
        y_max = _ov.get("y_axis", {}).get("max") if _ov.get("y_axis") else None
        if not philly_current.empty or not philly_future.empty or ism_df is not None:
            fig = _surveys_chart(philly_current, philly_future, ism_df)
            if y_min is not None or y_max is not None:
                fig.update_yaxes(range=[y_min, y_max])
                apply_clip_arrows(fig, y_min, y_max)
            st.plotly_chart(fig, use_container_width=True)
            if ism_df is None:
                st.caption("ISM PMI not loaded — upload via sidebar to add.")
        else:
            st.warning("Survey data unavailable.")

    with col_r:
        _ov = _sections.get("forward", {}) or {}
        _section_controls("forward", _ov, ["line"], has_secondary_y=True)
        if not new_orders.empty or not philly_future.empty:
            st.plotly_chart(_forward_chart(new_orders, philly_future), use_container_width=True)
        else:
            st.warning("Forward indicator data unavailable.")

    # ── ROW 4: Employment | Reshoring Tracker ─────────────────────────────────
    col_l, col_r = st.columns(2)

    with col_l:
        _ov = _sections.get("employment", {}) or {}
        _section_controls("employment", _ov, ["line", "area", "bar"])
        y_min = _ov.get("y_axis", {}).get("min") if _ov.get("y_axis") else None
        y_max = _ov.get("y_axis", {}).get("max") if _ov.get("y_axis") else None
        if not manemp.empty:
            chart_type = _ov.get("chart_type", "line")
            fig = _employment_chart(manemp, chart_type=chart_type)
            if y_min is not None or y_max is not None:
                fig.update_yaxes(range=[y_min, y_max])
                apply_clip_arrows(fig, y_min, y_max)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Employment data unavailable.")

    with col_r:
        _ov = _sections.get("reshoring", {}) or {}
        _section_controls("reshoring", _ov, ["bar", "line"])
        y_min = _ov.get("y_axis", {}).get("min") if _ov.get("y_axis") else None
        y_max = _ov.get("y_axis", {}).get("max") if _ov.get("y_axis") else None
        r_chart, r_table = st.columns([3, 2])
        with r_chart:
            chart_type = _ov.get("chart_type", "bar")
            fig = _reshoring_chart(chart_type=chart_type)
            if y_min is not None or y_max is not None:
                fig.update_yaxes(range=[y_min, y_max])
                apply_clip_arrows(fig, y_min, y_max)
            st.plotly_chart(fig, use_container_width=True)
        with r_table:
            st.markdown("**Recent Major Announcements**")
            st.dataframe(
                _RESHORING_TABLE,
                hide_index=True,
                use_container_width=True,
                height=310,
            )
        st.caption("Source: Reshoring Initiative · Updated annually.")

    # ── News Feed ──────────────────────────────────────────────────────────────
    news_query = _cfg.get("news_query", "")
    if news_query:
        render_news_section(news_query, title="Manufacturing & Trade News")
