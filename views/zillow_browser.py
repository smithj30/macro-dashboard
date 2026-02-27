"""
Zillow Data Browser — browse, download, and load Zillow Research datasets.
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from modules.data_ingestion.zillow_registry import (
    get_registry,
    get_categories,
    get_by_category,
)
from modules.data_ingestion.zillow_loader import (
    download_datasets,
    get_cached_datasets,
    load_zillow_csv,
    get_region_series,
    load_zillow_series,
    _any_cache_stale,
    _latest_download_date,
    _DEFAULT_CACHE_DIR,
)


def _init_state():
    """Initialise Zillow Browser session state keys."""
    if "zb_selected" not in st.session_state:
        st.session_state.zb_selected = set()
    if "zb_downloaded" not in st.session_state:
        st.session_state.zb_downloaded = set()
    if "zb_preview_entry" not in st.session_state:
        st.session_state.zb_preview_entry = None


def render():
    """Main render function for the Zillow Data Browser page."""
    _init_state()

    st.title("Zillow Data Browser")

    # Info banner
    latest = _latest_download_date()
    if latest:
        st.info(
            f"Zillow data updates monthly around the 16th. "
            f"Last download: {latest[:10]}"
        )
    else:
        st.info("Zillow data updates monthly around the 16th. No cached data yet.")

    if _any_cache_stale():
        st.warning(
            "Some cached datasets may be stale (downloaded before this month's update). "
            "Use **Refresh All Cached** to re-download."
        )

    registry = get_registry()

    # ── Category Expanders ────────────────────────────────────────────────────
    st.subheader("Datasets")

    categories = get_categories()
    for cat in categories:
        entries = get_by_category(cat)
        with st.expander(f"{cat} ({len(entries)} datasets)"):
            for entry in entries:
                key = f"zb_cb_{entry['id']}"
                checked = entry["id"] in st.session_state.zb_selected
                # Show verified badge
                badge = "" if entry.get("verified") else " (unverified URL)"
                if st.checkbox(
                    f"{entry['label']}{badge}",
                    value=checked,
                    key=key,
                    help=entry.get("notes", ""),
                ):
                    st.session_state.zb_selected.add(entry["id"])
                else:
                    st.session_state.zb_selected.discard(entry["id"])

    # ── Action Bar ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Actions")

    col_dl, col_refresh, col_clear, col_count = st.columns([2, 2, 2, 3])

    with col_count:
        n_sel = len(st.session_state.zb_selected)
        st.caption(f"{n_sel} dataset(s) selected")

    with col_dl:
        dl_clicked = st.button(
            "Download Selected",
            disabled=n_sel == 0,
            use_container_width=True,
        )

    with col_refresh:
        refresh_clicked = st.button(
            "Refresh All Cached",
            use_container_width=True,
        )

    with col_clear:
        clear_clicked = st.button(
            "Clear Cache",
            use_container_width=True,
        )

    # ── Download Selected ─────────────────────────────────────────────────────
    if dl_clicked and n_sel > 0:
        selected_entries = [
            e for e in registry if e["id"] in st.session_state.zb_selected
        ]
        progress_bar = st.progress(0, text="Downloading...")

        def _progress(i, total):
            progress_bar.progress(i / total, text=f"Downloading {i}/{total}...")

        results = download_datasets(
            selected_entries,
            cache_dir=_DEFAULT_CACHE_DIR,
            progress_callback=_progress,
        )
        progress_bar.empty()

        successes = [r for r in results if r["success"]]
        failures = [r for r in results if not r["success"]]
        for r in successes:
            st.session_state.zb_downloaded.add(r["entry"]["filename"])
        if successes:
            st.success(f"Downloaded {len(successes)} dataset(s) successfully.")
        for r in failures:
            st.warning(f"Failed: {r['entry']['label']} — {r['error']}")

    # ── Refresh All Cached ────────────────────────────────────────────────────
    if refresh_clicked:
        cached = get_cached_datasets(_DEFAULT_CACHE_DIR)
        if not cached:
            st.info("No cached datasets to refresh.")
        else:
            # Find registry entries matching cached files
            filename_to_entry = {e["filename"] + ".csv": e for e in registry}
            entries_to_refresh = []
            for c in cached:
                entry = filename_to_entry.get(c["filename"])
                if entry:
                    entries_to_refresh.append(entry)

            if entries_to_refresh:
                # Clear Streamlit cache for these URLs so they re-download
                from modules.data_ingestion.zillow_loader import download_zillow_csv
                download_zillow_csv.clear()

                progress_bar = st.progress(0, text="Refreshing...")

                def _progress(i, total):
                    progress_bar.progress(i / total, text=f"Refreshing {i}/{total}...")

                results = download_datasets(
                    entries_to_refresh,
                    cache_dir=_DEFAULT_CACHE_DIR,
                    progress_callback=_progress,
                )
                progress_bar.empty()
                successes = [r for r in results if r["success"]]
                failures = [r for r in results if not r["success"]]
                if successes:
                    st.success(f"Refreshed {len(successes)} dataset(s).")
                for r in failures:
                    st.warning(f"Failed: {r['entry']['label']} — {r['error']}")

    # ── Clear Cache ───────────────────────────────────────────────────────────
    if clear_clicked:
        if os.path.isdir(_DEFAULT_CACHE_DIR):
            import shutil
            for fname in os.listdir(_DEFAULT_CACHE_DIR):
                fpath = os.path.join(_DEFAULT_CACHE_DIR, fname)
                if fname == ".gitkeep":
                    continue
                if os.path.isfile(fpath):
                    os.remove(fpath)
            st.session_state.zb_downloaded.clear()
            # Clear the download cache too
            from modules.data_ingestion.zillow_loader import download_zillow_csv
            download_zillow_csv.clear()
            st.success("Cache cleared.")

    # ── Cached Datasets List ──────────────────────────────────────────────────
    cached = get_cached_datasets(_DEFAULT_CACHE_DIR)
    if cached:
        st.markdown("---")
        st.subheader("Cached Datasets")
        st.caption(f"{len(cached)} dataset(s) in cache")

        # Build lookup from filename to registry entry
        filename_to_entry = {e["filename"] + ".csv": e for e in registry}

        # Dropdown to select dataset for preview
        cached_labels = []
        cached_map = {}
        for c in cached:
            entry = filename_to_entry.get(c["filename"])
            label = entry["label"] if entry else c["filename"]
            size_mb = c["size_bytes"] / (1024 * 1024)
            display = f"{label} ({size_mb:.1f} MB, downloaded {c['downloaded_at'][:10]})"
            cached_labels.append(display)
            cached_map[display] = (c, entry)

        selected_label = st.selectbox(
            "Select a dataset to preview",
            cached_labels,
            index=0,
        )

        if selected_label:
            cached_info, entry = cached_map[selected_label]
            csv_path = os.path.join(_DEFAULT_CACHE_DIR, cached_info["filename"])

            # Load and preview
            try:
                zillow_data = load_zillow_csv(csv_path)
                wide_df = zillow_data["wide"]
                regions = zillow_data["regions"]
                date_cols = zillow_data["date_columns"]

                # Summary stats
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Rows", f"{len(wide_df):,}")
                with c2:
                    st.metric("Regions", f"{len(regions):,}")
                with c3:
                    if date_cols:
                        st.metric(
                            "Date Range",
                            f"{date_cols[0]} — {date_cols[-1]}",
                        )

                # Sample data
                with st.expander("Sample data (first 10 rows)"):
                    st.dataframe(wide_df.head(10), use_container_width=True)

                # ── Load to Catalog ───────────────────────────────────────────
                st.markdown("#### Load to Catalog")

                selected_regions = st.multiselect(
                    "Select regions to load",
                    regions,
                    default=regions[:5] if len(regions) > 5 else regions,
                    help="Pick which regions to include as columns",
                )

                prefix = st.text_input(
                    "Dataset name prefix",
                    value="Zillow",
                    help="Prefix for the catalog key",
                )

                if st.button(
                    "Load to Catalog",
                    disabled=len(selected_regions) == 0,
                    use_container_width=True,
                    type="primary",
                ):
                    if entry:
                        catalog_key = (
                            f"{prefix} — {entry['label']}"
                        )
                    else:
                        catalog_key = f"{prefix} — {cached_info['filename']}"

                    merged_df = load_zillow_series(
                        entry,
                        regions=selected_regions,
                        cache_dir=_DEFAULT_CACHE_DIR,
                    ) if entry else _load_from_path(csv_path, selected_regions)

                    if not merged_df.empty:
                        st.session_state.catalog[catalog_key] = merged_df
                        st.success(
                            f"Loaded **{catalog_key}** to catalog "
                            f"({len(merged_df):,} rows, {len(merged_df.columns)} regions)"
                        )
                    else:
                        st.error("No data found for selected regions.")

            except Exception as exc:
                st.error(f"Error loading CSV: {exc}")


def _load_from_path(csv_path: str, regions: list) -> pd.DataFrame:
    """Fallback: load from a CSV path without a registry entry."""
    zillow_data = load_zillow_csv(csv_path)
    dfs = []
    for region in regions:
        if region in zillow_data["regions"]:
            dfs.append(get_region_series(zillow_data, region))
    if not dfs:
        return pd.DataFrame()
    merged = dfs[0]
    for df in dfs[1:]:
        merged = merged.join(df, how="outer")
    return merged
