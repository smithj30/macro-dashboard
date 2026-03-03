# Macro Dashboard v2 — Functional Specification

## 1. Product Overview

### 1.1 Purpose

A macroeconomic research dashboard for a small investment team (2–5 people). The app provides a structured pipeline: **Data Sources → Data Feeds → Charts → Dashboards**. Users register data sources once, compose them into reusable charts, and assemble charts into dashboards that auto-refresh with the latest data.

### 1.2 Design Philosophy

- **Three-layer catalog architecture**: Data Feeds, Charts, and Dashboards are each stored as portable JSON configs. Every object is created in the UI but lives on disk as an editable file.
- **Convention over configuration**: sensible defaults so that the common case (plot a FRED series over time) requires minimal clicks.
- **Config-first durability**: the UI writes JSON; the JSON drives rendering. If the UI breaks, a user can hand-edit a JSON file and reload. If the user wants to bulk-create charts, they can duplicate and edit JSON configs directly.

### 1.3 Users & Deployment

- **Users**: Small team, shared view (no per-user auth or personalization).
- **Deployment**: Local development on a Mac Studio; remote team access via ngrok, Tailscale, or cloud deployment. The app should be stateless enough to run behind any reverse proxy.

### 1.4 Framework Recommendation

**Stay on Streamlit.** Rationale:

- The existing app is already Streamlit-based with working data loaders, transforms, and visualization code.
- The team is small and the build/edit cadence is weekly — Streamlit's rapid prototyping model fits this well.
- A React rewrite would cost months for marginal UX gain at this team size.
- Streamlit 1.x supports `st.columns`, custom components, and session state, which are sufficient for the side-by-side chart editor layout.

The spec below is Streamlit-native but architecturally clean enough that the rendering layer could be swapped later if needed.

---

## 2. Architecture

### 2.1 Conceptual Model

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Data Source  │────▶│  Data Feed  │────▶│    Chart    │────▶│  Dashboard  │
│  (provider)  │     │ (series)    │     │ (visual)    │     │  (layout)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
   Registered          Configured          Configured          Assembled
   in registry         in catalog          in catalog          in catalog
```

**Data Source**: A registered provider (FRED API, BEA API, Zillow CSV endpoint, RSS feed, uploaded file). Defines *how* to connect and fetch. Stored as provider plugins, not per-series configs.

**Data Feed**: A specific series or dataset retrieved from a Data Source. For example, "FRED → UNRATE" or "Zillow → ZHVI All Homes, Metro, Smoothed SA". Each feed has a unique key, metadata, and a refresh schedule. Stored in `catalogs/feeds.json`.

**Chart**: A visualization that references one or more Data Feeds, applies optional transforms, and defines chart type and display options. Stored in `catalogs/charts.json`.

**Dashboard**: A named layout of Charts (and optionally standalone metric cards or news widgets) arranged in a grid. Stored in `catalogs/dashboards/{name}.json`.

### 2.2 Directory Structure

```
macro-dashboard/
├── app.py                          # Entry point, sidebar nav, session bootstrap
├── config/
│   └── app_config.yaml             # Global settings (API keys, refresh schedule, paths)
│
├── catalogs/
│   ├── feeds.json                  # All registered data feeds
│   ├── charts.json                 # All chart definitions
│   └── dashboards/
│       ├── reindustrialization.json # Pre-built template dashboard
│       └── housing.json            # User-created dashboard
│
├── data/
│   ├── cache/                      # Cached API responses and downloaded CSVs
│   │   ├── fred/
│   │   ├── bea/
│   │   ├── zillow/
│   │   └── files/
│   └── refresh_log.json            # Tracks last refresh time per feed
│
├── providers/                      # Data source provider plugins
│   ├── base.py                     # Abstract base class for providers
│   ├── fred_provider.py            # FRED API provider
│   ├── bea_provider.py             # BEA API provider
│   ├── zillow_provider.py          # Zillow CSV provider (with registry)
│   ├── file_provider.py            # Uploaded CSV/Excel file provider
│   └── news_provider.py            # RSS/news feed provider
│
├── transforms/                     # Data transforms (pure functions)
│   ├── time_series.py              # YoY, MoM, rolling avg, indexing
│   ├── correlation.py              # Correlation matrix, rolling correlation
│   └── recession.py                # NBER recession date ranges
│
├── views/                          # Streamlit pages
│   ├── dashboard_viewer.py         # Renders a dashboard from its JSON config
│   ├── chart_editor.py             # Side-by-side chart builder/editor
│   ├── feed_manager.py             # Browse, add, preview, refresh data feeds
│   ├── dashboard_builder.py        # Assemble charts into dashboard layouts
│   └── data_explorer.py            # Ad-hoc data exploration (optional)
│
├── components/                     # Reusable Streamlit UI components
│   ├── chart_renderer.py           # Renders a chart config → Plotly figure
│   ├── metric_card.py              # Single-value metric card with delta
│   ├── news_widget.py              # News/RSS display component
│   └── feed_picker.py              # Reusable feed selection widget
│
└── scripts/
    └── refresh.py                  # CLI script for scheduled data refresh (cron)
