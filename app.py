"""
Macro Dashboard — main Streamlit entry point.

Run with:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np

# ── Module imports ────────────────────────────────────────────────────────────
from modules.data_ingestion.fred_loader import (
    get_fred_client,
    search_fred,
    load_fred_series,
    get_series_info,
)
from modules.data_ingestion.file_loader import load_uploaded_file
from modules.data_ingestion.web_scraper import scrape_table, scrape_tables
from modules.data_ingestion.zillow_loader import load_zillow_csv, get_region_series

from modules.data_processing.transforms import (
    year_over_year,
    month_over_month,
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
    correlation_heatmap,
    scatter_chart,
    rolling_corr_chart,
    residual_plot,
    residual_histogram,
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
    .metric-card {
        background: #f8f9fa;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 4px 0;
    }
    h1 { font-size: 1.8rem !important; }
    h2 { font-size: 1.3rem !important; border-bottom: 1px solid #e0e0e0; padding-bottom: 4px; }
    h3 { font-size: 1.1rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state initialisation ──────────────────────────────────────────────

if "catalog" not in st.session_state:
    # catalog: dict[str, pd.DataFrame]  — name → DataFrame with DatetimeIndex
    st.session_state.catalog = {}

if "zillow_cache" not in st.session_state:
    # For Zillow data that needs region selection after loading
    st.session_state.zillow_cache = None


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
    page = st.radio(
        "Navigate",
        ["Data Sources", "Chart Builder", "Regression & Analysis", "Data Table"],
        label_visibility="collapsed",
    )
    st.markdown("---")

    # Catalog summary
    st.markdown("**Loaded Datasets**")
    if st.session_state.catalog:
        for name, df in st.session_state.catalog.items():
            st.markdown(
                f"- `{name}` — {len(df):,} rows, {len(df.columns)} col(s)"
            )
        if st.button("Clear All Data", use_container_width=True):
            st.session_state.catalog = {}
            st.session_state.zillow_cache = None
            st.rerun()
    else:
        st.caption("No datasets loaded yet.")

    st.markdown("---")
    st.caption("Built with Streamlit · Plotly · FRED API")


# =============================================================================
# PAGE: DATA SOURCES
# =============================================================================

if page == "Data Sources":
    st.title("Data Sources")
    st.markdown("Load data from FRED, file uploads, web scraping, or Zillow CSVs.")

    tab_fred, tab_file, tab_web, tab_zillow = st.tabs(
        ["🏦 FRED", "📁 File Upload", "🌐 Web Scraper", "🏠 Zillow"]
    )

    # ── FRED ─────────────────────────────────────────────────────────────────
    with tab_fred:
        st.subheader("FRED API")

        _, err = get_fred_client()
        if err:
            st.warning(
                f"**FRED API key not configured.**\n\n{err}\n\n"
                "Copy `.env.example` to `.env` and add your key."
            )

        col1, col2 = st.columns([3, 1])
        with col1:
            search_query = st.text_input(
                "Search FRED",
                placeholder="e.g. unemployment rate, CPI, GDP…",
                key="fred_search_query",
            )
        with col2:
            search_limit = st.number_input("Results", min_value=5, max_value=100, value=20, step=5)

        if st.button("Search", key="fred_search_btn", use_container_width=True):
            if not search_query:
                st.warning("Enter a search term.")
            else:
                with st.spinner("Searching FRED…"):
                    try:
                        results = search_fred(search_query, limit=search_limit)
                        if results.empty:
                            st.info("No results found.")
                        else:
                            st.session_state["fred_search_results"] = results
                    except Exception as e:
                        st.error(f"Search failed: {e}")

        if "fred_search_results" in st.session_state:
            results = st.session_state["fred_search_results"]
            st.markdown(f"**{len(results)} result(s):**")
            st.dataframe(results, use_container_width=True, height=250)

        st.markdown("---")
        st.markdown("**Load a Series by ID**")

        col_a, col_b, col_c = st.columns([2, 1, 1])
        with col_a:
            series_id = st.text_input(
                "Series ID",
                placeholder="e.g. UNRATE, CPIAUCSL, GDP",
                key="fred_series_id",
            ).strip().upper()
        with col_b:
            start_date = st.date_input("Start date", value=None, key="fred_start")
        with col_c:
            end_date = st.date_input("End date", value=None, key="fred_end")

        custom_name = st.text_input(
            "Dataset name (optional)",
            placeholder="Leave blank to use Series ID",
            key="fred_name",
        ).strip()

        if st.button("Load Series", key="fred_load_btn", use_container_width=True):
            if not series_id:
                st.warning("Enter a Series ID.")
            else:
                with st.spinner(f"Loading {series_id}…"):
                    try:
                        df = load_fred_series(
                            series_id,
                            start_date=str(start_date) if start_date else None,
                            end_date=str(end_date) if end_date else None,
                        )
                        name = custom_name or series_id
                        add_to_catalog(name, df)
                        st.success(f"Loaded **{name}** — {len(df):,} observations.")

                        # Show info
                        try:
                            info = get_series_info(series_id)
                            if info:
                                title = info.get("title", "")
                                units = info.get("units", "")
                                freq = info.get("frequency", "")
                                st.caption(f"{title} | {units} | {freq}")
                        except Exception:
                            pass

                        st.line_chart(df)
                    except Exception as e:
                        st.error(f"Failed to load series: {e}")

    # ── File Upload ──────────────────────────────────────────────────────────
    with tab_file:
        st.subheader("CSV / Excel Upload")

        uploaded = st.file_uploader(
            "Upload a CSV or Excel file",
            type=["csv", "xlsx", "xls"],
            key="file_uploader",
        )

        if uploaded:
            col1, col2 = st.columns([3, 1])
            with col1:
                file_name = st.text_input(
                    "Dataset name",
                    value=uploaded.name.rsplit(".", 1)[0],
                    key="file_name",
                )

            if st.button("Load File", key="file_load_btn", use_container_width=True):
                with st.spinner("Parsing file…"):
                    try:
                        df, msg = load_uploaded_file(uploaded)
                        add_to_catalog(file_name, df)
                        st.success(f"Loaded **{file_name}** — {len(df):,} rows, {len(df.columns)} columns.")
                        st.caption(msg)
                        st.dataframe(df.head(10), use_container_width=True)
                    except Exception as e:
                        st.error(f"Failed to load file: {e}")

    # ── Web Scraper ──────────────────────────────────────────────────────────
    with tab_web:
        st.subheader("Web Table Scraper")
        st.caption("Scrapes HTML `<table>` elements from a public URL.")

        url = st.text_input(
            "URL",
            placeholder="https://example.com/data-page",
            key="scraper_url",
        )

        col1, col2 = st.columns([1, 2])
        with col1:
            table_idx = st.number_input("Table index (0 = first)", min_value=0, value=0, key="scraper_idx")
        with col2:
            scraper_name = st.text_input(
                "Dataset name",
                value="scraped_table",
                key="scraper_name",
            )

        if st.button("Scrape", key="scraper_btn", use_container_width=True):
            if not url:
                st.warning("Enter a URL.")
            else:
                with st.spinner("Fetching page…"):
                    try:
                        # First pass: get table count
                        tables = scrape_tables(url)
                        st.info(f"Found {len(tables)} table(s) on the page.")

                        df, msg = scrape_table(url, table_index=int(table_idx))
                        add_to_catalog(scraper_name, df)
                        st.success(f"Loaded **{scraper_name}** — {len(df):,} rows.")
                        st.caption(msg)
                        st.dataframe(df.head(10), use_container_width=True)
                    except Exception as e:
                        st.error(f"Scraping failed: {e}")

    # ── Zillow ────────────────────────────────────────────────────────────────
    with tab_zillow:
        st.subheader("Zillow Data")
        st.caption(
            "Upload a Zillow public CSV export (ZHVI, ZORI, etc.). "
            "Download from [zillow.com/research/data](https://www.zillow.com/research/data/)."
        )

        zillow_file = st.file_uploader(
            "Upload Zillow CSV",
            type=["csv"],
            key="zillow_uploader",
        )

        value_col_name = st.text_input(
            "Value column label",
            value="value",
            key="zillow_value_col",
        )

        if st.button("Parse Zillow File", key="zillow_parse_btn", use_container_width=True):
            if not zillow_file:
                st.warning("Upload a Zillow CSV first.")
            else:
                with st.spinner("Parsing Zillow CSV…"):
                    try:
                        data = load_zillow_csv(zillow_file, value_col_name=value_col_name)
                        st.session_state.zillow_cache = data
                        st.success(
                            f"Parsed {len(data['wide']):,} regions × "
                            f"{len(data['date_columns'])} time periods."
                        )
                    except Exception as e:
                        st.error(f"Failed to parse: {e}")

        if st.session_state.zillow_cache:
            data = st.session_state.zillow_cache
            regions = data["regions"]

            selected_regions = st.multiselect(
                "Select regions to add to catalog",
                options=regions,
                default=regions[:3] if len(regions) >= 3 else regions,
                key="zillow_regions",
            )

            zillow_prefix = st.text_input(
                "Name prefix for catalog entries",
                value="Zillow",
                key="zillow_prefix",
            )

            if st.button("Add to Catalog", key="zillow_add_btn", use_container_width=True):
                if not selected_regions:
                    st.warning("Select at least one region.")
                else:
                    added = []
                    for region in selected_regions:
                        series_df = get_region_series(data, region, value_col=value_col_name)
                        entry_name = f"{zillow_prefix} — {region}"
                        add_to_catalog(entry_name, series_df)
                        added.append(entry_name)
                    st.success(f"Added {len(added)} region(s) to catalog.")


# =============================================================================
# PAGE: CHART BUILDER
# =============================================================================

elif page == "Chart Builder":
    st.title("Chart Builder")

    if not st.session_state.catalog:
        st.info("No data loaded yet. Go to **Data Sources** to load some datasets.")
        st.stop()

    chart_type = st.selectbox(
        "Chart type",
        ["Time Series", "Correlation Heatmap", "Scatter Plot"],
        key="chart_type",
    )

    st.markdown("---")

    # ── Time Series ──────────────────────────────────────────────────────────
    if chart_type == "Time Series":
        st.subheader("Time Series")

        selected_datasets = st.multiselect(
            "Select datasets",
            options=catalog_names(),
            default=catalog_names()[:2],
            key="ts_datasets",
        )

        if not selected_datasets:
            st.info("Select at least one dataset.")
            st.stop()

        merged = get_merged_df(selected_datasets)
        numeric_cols = get_numeric_columns(merged)

        if not numeric_cols:
            st.warning("No numeric columns found in the selected datasets.")
            st.stop()

        col1, col2 = st.columns([3, 1])
        with col1:
            selected_cols = st.multiselect(
                "Series to plot",
                options=numeric_cols,
                default=numeric_cols[:4],
                key="ts_cols",
            )
        with col2:
            dual_axis = st.selectbox(
                "Dual y-axis series",
                options=["(none)"] + (selected_cols or []),
                key="ts_dual",
            )

        # Transforms
        with st.expander("Transforms (optional)"):
            apply_yoy = st.checkbox("Year-over-Year %", key="ts_yoy")
            apply_mom = st.checkbox("Month-over-Month %", key="ts_mom")
            apply_ma = st.checkbox("Rolling Mean", key="ts_ma")
            if apply_ma:
                ma_window = st.slider("MA window (periods)", 2, 120, 12, key="ts_ma_window")

        chart_title = st.text_input(
            "Chart title",
            value="Time Series",
            key="ts_title",
        )

        if st.button("Build Chart", key="ts_build", use_container_width=True) or True:
            if not selected_cols:
                st.info("Select at least one series to plot.")
            else:
                plot_df = merged[selected_cols].copy()

                # Apply transforms to each column
                transformed_parts = []
                for col in selected_cols:
                    s = plot_df[col].dropna()
                    parts = [s]
                    if apply_yoy:
                        parts.append(year_over_year(s))
                    if apply_mom:
                        parts.append(month_over_month(s))
                    if apply_ma:
                        parts.append(rolling_mean(s, ma_window))
                    transformed_parts.extend(parts)

                if apply_yoy or apply_mom or apply_ma:
                    plot_df = pd.concat(transformed_parts, axis=1)

                dual_col = None if dual_axis == "(none)" else dual_axis

                fig = time_series_chart(
                    plot_df,
                    title=chart_title,
                    dual_axis_col=dual_col,
                )
                st.plotly_chart(fig, use_container_width=True)

    # ── Correlation Heatmap ──────────────────────────────────────────────────
    elif chart_type == "Correlation Heatmap":
        st.subheader("Correlation Heatmap")

        selected_datasets = st.multiselect(
            "Select datasets",
            options=catalog_names(),
            default=catalog_names()[:3],
            key="heat_datasets",
        )

        if not selected_datasets:
            st.info("Select at least two datasets.")
            st.stop()

        merged = get_merged_df(selected_datasets)
        numeric_cols = get_numeric_columns(merged)

        selected_cols = st.multiselect(
            "Series to include",
            options=numeric_cols,
            default=numeric_cols[:8],
            key="heat_cols",
        )

        corr_method = st.selectbox("Method", ["pearson", "spearman", "kendall"], key="heat_method")

        if selected_cols and len(selected_cols) >= 2:
            sub = merged[selected_cols].dropna()
            corr = sub.corr(method=corr_method)
            fig = correlation_heatmap(corr, title=f"{corr_method.title()} Correlation Matrix")
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("Show correlation table"):
                st.dataframe(corr.round(4), use_container_width=True)
        else:
            st.info("Select at least two series.")

    # ── Scatter Plot ─────────────────────────────────────────────────────────
    elif chart_type == "Scatter Plot":
        st.subheader("Scatter Plot")

        selected_datasets = st.multiselect(
            "Select datasets",
            options=catalog_names(),
            default=catalog_names()[:2],
            key="scatter_datasets",
        )

        if not selected_datasets:
            st.info("Select at least one dataset.")
            st.stop()

        merged = get_merged_df(selected_datasets)
        numeric_cols = get_numeric_columns(merged)

        if len(numeric_cols) < 2:
            st.warning("Need at least two numeric columns.")
            st.stop()

        col1, col2 = st.columns(2)
        with col1:
            x_col = st.selectbox("X-axis", options=numeric_cols, index=0, key="scatter_x")
        with col2:
            y_col = st.selectbox("Y-axis", options=numeric_cols, index=min(1, len(numeric_cols) - 1), key="scatter_y")

        col3, col4 = st.columns(2)
        with col3:
            add_trendline = st.checkbox("Add trendline", value=True, key="scatter_trend")
        with col4:
            color_by_date = st.checkbox("Colour by date", value=True, key="scatter_color")

        if x_col and y_col and x_col != y_col:
            fig = scatter_chart(
                merged[x_col],
                merged[y_col],
                add_trendline=add_trendline,
                color_by_date=color_by_date,
            )
            st.plotly_chart(fig, use_container_width=True)

            # Quick correlation readout
            combined = pd.concat([merged[x_col], merged[y_col]], axis=1).dropna()
            if len(combined) > 2:
                r = combined.iloc[:, 0].corr(combined.iloc[:, 1])
                st.metric("Pearson r", f"{r:.4f}")
        else:
            st.info("Select two different series.")


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
