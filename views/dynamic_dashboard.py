"""
Generic renderer for builder-created (dynamic) dashboards.

Called by app.py as:  render_dynamic(config_dict)
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from modules.config.dashboard_config import save_config
from modules.config.chart_catalog import get_item as catalog_get_item
from modules.config.feed_catalog import get_feed
from modules.data_ingestion.fred_loader import load_fred_series
from modules.data_processing.transforms import (
    month_over_month,
    rolling_mean,
    year_over_year,
)
from modules.visualization.charts import time_series_chart
from modules.visualization.news_widget import render_news_section
from components.chart_renderer import apply_style


# ---------------------------------------------------------------------------
# Layout aliases: normalise old "left"/"right" → "half"
# ---------------------------------------------------------------------------

_LAYOUT_WIDTHS: Dict[str, float] = {
    "full": 1.0,
    "half": 0.5,
    "third": 1 / 3,
    "quarter": 0.25,
    # Backward compat
    "left": 0.5,
    "right": 0.5,
}


# ---------------------------------------------------------------------------
# Cached FRED loaders
# ---------------------------------------------------------------------------


@st.cache_data(ttl=1800, show_spinner=False)
def _load_series_fred(series_id: str, years_back: int, transform: str) -> pd.DataFrame:
    """Load a FRED series and apply the requested transform."""
    start = (datetime.today() - timedelta(days=years_back * 365)).strftime("%Y-%m-%d")
    df = load_fred_series(series_id, start_date=start)
    if df.empty:
        return df
    series = df.iloc[:, 0]
    if transform == "yoy":
        series = year_over_year(series)
    elif transform == "mom":
        series = month_over_month(series)
    elif transform == "rolling_12":
        series = rolling_mean(series, 12)
    return series.to_frame()


@st.cache_data(ttl=1800, show_spinner=False)
def _load_card_fred(series_id: str) -> pd.DataFrame:
    """Load a FRED series for card display (no transform, full history)."""
    return load_fred_series(series_id)


@st.cache_data(ttl=1800, show_spinner=False)
def _load_series_feed(
    provider_name: str, series_id: str, feed_kwargs_json: str, years_back: int, transform: str
) -> pd.DataFrame:
    """Load a registered feed series via provider and apply transform."""
    import json
    from providers import get_provider as _gp

    try:
        provider = _gp(provider_name)
        kwargs = json.loads(feed_kwargs_json) if feed_kwargs_json and feed_kwargs_json != "{}" else {}
        df = provider.fetch_series(series_id, **kwargs)
        if df is None or df.empty:
            return pd.DataFrame()
        series = df.iloc[:, 0]
        # Apply time window filter
        if years_back and isinstance(df.index, pd.DatetimeIndex):
            cutoff = datetime.today() - timedelta(days=years_back * 365)
            series = series[series.index >= cutoff]
        # Apply transform
        if transform == "yoy":
            series = year_over_year(series)
        elif transform == "mom":
            series = month_over_month(series)
        elif transform in ("rolling_12", "rolling"):
            series = rolling_mean(series, 12)
        return series.to_frame()
    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _yoy_pct(series: pd.Series) -> Optional[float]:
    """Year-over-year percent change using 12-period lookback."""
    if len(series) < 13:
        return None
    try:
        prev = series.iloc[-13]
        curr = series.iloc[-1]
        if prev == 0:
            return None
        return (curr / prev - 1) * 100
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Per-section settings controls (dynamic version)
# ---------------------------------------------------------------------------


def _compute_data_range(
    merged: Optional[pd.DataFrame],
    dual_axis_col: Optional[str] = None,
) -> Dict[str, Dict[str, float]]:
    """Compute actual min/max from data for pre-populating Y-axis inputs.

    Returns {"primary": {"min": ..., "max": ...}, "secondary": {"min": ..., "max": ...}}.
    """
    result: Dict[str, Dict[str, float]] = {
        "primary": {"min": 0.0, "max": 100.0},
        "secondary": {"min": 0.0, "max": 100.0},
    }
    if merged is None or merged.empty:
        return result

    if dual_axis_col and dual_axis_col in merged.columns:
        primary_cols = [c for c in merged.columns if c != dual_axis_col]
        sec_data = merged[dual_axis_col].dropna()
        if not sec_data.empty:
            result["secondary"] = {"min": float(sec_data.min()), "max": float(sec_data.max())}
    else:
        primary_cols = list(merged.columns)

    if primary_cols:
        pri_data = merged[primary_cols].dropna(how="all")
        if not pri_data.empty:
            result["primary"] = {"min": float(pri_data.min().min()), "max": float(pri_data.max().max())}

    return result


def _section_controls_dynamic(
    sec: Dict[str, Any],
    config: Dict[str, Any],
    data_range: Optional[Dict[str, Dict[str, float]]] = None,
    has_dual_axis: Optional[bool] = None,
) -> None:
    """Settings expander for a dynamic section; saves updated config on submit."""
    section_id = sec.get("id", "")
    allowed_types = ["line", "bar", "area"]
    current_type = sec.get("chart_type", "line")
    if current_type not in allowed_types:
        current_type = "line"

    y_axis = sec.get("y_axis") or {}
    y_axis2 = sec.get("y_axis2") or {}
    has_secondary = has_dual_axis if has_dual_axis is not None else any(s.get("axis") == 2 for s in sec.get("series", []))

    # Default values from data range when no saved value exists
    dr = data_range or {"primary": {"min": 0.0, "max": 100.0}, "secondary": {"min": 0.0, "max": 100.0}}
    default_ymin = dr["primary"]["min"]
    default_ymax = dr["primary"]["max"]
    default_ymin2 = dr["secondary"]["min"]
    default_ymax2 = dr["secondary"]["max"]

    with st.expander("⚙ Chart Settings", expanded=False):
        new_chart_type = st.selectbox(
            "Chart type",
            options=allowed_types,
            index=allowed_types.index(current_type),
            key=f"dyn_ct_{section_id}",
        )

        st.caption(f"Data range: {default_ymin:,.2f} – {default_ymax:,.2f}")
        col_a, col_b = st.columns(2)
        with col_a:
            en_ymin = st.checkbox(
                "Set Y min",
                value=y_axis.get("min") is not None,
                key=f"dyn_en_ymin_{section_id}",
            )
            y_min_val = st.number_input(
                "Y min",
                value=float(y_axis["min"]) if y_axis.get("min") is not None else default_ymin,
                key=f"dyn_ymin_{section_id}",
                disabled=not en_ymin,
            )
        with col_b:
            en_ymax = st.checkbox(
                "Set Y max",
                value=y_axis.get("max") is not None,
                key=f"dyn_en_ymax_{section_id}",
            )
            y_max_val = st.number_input(
                "Y max",
                value=float(y_axis["max"]) if y_axis.get("max") is not None else default_ymax,
                key=f"dyn_ymax_{section_id}",
                disabled=not en_ymax,
            )

        if has_secondary:
            st.caption(f"Secondary axis range: {default_ymin2:,.2f} – {default_ymax2:,.2f}")
            col_c, col_d = st.columns(2)
            with col_c:
                en_ymin2 = st.checkbox(
                    "Set Y2 min",
                    value=y_axis2.get("min") is not None,
                    key=f"dyn_en_ymin2_{section_id}",
                )
                y_min2_val = st.number_input(
                    "Y2 min",
                    value=float(y_axis2["min"]) if y_axis2.get("min") is not None else default_ymin2,
                    key=f"dyn_ymin2_{section_id}",
                    disabled=not en_ymin2,
                )
            with col_d:
                en_ymax2 = st.checkbox(
                    "Set Y2 max",
                    value=y_axis2.get("max") is not None,
                    key=f"dyn_en_ymax2_{section_id}",
                )
                y_max2_val = st.number_input(
                    "Y2 max",
                    value=float(y_axis2["max"]) if y_axis2.get("max") is not None else default_ymax2,
                    key=f"dyn_ymax2_{section_id}",
                    disabled=not en_ymax2,
                )
        else:
            en_ymin2 = en_ymax2 = False
            y_min2_val = y_max2_val = 0.0

        if st.button("Save settings", key=f"dyn_save_{section_id}"):
            new_cfg = copy.deepcopy(config)
            for s in new_cfg.get("sections", []):
                if s.get("id") == section_id:
                    s["chart_type"] = new_chart_type
                    s["y_axis"] = {
                        "min": float(y_min_val) if en_ymin else None,
                        "max": float(y_max_val) if en_ymax else None,
                    }
                    if has_secondary:
                        s["y_axis2"] = {
                            "min": float(y_min2_val) if en_ymin2 else None,
                            "max": float(y_max2_val) if en_ymax2 else None,
                        }
                    break
            save_config(new_cfg)
            st.rerun()


# ---------------------------------------------------------------------------
# Chart section renderer (uses st.* directly; call inside 'with col:' for columns)
# ---------------------------------------------------------------------------


def _render_chart_section(
    sec: Dict[str, Any],
    config: Dict[str, Any],
) -> None:
    """Load series, build chart, apply clip arrows, render controls."""
    st.subheader(sec.get("title", "Chart"))

    series_defs = sec.get("series", [])
    if not series_defs:
        st.info("No series configured for this section.")
        return

    load_errors: List[str] = []
    frames: List[pd.DataFrame] = []
    dual_axis_col: Optional[str] = None

    for sdef in series_defs:
        source = sdef.get("source", "fred")
        sid = sdef.get("series_id", "")
        label = sdef.get("label") or sid
        transform = sdef.get("transform", "none")
        years_back = int(sdef.get("years_back", 10))
        axis = int(sdef.get("axis", 1))

        if source == "fred" and sid:
            try:
                df = _load_series_fred(sid, years_back, transform)
                if not df.empty:
                    df.columns = [label]
                    frames.append(df)
                    if axis == 2:
                        dual_axis_col = label
            except Exception as e:
                load_errors.append(f"{label}: {e}")

    if load_errors:
        for err in load_errors:
            st.warning(err)

    if not frames:
        st.warning("Could not load any series for this section.")
        _section_controls_dynamic(sec, config)
        return

    merged = frames[0]
    for f in frames[1:]:
        merged = merged.join(f, how="outer")

    y_axis = sec.get("y_axis") or {}
    y_axis2 = sec.get("y_axis2") or {}
    y_min = y_axis.get("min")
    y_max = y_axis.get("max")
    y_min2 = y_axis2.get("min")
    y_max2 = y_axis2.get("max")
    chart_type = sec.get("chart_type", "line")

    fig = time_series_chart(
        merged,
        title="",
        dual_axis_col=dual_axis_col,
        chart_type=chart_type,
        y_min=y_min,
        y_max=y_max,
        y_min2=y_min2,
        y_max2=y_max2,
    )

    data_range = _compute_data_range(merged, dual_axis_col)
    _section_controls_dynamic(sec, config, data_range=data_range)
    apply_style(fig)
    fig.update_layout(margin=dict(t=30))
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Catalog chart renderer (uses st.* directly; call inside 'with col:' for columns)
# ---------------------------------------------------------------------------


def _render_catalog_chart_section(
    sec: Dict[str, Any],
    config: Dict[str, Any],
) -> None:
    """Load a saved catalog chart item and render it."""
    catalog_id = sec.get("catalog_id", "")
    item_id = sec.get("item_id", "")
    item = catalog_get_item(catalog_id, item_id)

    if item is None:
        st.warning(f"Saved chart not found (catalog: {catalog_id}, item: {item_id})")
        return

    title = sec.get("title_override") or item.get("title", "Chart")
    st.subheader(title)

    series_defs = item.get("series", [])
    if not series_defs:
        st.info("No series configured for this chart.")
        return

    load_errors: List[str] = []
    frames: List[pd.DataFrame] = []
    dual_axis_col: Optional[str] = None
    years_back_default = 10

    # First pass: build a name→df map for non-computed series so computed
    # series can reference them
    raw_data: Dict[str, pd.Series] = {}

    for sdef in series_defs:
        source = sdef.get("source", "fred")
        sid = sdef.get("series_id", "")
        label = sdef.get("label") or sid
        transform = sdef.get("transform", "none")
        years_back = int(sdef.get("years_back", years_back_default))
        axis = int(sdef.get("axis", 1))

        try:
            if source == "fred" and sid:
                df = _load_series_fred(sid, years_back, transform)
                if not df.empty:
                    s = df.iloc[:, 0].rename(label)
                    raw_data[label] = s
                    frames.append(s.to_frame())
                    if axis == 2:
                        dual_axis_col = label

            elif source == "catalog":
                # When col is a valid FRED series ID (e.g. "CPIAUCSL"), we can
                # reload it from FRED. If the column came from a CSV/BEA/Zillow
                # dataset the name won't be a FRED ID and loading will fail —
                # in that case, show a descriptive message instead of a cryptic error.
                col_name = sdef.get("col", "")
                dataset_name = sdef.get("catalog_name", sdef.get("dataset_name", ""))
                if col_name:
                    try:
                        df = _load_series_fred(col_name, years_back, transform)
                        if not df.empty:
                            s = df.iloc[:, 0].rename(label)
                            raw_data[label] = s
                            frames.append(s.to_frame())
                            if axis == 2:
                                dual_axis_col = label
                        else:
                            load_errors.append(f"{label}: no data returned for '{col_name}'")
                    except Exception:
                        # col is not a FRED series ID — it came from a session-only dataset
                        load_errors.append(
                            f"{label}: series '{col_name}' from dataset '{dataset_name}' "
                            f"is session-only — re-load the dataset from Data Sources and "
                            f"re-save the chart to restore it."
                        )
                else:
                    load_errors.append(f"{label}: session-only data unavailable (no column name stored)")

            elif source == "feed":
                import json
                feed_id = sdef.get("feed_id", "")
                if feed_id:
                    feed = get_feed(feed_id)
                    if feed:
                        kwargs_json = json.dumps(feed.get("kwargs", {}))
                        df = _load_series_feed(
                            feed["provider"], feed["series_id"], kwargs_json, years_back, transform
                        )
                        if not df.empty:
                            s = df.iloc[:, 0].rename(label)
                            raw_data[label] = s
                            frames.append(s.to_frame())
                            if axis == 2:
                                dual_axis_col = label
                        else:
                            load_errors.append(f"{label}: no data from feed '{feed.get('name', feed_id)}'")
                    else:
                        load_errors.append(f"{label}: feed '{feed_id}' not found in catalog")
                else:
                    load_errors.append(f"{label}: no feed_id configured")

            elif source == "computed":
                series_a = sdef.get("series_a", "")
                series_b = sdef.get("series_b", "")
                op = sdef.get("op", "div")

                # Try to resolve each operand: check raw_data first, then try FRED
                def _resolve(name: str) -> Optional[pd.Series]:
                    if name in raw_data:
                        return raw_data[name]
                    # Try loading as FRED series ID
                    try:
                        df_tmp = _load_series_fred(name, years_back_default, "none")
                        if not df_tmp.empty:
                            s_tmp = df_tmp.iloc[:, 0]
                            raw_data[name] = s_tmp
                            return s_tmp
                    except Exception:
                        pass
                    return None

                sa = _resolve(series_a)
                sb = _resolve(series_b)

                if sa is not None and sb is not None:
                    sa_a, sb_a = sa.align(sb, join="inner")
                    if op == "div":
                        result = sa_a / sb_a
                    elif op == "sub":
                        result = sa_a - sb_a
                    elif op == "add":
                        result = sa_a + sb_a
                    elif op == "mul":
                        result = sa_a * sb_a
                    else:  # pct_diff
                        result = (sa_a - sb_a) / sb_a * 100
                    result = result.rename(label)
                    raw_data[label] = result
                    frames.append(result.to_frame())
                    if axis == 2:
                        dual_axis_col = label
                else:
                    load_errors.append(
                        f"computed '{label}': could not resolve "
                        f"'{series_a}' or '{series_b}'"
                    )

        except Exception as e:
            load_errors.append(f"{label}: {e}")

    if load_errors:
        for err in load_errors:
            st.warning(err)

    if not frames:
        st.warning("Could not load any series for this chart.")
        return

    merged = frames[0]
    for f in frames[1:]:
        merged = merged.join(f, how="outer")

    # Section-level overrides take priority over catalog item defaults
    y_axis = sec.get("y_axis") or item.get("y_axis") or {}
    y_axis2 = sec.get("y_axis2") or item.get("y_axis2") or {}
    y_min = y_axis.get("min")
    y_max = y_axis.get("max")
    y_min2 = y_axis2.get("min")
    y_max2 = y_axis2.get("max")

    # Section-level chart_type override, then per-series from catalog item
    chart_type = sec.get("chart_type") or ("line" if not series_defs else series_defs[0].get("chart_type", "line"))

    # Build per-series types map
    series_types = {
        sdef.get("label") or sdef.get("series_id", ""): sdef.get("chart_type", "line")
        for sdef in series_defs
    }

    fig = time_series_chart(
        merged,
        title="",
        dual_axis_col=dual_axis_col,
        chart_type=chart_type,
        series_types=series_types,
        y_min=y_min,
        y_max=y_max,
        y_min2=y_min2,
        y_max2=y_max2,
        show_legend=item.get("show_legend", True),
    )

    # Apply saved default date range
    _default_range = item.get("default_range_years")
    if _default_range and int(_default_range) > 0:
        _range_end = datetime.today()
        _range_start = _range_end - timedelta(days=int(_default_range) * 365)
        fig.update_layout(xaxis=dict(range=[_range_start.strftime("%Y-%m-%d"), _range_end.strftime("%Y-%m-%d")]))

    data_range = _compute_data_range(merged, dual_axis_col)
    _section_controls_dynamic(sec, config, data_range=data_range, has_dual_axis=dual_axis_col is not None)
    apply_style(fig)
    fig.update_layout(margin=dict(t=30))
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Card row renderer (uses st.* directly, creates its own columns)
# ---------------------------------------------------------------------------


def _render_card_row_section(sec: Dict[str, Any]) -> None:
    """Render a row of metric cards from catalog items."""
    cards = sec.get("cards", [])
    if not cards:
        st.warning("Card row has no cards configured.")
        return

    cols = st.columns(len(cards))
    for col, ref in zip(cols, cards):
        item = catalog_get_item(ref.get("catalog_id", ""), ref.get("item_id", ""))
        if item is None:
            col.warning("Card not found")
            continue

        card_title = item.get("title", "")
        delta_type = item.get("delta_type", "none")
        fmt = item.get("value_format", ",.2f")
        sfx = item.get("value_suffix", "")
        pfx = item.get("value_prefix", "")  # backward compat

        # ── Resolve data series ──────────────────────────────────────────────
        series: Optional[pd.Series] = None

        # Primary path: feed_id (new format)
        _card_feed_id = item.get("feed_id", "")
        if _card_feed_id:
            try:
                from modules.config.feed_catalog import get_feed as _card_get_feed
                from providers import get_provider as _card_get_prov
                _card_feed = _card_get_feed(_card_feed_id)
                if _card_feed:
                    _cprov = _card_get_prov(_card_feed["provider"])
                    _cdf = _cprov.fetch_series(_card_feed["series_id"], **_card_feed.get("kwargs", {}))
                    if _cdf is not None and not _cdf.empty:
                        series = _cdf.iloc[:, 0].dropna()
            except Exception:
                pass

        # Fallback: dataset_name + column from session catalog (legacy)
        if series is None or series.empty:
            dataset_name = item.get("dataset_name", "")
            column = item.get("column", "")
            if dataset_name and column:
                session_cat = st.session_state.get("catalog", {})
                df_cat = session_cat.get(dataset_name)
                if df_cat is not None and column in df_cat.columns:
                    series = df_cat[column].dropna()
                    if not isinstance(series.index, pd.DatetimeIndex):
                        try:
                            series.index = pd.to_datetime(series.index)
                        except Exception:
                            pass

        # Fallback: FRED series_id (old format or explicit fred_series_id)
        if series is None or series.empty:
            fred_id = item.get("fred_series_id") or item.get("series_id") or ""
            if fred_id:
                try:
                    df_fred = _load_card_fred(fred_id)
                    if not df_fred.empty:
                        series = df_fred.iloc[:, 0].dropna()
                except Exception:
                    pass

        if series is None or series.empty:
            source_hint = f"`{dataset_name}/{column}`" if dataset_name else "no data source"
            col.warning(f"{card_title or 'Card'}: no data ({source_hint})")
            continue

        value = series.iloc[-1]

        # Delta
        delta_str: Optional[str] = None
        if delta_type == "yoy":
            yoy = _yoy_pct(series)
            if yoy is not None:
                delta_str = f"{yoy:+.2f}% YoY"
        elif delta_type == "period":
            if len(series) >= 2:
                chg = series.iloc[-1] - series.iloc[-2]
                delta_str = f"{chg:+.4g} vs prior period"

        # Format value
        try:
            val_str = f"{pfx}{format(value, fmt)}{sfx}"
        except Exception:
            val_str = f"{pfx}{value}{sfx}"

        col.metric(card_title or (column or "Value"), val_str, delta_str)

        # Backward compat: show release dates if present (old format)
        prior = item.get("prior_release") or ""
        nxt = item.get("next_release") or ""
        if prior or nxt:
            col.caption(f"Prior: {prior or '—'}  ·  Next: {nxt or '—'}")


# ---------------------------------------------------------------------------
# Grid layout helpers
# ---------------------------------------------------------------------------


def _group_into_rows(sections: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """
    Group sections into display rows.

    Rules:
    - card_row sections always form their own single-item full-width row.
    - Sections with layout=="full" form their own single-item row.
    - Consecutive non-full sections are collected into one row.
    """
    rows: List[List[Dict[str, Any]]] = []
    pending: List[Dict[str, Any]] = []

    for sec in sections:
        if sec.get("type") == "card_row":
            if pending:
                rows.append(pending)
                pending = []
            rows.append([sec])
        elif sec.get("layout", "full") == "full":
            if pending:
                rows.append(pending)
                pending = []
            rows.append([sec])
        else:
            pending.append(sec)

    if pending:
        rows.append(pending)

    return rows


# ---------------------------------------------------------------------------
# Main render entry point
# ---------------------------------------------------------------------------


def render(config: Dict[str, Any], preview: bool = False) -> None:
    """Render a fully config-driven dashboard.

    Parameters
    ----------
    config  : dashboard JSON config dict
    preview : if True, skip the toolbar (used by Dashboard Builder preview)
    """
    title = config.get("title", "Dashboard")
    description = config.get("description", "")
    news_query = config.get("news_query", "")

    if preview:
        st.subheader(title)
        if description:
            st.caption(description)
    else:
        # Title row with toolbar buttons on the right
        _tb_title, _tb_edit, _tb_refresh = st.columns([8, 1, 1])
        with _tb_title:
            st.title(title)
            if description:
                st.caption(description)
        with _tb_edit:
            st.markdown("<div style='padding-top:0.6rem'></div>", unsafe_allow_html=True)
            if st.button("Edit", key=f"dyn_edit_{config.get('id', '')}", help="Edit in Dashboard Builder"):
                st.session_state.builder_draft = config
                st.session_state.builder_edit_id = config.get("id")
                st.session_state.builder_step = 2
                st.session_state["b_pending_series"] = []
                st.session_state.page = "Dashboard Builder"
                st.rerun()
        with _tb_refresh:
            st.markdown("<div style='padding-top:0.6rem'></div>", unsafe_allow_html=True)
            if st.button("Refresh", key=f"dyn_refresh_{config.get('id', '')}", help="Reload all data"):
                _load_series_fred.clear()
                _load_card_fred.clear()
                _load_series_feed.clear()
                st.rerun()

    sections = config.get("sections", [])
    if not sections:
        st.info("This dashboard has no sections yet. Edit it in Dashboard Builder.")
        return

    rows = _group_into_rows(sections)

    for row in rows:
        if len(row) == 1:
            sec = row[0]
            sec_type = sec.get("type", "chart")
            if sec_type == "chart":
                _render_chart_section(sec, config)
            elif sec_type == "catalog_chart":
                _render_catalog_chart_section(sec, config)
            elif sec_type == "card_row":
                _render_card_row_section(sec)
            elif sec_type == "news":
                render_news_section(
                    sec.get("query") or news_query,
                    title=sec.get("title", "Latest News"),
                )
        else:
            # Multi-column row
            cols = st.columns(len(row))
            for col, sec in zip(cols, row):
                sec_type = sec.get("type", "chart")
                with col:
                    if sec_type == "chart":
                        _render_chart_section(sec, config)
                    elif sec_type == "catalog_chart":
                        _render_catalog_chart_section(sec, config)
                    elif sec_type == "news":
                        render_news_section(
                            sec.get("query") or news_query,
                            title=sec.get("title", "Latest News"),
                        )

    # Dashboard-level news feed (if no explicit news section)
    has_news_section = any(s.get("type") == "news" for s in sections)
    if news_query and not has_news_section:
        render_news_section(news_query, title="Latest News")