```

### 2.3 Persistence & Storage

All persistence is local files:

| What | Format | Location |
|------|--------|----------|
| Feed catalog | JSON | `catalogs/feeds.json` |
| Chart catalog | JSON | `catalogs/charts.json` |
| Dashboard configs | JSON | `catalogs/dashboards/*.json` |
| App settings | YAML | `config/app_config.yaml` |
| Cached data | Parquet | `data/cache/{provider}/{key}.parquet` |
| Refresh log | JSON | `data/refresh_log.json` |

**Why Parquet for cache?** Efficient columnar storage, preserves dtypes (especially dates), fast to read with pandas, and smaller than CSV for wide time-series data. The Zillow ZIP-code file drops from ~50MB CSV to ~10MB Parquet.

**Why JSON for configs?** Human-readable and hand-editable, which is core to the hybrid workflow. Users can open `charts.json` in any text editor.

---

## 3. Data Model — JSON Schemas

### 3.1 Data Feed

```json
{
  "feed_id": "fred_unrate",
  "provider": "fred",
  "name": "Unemployment Rate",
  "description": "Civilian unemployment rate, seasonally adjusted",
  "params": {
    "series_id": "UNRATE"
  },
  "frequency": "monthly",
  "dimensions": {
    "geography": null,
    "segment": null
  },
  "refresh_schedule": "daily",
  "tags": ["labor", "employment"],
  "created_at": "2026-02-27T10:00:00Z",
  "updated_at": "2026-02-27T10:00:00Z"
}
```

Provider-specific `params` examples:

```json
// FRED
{ "series_id": "UNRATE" }

// BEA
{ "table_name": "T10101", "line_number": 1, "dataset": "NIPA" }

// Zillow
{
  "metric_key": "zhvi",
  "filename": "Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv",
  "url": "https://files.zillowstatic.com/research/public_csvs/zhvi/Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv",
  "regions": ["New York, NY", "Los Angeles-Long Beach-Anaheim, CA"]
}

// RSS/News
{ "feed_url": "https://www.federalreserve.gov/feeds/press_all.xml" }

// Uploaded file
{ "file_path": "data/cache/files/custom_data.csv", "date_column": "Date", "value_column": "Value" }
```

**Dimensions**: Feeds that span multiple geographies (Zillow, BEA) or segments store available dimension values in cached metadata. The `params` may include filters (e.g., specific regions), or the full dataset can be cached and filtered at chart render time.

### 3.2 Chart

```json
{
  "chart_id": "unemployment_vs_claims",
  "name": "Unemployment Rate vs. Initial Claims",
  "chart_type": "time_series",
  "feeds": [
    {
      "feed_id": "fred_unrate",
      "label": "Unemployment Rate (%)",
      "axis": "left",
      "color": "#1f77b4",
      "transform": null
    },
    {
      "feed_id": "fred_icsa",
      "label": "Initial Claims (thousands)",
      "axis": "right",
      "color": "#ff7f0e",
      "transform": {
        "type": "rolling_avg",
        "window": 4
      }
    }
  ],
  "options": {
    "title": "Labor Market Overview",
    "date_range": { "start": "2019-01-01", "end": null },
    "recession_shading": true,
    "show_legend": true,
    "height": 450,
    "annotations": []
  },
  "tags": ["labor", "weekly"],
  "created_at": "2026-02-27T10:00:00Z",
  "updated_at": "2026-02-27T10:00:00Z"
}
```

**Supported `chart_type` values:**

| Type | Description | Feed Requirements |
|------|-------------|-------------------|
| `time_series` | Line chart over time, dual-axis support | 1+ feeds, each with a time dimension |
| `bar` | Vertical or horizontal bar chart | 1+ feeds; can be time-based or categorical |
| `metric_card` | Single latest value with period-over-period delta | Exactly 1 feed |
| `heatmap` | Correlation matrix or calendar heatmap | 2+ feeds (correlation) or 1 feed (calendar) |
| `table` | Tabular data display with optional sparklines | 1+ feeds |

**Supported `transform` types:**

| Transform | Params | Description |
|-----------|--------|-------------|
| `yoy_pct` | — | Year-over-year percent change |
| `mom_pct` | — | Month-over-month percent change |
| `rolling_avg` | `window` (int) | Rolling mean over N periods |
| `index_to_date` | `base_date` (str) | Normalize series to 100 at the given date |
| `diff` | — | First difference |
| `cumulative` | — | Cumulative sum from start |
| `log` | — | Natural log |

### 3.3 Dashboard

```json
{
  "dashboard_id": "reindustrialization",
  "name": "US Reindustrialization Tracker",
  "description": "Key metrics tracking the US manufacturing and industrial renaissance",
  "layout": [
    {
      "row": 1,
      "items": [
        { "type": "chart", "chart_id": "manufacturing_employment", "width": 6 },
        { "type": "chart", "chart_id": "construction_spending", "width": 6 }
      ]
    },
    {
      "row": 2,
      "items": [
        { "type": "chart", "chart_id": "ism_pmi_card", "width": 3 },
        { "type": "chart", "chart_id": "industrial_production_card", "width": 3 },
        { "type": "chart", "chart_id": "capacity_utilization_card", "width": 3 },
        { "type": "chart", "chart_id": "durable_goods_card", "width": 3 }
      ]
    },
    {
      "row": 3,
      "items": [
        { "type": "chart", "chart_id": "manufacturing_correlation_heatmap", "width": 8 },
        { "type": "news", "config": { "feed_id": "rss_fed_releases", "max_items": 5 }, "width": 4 }
      ]
    }
  ],
  "auto_refresh": true,
  "tags": ["manufacturing", "industrial"],
  "created_at": "2026-02-27T10:00:00Z",
  "updated_at": "2026-02-27T10:00:00Z"
}
```

**Layout rules:**
- Each row is a list of items.
- `width` values are based on a 12-column grid (maps to Streamlit columns).
- Widths within a row must sum to 12.
- Item `type` is `chart` (references a chart_id) or `news` (inline config for a news widget).

---

## 4. Provider System

### 4.1 Base Provider Interface

Every data source provider implements a common interface:

```python
class BaseProvider(ABC):
    """Abstract base class for data source providers."""

    @abstractmethod
    def get_provider_id(self) -> str:
        """Return unique provider identifier, e.g., 'fred', 'bea', 'zillow'."""

    @abstractmethod
    def validate_params(self, params: dict) -> bool:
        """Validate that feed params are well-formed for this provider."""

    @abstractmethod
    def fetch(self, params: dict, cache_dir: str) -> pd.DataFrame:
        """
        Fetch data for the given params. Return a DataFrame with at minimum:
          - 'date' column (datetime64)
          - 'value' column (float64)
        For multi-region data, also include:
          - 'region' column (str)
        Cache raw responses in cache_dir.
        """

    @abstractmethod
    def get_metadata(self, params: dict) -> dict:
        """Return metadata: name, frequency, units, available date range, etc."""

    def get_available_series(self) -> list[dict]:
        """
        Optional. For providers with a browsable catalog (e.g., Zillow registry),
        return list of available series with their params.
        Default: returns empty list (user must know the series ID).
        """
        return []
```

### 4.2 Provider Implementations

#### FRED Provider (`fred_provider.py`)

- Uses `fredapi` Python package (already in use).
- `params`: `{ "series_id": "UNRATE" }`.
- `fetch()`: Calls FRED API, returns date/value DataFrame. Cached with `@st.cache_data(ttl=3600)` in the UI layer; raw responses also saved as Parquet in `data/cache/fred/`.
- `get_metadata()`: Returns series title, frequency, units, seasonal adjustment, last updated date from FRED API.
- `get_available_series()`: Not implemented (FRED has 800k+ series; users search by ID). However, provide a **search function** `search(query: str) -> list` that wraps `fred.search()`.

#### BEA Provider (`bea_provider.py`)

- Uses BEA REST API with API key.
- `params`: `{ "dataset": "NIPA", "table_name": "T10101", "line_number": 1 }`.
- `fetch()`: Calls BEA API, parses response, returns date/value DataFrame.
- `get_metadata()`: Returns table description, line description, units.
- Supports BEA's multi-line tables: a single table fetch can yield multiple series (one per line number). The provider should cache the full table and extract the requested line.

#### Zillow Provider (`zillow_provider.py`)

- Downloads CSVs from `files.zillowstatic.com`. No API key needed.
- Contains an embedded **registry** of all known Zillow datasets (the comprehensive URL catalog from the Zillow research page — ZHVI, ZORI, ZHVF, ZORF, listings, inventory, sales, etc. across all geography levels).
- `params`: `{ "metric_key": "zhvi", "filename": "Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv", "url": "...", "regions": [...] }`.
- `fetch()`: Downloads CSV if not cached (or stale), melts wide-format to long-format (Zillow CSVs have one column per date), optionally filters to specified regions. Returns DataFrame with `date`, `value`, `region` columns.
- `get_available_series()`: Returns the full registry for browsing in the Feed Manager UI.
- **Wide-to-long parsing logic**: Zillow CSVs have metadata columns (`RegionID`, `SizeRank`, `RegionName`, `RegionType`, `StateName`, etc.) followed by date columns (`2020-01-31`, `2020-02-29`, ...). The provider auto-detects date columns by regex matching `YYYY-MM-DD` patterns and melts accordingly.

#### File Provider (`file_provider.py`)

- Handles user-uploaded CSV and Excel files.
- `params`: `{ "file_path": "...", "date_column": "Date", "value_column": "Value" }`.
- `fetch()`: Reads the file from disk, extracts the specified columns.
- On upload, copies the file to `data/cache/files/` for persistence.

#### News Provider (`news_provider.py`)

- Fetches and parses RSS/Atom feeds.
- `params`: `{ "feed_url": "https://..." }`.
- `fetch()`: Returns a DataFrame with `date`, `title`, `link`, `summary` columns.
- Cached with a short TTL (e.g., 30 minutes).

### 4.3 Provider Registry

A simple registry maps provider IDs to classes:

```python
PROVIDERS = {
    "fred": FredProvider,
    "bea": BeaProvider,
    "zillow": ZillowProvider,
    "file": FileProvider,
    "news": NewsProvider,
}
```

To add a new provider in the future (e.g., Census, OECD), implement `BaseProvider` and add an entry.

---

## 5. Transforms System

### 5.1 Design Principle

Transforms are **pure functions** that take a DataFrame and return a DataFrame. They are applied at render time, not stored in the cache. This means the cache always holds raw data, and transforms can be changed without re-fetching.

### 5.2 Transform Functions

All functions accept a DataFrame with `date` and `value` columns (and optionally `region`) and return the same schema.

```python
def yoy_pct(df: pd.DataFrame) -> pd.DataFrame:
    """Year-over-year percent change."""

def mom_pct(df: pd.DataFrame) -> pd.DataFrame:
    """Month-over-month percent change."""

def rolling_avg(df: pd.DataFrame, window: int) -> pd.DataFrame:
    """Rolling average over N periods."""

def index_to_date(df: pd.DataFrame, base_date: str) -> pd.DataFrame:
    """Normalize to 100 at base_date."""

def diff(df: pd.DataFrame) -> pd.DataFrame:
    """First difference."""

def cumulative(df: pd.DataFrame) -> pd.DataFrame:
    """Cumulative sum."""

def log_transform(df: pd.DataFrame) -> pd.DataFrame:
    """Natural logarithm."""
```

### 5.3 Recession Shading

Recession shading is not a data transform but a chart overlay. The `recession.py` module provides NBER recession date ranges as a list of `(start, end)` tuples. The chart renderer uses these to draw shaded `vrect` regions on Plotly figures. Recession dates should be fetched from FRED series `USREC` (or hardcoded with the known historical dates) and updated via the normal refresh mechanism.

### 5.4 Correlation Analysis

Given a list of feeds and a date range:

1. Fetch and align all series to a common date index (forward-fill, then intersect).
2. Compute a correlation matrix.
3. Return as a DataFrame suitable for heatmap rendering.

Optionally support rolling correlation between exactly 2 series with a configurable window.

---

## 6. Views & User Workflows

### 6.1 Sidebar Navigation

The sidebar provides navigation and global controls:

```
📊 Macro Dashboard
─────────────────
[Dashboard Viewer ▼]   ← dropdown of saved dashboards
─────────────────
📋 Feed Manager
📈 Chart Editor
🖥️ Dashboard Builder
─────────────────
⚙️ Settings
🔄 Refresh Data
```

The default landing page is the **Dashboard Viewer** showing the most recently viewed (or a default) dashboard.

### 6.2 Dashboard Viewer (`views/dashboard_viewer.py`)

**Purpose**: Render a saved dashboard from its JSON config.

**Behavior**:
- Reads the selected dashboard JSON from `catalogs/dashboards/`.
- For each chart reference in the layout, loads the chart config from `catalogs/charts.json`.
- For each chart, loads the required feeds, applies transforms, and renders the visualization.
- Arranges items in the grid layout using `st.columns()` based on the `width` values.
- Shows a toolbar at the top: dashboard name, description, last refresh time, "Edit" button (navigates to Dashboard Builder), "Refresh" button.
- News widgets render inline from their RSS configs.
- Metric cards show the latest value and a configurable delta (e.g., change from prior month, prior year).

**Performance**:
- Data loading is cached via `@st.cache_data` with appropriate TTLs.
- On initial load, all feeds for the dashboard are pre-fetched in bulk.
- Loading indicators shown per chart slot while data is fetched.

### 6.3 Feed Manager (`views/feed_manager.py`)

**Purpose**: Browse, add, configure, and preview data feeds.

**Workflows**:

1. **Browse existing feeds**: Show a searchable, filterable table of all registered feeds from `catalogs/feeds.json`. Columns: name, provider, frequency, tags, last refreshed. Click a row to see a preview chart and metadata.

2. **Add a FRED feed**: Text input for series ID. On submit, call FRED API to validate and fetch metadata. Show preview chart. Confirm to save to catalog.

3. **Add a BEA feed**: Dropdowns to select dataset → table → line number (progressively loaded from BEA API). Preview and confirm.

4. **Add a Zillow feed**: Browse the Zillow registry grouped by category (Home Values, Rentals, Listings, etc.). Select a dataset and geography level. For multi-region datasets, show a region picker. Preview and confirm.

5. **Add a file feed**: File upload widget. Auto-detect columns, let user map date and value columns. Preview and confirm.

6. **Add a news feed**: URL input for RSS feed. Preview parsed items. Confirm.

7. **Preview any feed**: Select a feed → show a quick time-series chart, summary stats (min, max, mean, latest value, date range, number of observations), and raw data table.

8. **Edit a feed**: Change display name, tags, refresh schedule, or provider params (e.g., add/remove Zillow regions).

9. **Delete a feed**: With confirmation. Warn if the feed is referenced by any charts.

10. **Refresh a feed**: Manual one-click refresh that re-fetches from the source and updates the cache.

11. **Bulk actions**: Select multiple feeds → bulk refresh, bulk tag, bulk delete.

### 6.4 Chart Editor (`views/chart_editor.py`)

**Purpose**: Create and edit chart configurations with a live preview.

**Layout**: Side-by-side panels. Left panel (≈40% width): configuration form. Right panel (≈60% width): live-rendered chart preview that updates as the user changes settings.

**Workflows**:

1. **Create new chart**:
   - Select chart type (time_series, bar, metric_card, heatmap, table).
   - Add feeds using a reusable feed picker component (searchable dropdown of registered feeds, with quick-add to register a new feed inline).
   - For each feed: set display label, axis (left/right for time_series), color, and optional transform.
   - Set chart options: title, date range, recession shading toggle, legend toggle, height.
   - Live preview updates on every change.
   - Save to catalog.

2. **Edit existing chart**:
   - Load from catalog, populate form, edit, save.
   - "Save As" to duplicate and create a variant.

3. **Browse charts**:
   - Searchable list of all charts from `catalogs/charts.json`.
   - Thumbnail preview (small rendered version) for each.
   - Click to open in editor.
   - Delete with confirmation (warn if chart is on any dashboard).

4. **Transform configuration**:
   - For each feed on a chart, an optional transform dropdown (YoY%, MoM%, Rolling Avg, Index to Date, etc.).
   - Transform params shown conditionally (e.g., window size for rolling avg, base date for indexing).
   - Preview updates immediately to show transformed data.

5. **Correlation heatmap special case**:
   - When chart type is `heatmap`, the UI shows a multi-feed selector (pick N feeds).
   - Date range picker to set the correlation window.
   - Preview renders the correlation matrix.

### 6.5 Dashboard Builder (`views/dashboard_builder.py`)

**Purpose**: Assemble charts into a named dashboard layout.

**Workflows**:

1. **Create new dashboard**:
   - Set name and description.
   - Add rows. For each row, add items by picking from the chart catalog or adding a news widget.
   - Set column widths per item (must sum to 12 per row). Provide preset layouts: "2 equal", "3 equal", "1/3 + 2/3", "2/3 + 1/3", "4 equal".
   - Reorder rows via drag-and-drop (or up/down buttons in Streamlit).
   - Full preview of the assembled dashboard.
   - Save.

2. **Edit existing dashboard**:
   - Load from catalog, modify layout, save.
   - "Clone" to create a copy for iteration.

3. **Quick-add chart to dashboard**:
   - From the Chart Editor, a "Add to Dashboard" button lets the user pick a target dashboard and row position.

4. **Template dashboards**:
   - Pre-built dashboard configs shipped with the app (e.g., "US Reindustrialization Tracker", "Housing Market Overview").
   - These reference pre-registered feeds and charts. On first run, the app checks if the template feeds/charts exist and creates them if needed.
   - Templates are normal dashboard JSON files — users can clone and customize them.

### 6.6 Data Explorer (`views/data_explorer.py`) — Optional / Phase 2

A lightweight ad-hoc exploration view:
- Pick any registered feed.
- Apply transforms interactively.
- Compare multiple series on a scratch chart.
- Export to CSV.

This is lower priority than the core Feed → Chart → Dashboard pipeline.

---

## 7. Data Refresh System

### 7.1 Scheduled Refresh (`scripts/refresh.py`)

A standalone Python script (no Streamlit dependency) that can be run via cron:

```bash
# Run daily at 6 AM
0 6 * * * cd /path/to/macro-dashboard && python scripts/refresh.py
```

**Behavior**:
1. Reads `catalogs/feeds.json` to get all registered feeds.
2. For each feed, checks `data/refresh_log.json` for the last refresh timestamp.
3. Based on the feed's `refresh_schedule` (`daily`, `weekly`, `monthly`) and the last refresh time, decides whether to refresh.
4. Calls the appropriate provider's `fetch()` method and writes updated Parquet to `data/cache/`.
5. Updates `data/refresh_log.json` with the new timestamp.
6. Logs results (success/failure per feed) to stdout and optionally to a log file.

**Refresh schedules**:
- `daily`: Refresh if last refresh was > 20 hours ago.
- `weekly`: Refresh if last refresh was > 6 days ago.
- `monthly`: Refresh if last refresh was > 25 days ago. (For Zillow, ideally check if we're past the 16th and the cache predates the 16th.)

### 7.2 Manual Refresh (In-App)

- **Per-feed**: "Refresh" button on the Feed Manager page.
- **Per-dashboard**: "Refresh" button on the Dashboard Viewer that refreshes all feeds used by that dashboard.
- **Global**: "Refresh All" in the sidebar Settings area.

### 7.3 Staleness Indicators

- Each chart on a dashboard shows a subtle "last updated" timestamp.
- If a feed hasn't been refreshed within 2× its expected schedule (e.g., a daily feed not refreshed in 2 days), show an amber warning indicator.
- Zillow-specific: if today is past the 16th and the cache is from before the 16th, show "New Zillow data may be available."

---

## 8. Configuration (`config/app_config.yaml`)

```yaml
# API Keys
fred_api_key: "your-fred-api-key"
bea_api_key: "your-bea-api-key"

# Paths (relative to project root)
catalog_dir: "catalogs"
cache_dir: "data/cache"
refresh_log: "data/refresh_log.json"

# Defaults
default_dashboard: "reindustrialization"
default_date_range_years: 5        # Default lookback for new charts
default_chart_height: 450

# Refresh
refresh_schedule_default: "daily"  # Default for new feeds

# Appearance
plotly_template: "plotly_white"    # Plotly template for all charts
color_palette:                     # Default color cycle for multi-series charts
  - "#1f77b4"
  - "#ff7f0e"
  - "#2ca02c"
  - "#d62728"
  - "#9467bd"
  - "#8c564b"
  - "#e377c2"
  - "#7f7f7f"
```

---

## 9. Pre-Built Template: US Reindustrialization Dashboard

The app ships with a complete template that demonstrates the full pipeline. On first run, it seeds the following:

### 9.1 Template Feeds

| Feed ID | Provider | Series / Params | Description |
|---------|----------|-----------------|-------------|
| `fred_manemp` | fred | MANEMP | Manufacturing employment (thousands) |
| `fred_ipman` | fred | IPMAN | Industrial production: manufacturing |
| `fred_pcuomfg` | fred | PCUOMFG | Producer price index: manufacturing |
| `fred_tlrescons` | fred | TLRESCONS | Total construction spending |
| `fred_amtmno` | fred | AMTMNO | Manufacturers' new orders |
| `fred_dgorder` | fred | DGORDER | Durable goods orders |
| `fred_mcumfn` | fred | MCUMFN | Manufacturing capacity utilization |
| `fred_ismpmi` | fred | ISM/PMI | ISM Manufacturing PMI |
| `rss_fed` | news | Fed RSS URL | Federal Reserve press releases |

### 9.2 Template Charts

A set of charts combining these feeds into time series, metric cards, and a correlation heatmap, all pre-configured with appropriate transforms, date ranges, and recession shading.

### 9.3 Template Dashboard Layout

A 3–4 row layout with:
- Row 1: Two time-series charts (employment + construction spending)
- Row 2: Four metric cards (PMI, IP, capacity utilization, durable goods)
- Row 3: Correlation heatmap + Fed news feed

---

## 10. Standard Workflows & Use Cases

### Workflow 1: "I want to track a new FRED series"
1. Go to **Feed Manager** → **Add Feed** → Select FRED
2. Type series ID (e.g., `CPIAUCSL`), see preview
3. Save feed → it appears in the feed catalog
4. Go to **Chart Editor** → Create new time series chart → pick the feed
5. Configure title, transforms (e.g., YoY%), recession shading
6. Save chart
7. Go to **Dashboard Builder** → add chart to a dashboard row
8. View on **Dashboard Viewer**

### Workflow 2: "I want to update an existing chart's date range"
1. **Option A (UI)**: Dashboard Viewer → click "Edit" on the chart → opens Chart Editor → change date range → Save
2. **Option B (JSON)**: Open `catalogs/charts.json` → find the chart → change `options.date_range.start` → save file → reload app

### Workflow 3: "I want to compare housing values across metros"
1. Feed Manager → Add Zillow feed → browse registry → select ZHVI All Homes, Metro
2. Pick regions: New York, LA, Chicago, Miami
3. Save feed
4. Chart Editor → new time series → pick the Zillow feed
5. The chart renderer automatically plots one line per region
6. Optionally apply "Index to Date" transform to normalize for comparison
7. Save and add to a "Housing" dashboard

### Workflow 4: "I want to clone and customize a template dashboard"
1. Dashboard Builder → open "US Reindustrialization" → click "Clone"
2. Rename to "My Reindustrialization View"
3. Remove rows, add new charts, rearrange
4. Save

### Workflow 5: "I want to bulk-create feeds via JSON"
1. Open `catalogs/feeds.json` in a text editor
2. Copy an existing FRED feed entry, change `feed_id`, `params.series_id`, `name`
3. Repeat for N series
4. Save file, reload app — all feeds appear in the catalog
5. Run `python scripts/refresh.py` to fetch data for all new feeds

### Workflow 6: "Data refreshes automatically overnight"
1. Set up cron: `0 6 * * * cd /path/to/app && python scripts/refresh.py`
2. The refresh script reads the feed catalog, checks staleness, re-fetches as needed
3. Next morning, open the dashboard — all charts show latest data
4. Stale-data warnings appear if any feed failed to refresh

### Workflow 7: "I want to see the correlation between N series"
1. Register all desired feeds in the Feed Manager
2. Chart Editor → new heatmap chart → select the feeds
3. Set date range for the correlation window
4. Preview shows the correlation matrix
5. Save and add to a dashboard

### Workflow 8: "I want to add a news feed to my dashboard"
1. Feed Manager → Add Feed → News/RSS → enter URL
2. Preview parsed headlines
3. Save feed
4. Dashboard Builder → add a news widget to any row, referencing the feed
5. Dashboard Viewer shows latest headlines with links

---

## 11. Error Handling & Edge Cases

| Scenario | Behavior |
|----------|----------|
| FRED API key missing or invalid | Show config error on app start, link to Settings |
| Network failure during fetch | Show warning toast, serve stale cached data if available |
| Feed referenced by chart is deleted | Chart renders with "Missing feed: {feed_id}" placeholder |
| Chart referenced by dashboard is deleted | Dashboard renders with "Missing chart: {chart_id}" placeholder |
| Zillow CSV URL returns 404 | Log warning, skip feed, show stale indicator |
| Uploaded file is moved/deleted | Show error on feed preview, prompt user to re-upload |
| Duplicate feed_id in JSON | Reject on load, show validation error |
| Malformed JSON in catalog file | Show parse error with file path and line number |
| Very large dataset (Zillow ZIP-level) | Use Parquet caching; load only requested regions into memory |

---

## 12. Implementation Phases

### Phase 1: Core Pipeline (MVP)
- Provider base class + FRED provider (refactored from existing code)
- Feed catalog (JSON) + Feed Manager UI (add, browse, preview FRED feeds)
- Chart catalog (JSON) + Chart Editor UI (time series + metric card)
- Dashboard catalog (JSON) + Dashboard Viewer (render from config)
- Dashboard Builder (assemble charts into rows)
- Reindustrialization template dashboard (seeded on first run)
- Manual refresh per feed and per dashboard

### Phase 2: Full Provider Coverage
- BEA provider (refactored from existing code)
- Zillow provider with full registry (refactored from existing code)
- File provider (refactored from existing code)
- News provider (refactored from existing code)
- Zillow registry browser in Feed Manager

### Phase 3: Automation & Polish
- `scripts/refresh.py` for cron-based scheduled refresh
- Staleness indicators on dashboard
- Bar chart, heatmap/correlation, and table chart types
- Transforms: YoY, MoM, rolling avg, index to date, recession shading
- Chart "Save As" / clone
- Dashboard clone
- Bulk feed operations

### Phase 4: Advanced Features
- Data Explorer (ad-hoc analysis)
- Rolling correlation charts
- Annotation support on time series
- Export dashboard as PDF/PNG
- Web-scraped HTML tables (if needed)

---

## 13. Migration from Current App

The current app has working code for FRED, BEA, Zillow, file upload, web scraping, news, charts, and dashboards. The refactor should:

1. **Extract** existing data-fetching logic from current loaders into the new provider classes. Don't rewrite from scratch — wrap the working code in the new provider interface.
2. **Migrate** any existing dashboard JSON configs to the new schema (likely requires a one-time conversion script).
3. **Preserve** the Reindustrialization dashboard content — it should appear as a template in the new system.
4. **Deprecate** the old `modules/` directory structure once the new `providers/`, `transforms/`, `views/`, `components/` structure is in place.

The migration can be done incrementally: stand up the new skeleton, port one provider at a time, and keep the old views accessible until the new ones are complete.
