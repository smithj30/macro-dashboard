"""
Macro Dashboard — main Streamlit entry point.

Run with:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np

# ── Dashboard views ───────────────────────────────────────────────────────────
from views.dynamic_dashboard import render as render_dynamic
from views.dashboard_builder import render as render_builder
from views.feed_manager import render as render_feed_manager
from views.tag_manager import render_tag_manager
from views.data_explorer import render as render_data_explorer

from modules.config.dashboard_config import list_dynamic_dashboards

# ── Module imports ────────────────────────────────────────────────────────────

from modules.data_processing.transforms import (
    year_over_year,
    month_over_month,
    year_over_year_diff,
    month_over_month_diff,
    merge_dataframes,
    summary_statistics,
    rolling_mean,
)
from modules.analysis.regression import (
    run_ols,
    format_ols_table,
    rolling_correlation,
    correlation_matrix,
)
from modules.visualization.charts import (
    time_series_chart,
    rolling_corr_chart,
    residual_plot,
    residual_histogram,
    apply_recession_shading,
)

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Macro Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { min-width: 260px; max-width: 320px; }
    .block-container { padding-top: 1rem !important; padding-bottom: 0.5rem !important; max-width: 100% !important; padding-left: 1.5rem !important; padding-right: 1.5rem !important; }
    .main .block-container { width: 100% !important; }
    .metric-card {
        background: #FAF9F9;
        border: 1px solid #E1DBD4;
        border-radius: 8px;
        padding: 10px 14px;
        margin: 3px 0;
    }
    h1 { font-size: 1.5rem !important; }
    h2 { font-size: 1.1rem !important; border-bottom: 1px solid #E1DBD4; padding-bottom: 4px; }
    h3 { font-size: 0.95rem !important; }
    p, li, label, .stMarkdown, .stCaption, [data-testid="stText"] {
        font-size: 0.9rem !important;
    }
    .stButton button {
        font-size: 0.82rem !important;
        padding: 0.3rem 0.8rem !important;
    }
    [data-testid="stMetricValue"] { font-size: 1.3rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.82rem !important; }
    [data-testid="stMetricDelta"] { font-size: 0.78rem !important; }
    /* Hide heading anchor link icons */
    h1 a, h2 a, h3 a, h4 a, h5 a, h6 a,
    [data-testid="stHeaderActionElements"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Navigation config ─────────────────────────────────────────────────────────

# Scan dashboards/ for dynamic configs on every rerun (builder writes → immediate refresh)
_dynamic_dashboards = list_dynamic_dashboards()
_dynamic_page_map = {cfg["title"]: cfg for cfg in _dynamic_dashboards}

_DASHBOARD_PAGES = [cfg["title"] for cfg in _dynamic_dashboards]
_TOOL_PAGES = ["Data Explorer", "Feed Manager", "Chart Builder", "Chart Catalogs", "Dashboard Builder", "Tag Manager", "Regression & Analysis", "Data Table"]

if "page" not in st.session_state:
    st.session_state.page = _DASHBOARD_PAGES[0] if _DASHBOARD_PAGES else _TOOL_PAGES[0]

# ── Session state initialisation ──────────────────────────────────────────────

if "catalog" not in st.session_state:
    # catalog: dict[str, pd.DataFrame]  — name → DataFrame with DatetimeIndex
    st.session_state.catalog = {}

if "zillow_cache" not in st.session_state:
    # For Zillow data that needs region selection after loading
    st.session_state.zillow_cache = None

# cb_* and cc_* session state is initialised in views/chart_editor.py::_init_state()


# ── Helpers ───────────────────────────────────────────────────────────────────

def add_to_catalog(name: str, df: pd.DataFrame):
    """Add or overwrite a dataset in the session catalog."""
    if not isinstance(df.index, pd.DatetimeIndex):
        try:
            df.index = pd.to_datetime(df.index)
        except Exception:
            pass
    st.session_state.catalog[name] = df


def catalog_names() -> list[str]:
    return list(st.session_state.catalog.keys())


def get_numeric_columns(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include=[np.number]).columns.tolist()


def get_merged_df(selected_datasets: list[str]) -> pd.DataFrame:
    """Merge selected datasets from catalog into one DataFrame."""
    dfs = [st.session_state.catalog[n] for n in selected_datasets if n in st.session_state.catalog]
    if not dfs:
        return pd.DataFrame()
    return merge_dataframes(dfs, how="outer")


# ── Sidebar navigation ────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📈 Macro Dashboard")
    st.markdown("---")

    st.markdown(
        "<p style='color:#888;font-size:0.72rem;font-weight:700;"
        "letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px'>"
        "Dashboards</p>",
        unsafe_allow_html=True,
    )
    for _p in _DASHBOARD_PAGES:
        if st.button(
            _p,
            key=f"nav_{_p}",
            use_container_width=True,
            type="primary" if st.session_state.page == _p else "secondary",
        ):
            st.session_state.page = _p
            st.rerun()

    st.markdown(
        "<p style='color:#888;font-size:0.72rem;font-weight:700;"
        "letter-spacing:0.08em;text-transform:uppercase;margin:14px 0 6px'>"
        "Tools</p>",
        unsafe_allow_html=True,
    )
    for _p in _TOOL_PAGES:
        if st.button(
            _p,
            key=f"nav_{_p}",
            use_container_width=True,
            type="primary" if st.session_state.page == _p else "secondary",
        ):
            st.session_state.page = _p
            st.rerun()


    if st.session_state.get("cb_recent_fred"):
        st.markdown("**Recent FRED**")
        for _r in st.session_state.cb_recent_fred[:5]:
            st.caption(f"📈 `{_r['id']}`  {_r.get('title', '')[:25]}")

    st.markdown("---")
    st.caption("Built with Streamlit · Plotly · FRED API")

page = st.session_state.page


# =============================================================================
# PAGE: DYNAMIC DASHBOARDS
# =============================================================================

if page in _dynamic_page_map:
    render_dynamic(_dynamic_page_map[page])


# =============================================================================
# PAGE: DASHBOARD BUILDER
# =============================================================================

elif page == "Dashboard Builder":
    render_builder()


# =============================================================================
# PAGE: DATA EXPLORER
# =============================================================================

elif page == "Data Explorer":
    render_data_explorer()




# =============================================================================
# PAGE: FEED MANAGER
# =============================================================================

elif page == "Feed Manager":
    render_feed_manager()

# =============================================================================
# PAGE: CHART BUILDER
# =============================================================================

elif page == "Chart Builder":
    from views.chart_editor import render_chart_builder
    render_chart_builder()

# =============================================================================
# PAGE: CHART CATALOGS
# =============================================================================

elif page == "Chart Catalogs":
    from views.chart_editor import render_chart_catalogs
    render_chart_catalogs()


# =============================================================================
# PAGE: REGRESSION & ANALYSIS
# =============================================================================

elif page == "Regression & Analysis":
    st.title("Regression & Analysis")

    if not st.session_state.catalog:
        st.info("No data loaded yet. Go to **Data Sources** to load some datasets.")
        st.stop()

    tab_ols, tab_rolcor, tab_transform, tab_stats = st.tabs(
        ["📐 OLS Regression", "📉 Rolling Correlation", "🔄 Transforms", "📊 Summary Stats"]
    )

    # ── OLS ──────────────────────────────────────────────────────────────────
    with tab_ols:
        st.subheader("OLS Regression")

        selected_datasets = st.multiselect(
            "Select datasets",
            options=catalog_names(),
            default=catalog_names()[:2],
            key="ols_datasets",
        )

        if not selected_datasets:
            st.info("Select at least one dataset.")
            st.stop()

        merged = get_merged_df(selected_datasets)
        numeric_cols = get_numeric_columns(merged)

        if len(numeric_cols) < 2:
            st.warning("Need at least two numeric columns for regression.")
            st.stop()

        col1, col2 = st.columns(2)
        with col1:
            dep_var = st.selectbox("Dependent variable (Y)", options=numeric_cols, key="ols_dep")
        with col2:
            indep_candidates = [c for c in numeric_cols if c != dep_var]
            indep_vars = st.multiselect(
                "Independent variable(s) (X)",
                options=indep_candidates,
                default=indep_candidates[:1],
                key="ols_indep",
            )

        add_const = st.checkbox("Add intercept (constant)", value=True, key="ols_const")

        if st.button("Run Regression", key="ols_run", use_container_width=True):
            if not indep_vars:
                st.warning("Select at least one independent variable.")
            else:
                with st.spinner("Running OLS…"):
                    try:
                        result = run_ols(merged, dep_var, indep_vars, add_constant=add_const)
                        st.session_state["ols_result"] = result
                        st.session_state["ols_merged"] = merged
                    except Exception as e:
                        st.error(f"Regression failed: {e}")

        if "ols_result" in st.session_state:
            result = st.session_state["ols_result"]

            # KPI row
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("R²", f"{result['rsquared']:.4f}")
            c2.metric("Adj. R²", f"{result['rsquared_adj']:.4f}")
            c3.metric("F-statistic", f"{result['fstatistic']:.4f}")
            c4.metric("Observations", f"{result['nobs']:,}")

            st.markdown("**Coefficient Table**")
            coef_table = format_ols_table(result)
            st.dataframe(
                coef_table.style.applymap(
                    lambda v: "color: green; font-weight: bold" if v is True else "",
                    subset=["significant"],
                ),
                use_container_width=True,
            )

            with st.expander("Full statsmodels summary"):
                st.markdown(result["summary_html"], unsafe_allow_html=True)

            # Residual plots
            st.markdown("**Residual Diagnostics**")
            rc1, rc2 = st.columns(2)
            with rc1:
                fig_resid = residual_plot(result["fitted"], result["residuals"])
                st.plotly_chart(fig_resid, use_container_width=True)
            with rc2:
                fig_hist = residual_histogram(result["residuals"])
                st.plotly_chart(fig_hist, use_container_width=True)

            # Fitted vs actual
            merged_plot = st.session_state["ols_merged"]
            actual_col = dep_var if "dep_var" not in st.session_state else dep_var
            actual = merged_plot[dep_var].dropna()
            fitted_series = result["fitted"].reindex(actual.index)

            plot_df = pd.DataFrame({
                f"{dep_var} (actual)": actual,
                f"{dep_var} (fitted)": fitted_series,
            })
            fig_fit = time_series_chart(plot_df, title="Actual vs Fitted")
            st.plotly_chart(fig_fit, use_container_width=True)

    # ── Rolling Correlation ──────────────────────────────────────────────────
    with tab_rolcor:
        st.subheader("Rolling Correlation")

        selected_datasets = st.multiselect(
            "Select datasets",
            options=catalog_names(),
            default=catalog_names()[:2],
            key="rc_datasets",
        )

        if not selected_datasets:
            st.info("Select at least one dataset.")
            st.stop()

        merged = get_merged_df(selected_datasets)
        numeric_cols = get_numeric_columns(merged)

        col1, col2, col3 = st.columns(3)
        with col1:
            s1_col = st.selectbox("Series A", numeric_cols, index=0, key="rc_s1")
        with col2:
            s2_col = st.selectbox("Series B", numeric_cols, index=min(1, len(numeric_cols) - 1), key="rc_s2")
        with col3:
            window = st.number_input("Window (periods)", min_value=3, max_value=500, value=36, key="rc_window")

        if st.button("Compute", key="rc_run", use_container_width=True):
            if s1_col == s2_col:
                st.warning("Select two different series.")
            else:
                try:
                    rc = rolling_correlation(merged[s1_col], merged[s2_col], window=int(window))
                    fig = rolling_corr_chart(rc)
                    st.plotly_chart(fig, use_container_width=True)

                    full_corr = merged[s1_col].corr(merged[s2_col])
                    st.metric("Full-period Pearson r", f"{full_corr:.4f}")
                except Exception as e:
                    st.error(f"Failed: {e}")

    # ── Transforms ───────────────────────────────────────────────────────────
    with tab_transform:
        st.subheader("Compute Transforms")
        st.caption("Compute YoY/MoM percent changes and add them to the catalog.")

        t_dataset = st.selectbox("Dataset", catalog_names(), key="tr_dataset")
        if t_dataset:
            df = st.session_state.catalog[t_dataset]
            numeric_cols = get_numeric_columns(df)

            t_cols = st.multiselect("Series", numeric_cols, default=numeric_cols[:3], key="tr_cols")

            tc1, tc2, tc3 = st.columns(3)
            with tc1:
                do_yoy = st.checkbox("Year-over-Year %", key="tr_yoy")
            with tc2:
                do_mom = st.checkbox("Month-over-Month %", key="tr_mom")
            with tc3:
                do_ma = st.checkbox("Rolling Mean", key="tr_ma")
                if do_ma:
                    tr_ma_window = st.number_input("Window", 2, 120, 12, key="tr_ma_win")

            new_name = st.text_input(
                "Save as (catalog name)",
                value=f"{t_dataset}_transformed",
                key="tr_new_name",
            )

            if st.button("Apply & Save", key="tr_apply", use_container_width=True):
                if not t_cols:
                    st.warning("Select at least one series.")
                else:
                    parts = []
                    for col in t_cols:
                        s = df[col].dropna()
                        if do_yoy:
                            parts.append(year_over_year(s))
                        if do_mom:
                            parts.append(month_over_month(s))
                        if do_ma:
                            parts.append(rolling_mean(s, int(tr_ma_window)))
                        if not (do_yoy or do_mom or do_ma):
                            parts.append(s)

                    new_df = pd.concat(parts, axis=1)
                    add_to_catalog(new_name, new_df)
                    st.success(f"Saved **{new_name}** to catalog ({len(new_df.columns)} series).")
                    st.dataframe(new_df.tail(8), use_container_width=True)

    # ── Summary Stats ─────────────────────────────────────────────────────────
    with tab_stats:
        st.subheader("Summary Statistics")

        stat_datasets = st.multiselect(
            "Select datasets",
            options=catalog_names(),
            default=catalog_names()[:2],
            key="stat_datasets",
        )

        if stat_datasets:
            merged = get_merged_df(stat_datasets)
            stats = summary_statistics(merged)
            if stats.empty:
                st.info("No numeric data found.")
            else:
                st.dataframe(stats, use_container_width=True)

                # Download
                csv = stats.to_csv()
                st.download_button(
                    "Download CSV",
                    data=csv,
                    file_name="summary_statistics.csv",
                    mime="text/csv",
                )
        else:
            st.info("Select at least one dataset.")


# =============================================================================
# PAGE: DATA TABLE
# =============================================================================

elif page == "Data Table":
    st.title("Data Table")

    if not st.session_state.catalog:
        st.info("No data loaded yet. Go to **Data Sources** to load some datasets.")
        st.stop()

    selected = st.selectbox("Dataset", catalog_names(), key="dt_selected")

    if selected:
        df = st.session_state.catalog[selected]

        # Header metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Rows", f"{len(df):,}")
        c2.metric("Columns", f"{len(df.columns)}")
        if isinstance(df.index, pd.DatetimeIndex) and len(df) > 0:
            c3.metric("Date Range", f"{df.index.min().date()} → {df.index.max().date()}")

        st.markdown("---")

        # Column filter
        all_cols = list(df.columns)
        show_cols = st.multiselect(
            "Show columns",
            options=all_cols,
            default=all_cols[:10] if len(all_cols) > 10 else all_cols,
            key="dt_cols",
        )

        if show_cols:
            view_df = df[show_cols]
        else:
            view_df = df

        # Date range filter
        if isinstance(df.index, pd.DatetimeIndex) and len(df) > 0:
            col_a, col_b = st.columns(2)
            with col_a:
                d_start = st.date_input(
                    "From",
                    value=df.index.min().date(),
                    key="dt_start",
                )
            with col_b:
                d_end = st.date_input(
                    "To",
                    value=df.index.max().date(),
                    key="dt_end",
                )
            view_df = view_df.loc[
                (view_df.index >= pd.Timestamp(d_start)) &
                (view_df.index <= pd.Timestamp(d_end))
            ]

        st.dataframe(view_df, use_container_width=True, height=500)

        # Remove from catalog
        col_dl, col_rm = st.columns([3, 1])
        with col_dl:
            csv = view_df.to_csv()
            st.download_button(
                "Download CSV",
                data=csv,
                file_name=f"{selected}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col_rm:
            if st.button("Remove from catalog", use_container_width=True, key="dt_remove"):
                del st.session_state.catalog[selected]
                st.rerun()


# =============================================================================
# PAGE: TAG MANAGER
# =============================================================================

elif page == "Tag Manager":
    render_tag_manager()
