# Macro Dashboard v2 — Functional Specification

## 1. Product Overview

### 1.1 Purpose

A macroeconomic research dashboard for a small investment team (2–5 people). The app provides a structured pipeline: **Data Explorer → Feeds → Charts → Dashboards**. Users discover and preview data in the Data Explorer, save what they need as feeds, compose feeds into reusable charts, and assemble charts into dashboards that auto-refresh with the latest data.

### 1.2 Design Philosophy

- **Tags over catalogs**: All organization is through a controlled tag vocabulary. Feeds, charts, and dashboards are tagged for flexible filtering rather than placed in rigid folder hierarchies.
- **Convention over configuration**: Sensible defaults so that the common case (plot a FRED series over time) requires minimal clicks.
- **Config-first durability**: The UI writes JSON; the JSON drives rendering. If the UI breaks, a user can hand-edit a JSON file and reload. If the user wants to bulk-create charts, they can duplicate and edit JSON configs directly.
- **Single responsibility per view**: Each view has one job. The Data Explorer is for discovery and feed creation. The Feed Manager is for metadata and cleanup. The Chart Editor is for building visuals. The Dashboard Builder is for layout.

### 1.3 Users & Deployment

- **Users**: Small team (2–5), shared view (no per-user auth or personalization).
- **Deployment**: Local development on a Mac Studio; remote team access via SSH port forwarding over ngrok, Tailscale, or cloud deployment. The app should be stateless enough to run behind any reverse proxy.

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
┌──────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│Data Explorer │────▶│    Feed     │────▶│    Chart    │────▶│  Dashboard  │
│  (discover)  │     │  (series)   │     │  (visual)   │     │  (layout)   │
└──────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
   Browse & preview     Saved config       Saved config        Assembled
   Create/update feeds  Edit metadata      Edit in editor      from charts
                        via Feed Manager   via Chart Editor
```

**Data Explorer**: The single entry point for discovering data and creating/updating feeds. Browse FRED, BEA, Zillow registries, upload files, configure RSS feeds. Preview data before saving. When updating an existing feed, the Data Explorer opens pre-populated with that feed's current configuration.

**Feed**: A saved data series configuration. Has a unique ID, provider params, metadata (name, description, tags, source/release info), and a refresh schedule. Stored in `feeds.json`.

**Chart**: A visualization referencing one or more Feeds with optional transforms and display options. Stored in `charts.json`.

**Dashboard**: A named grid layout of Charts and news widgets. Stored in `dashboards/{name}.json`.

**Tags**: A controlled vocabulary managed in the Tag Manager. Only pre-created tags can be applied to feeds and charts. Tags replace the catalog concept for organization.

### 2.2 Directory Structure

```
macro-dashboard/
├── app.py                          # Entry point, sidebar nav, session bootstrap
├── config/
│   ├── app_config.yaml             # Global settings (API keys, refresh schedule, paths)
│   ├── tags.json                   # Controlled tag vocabulary
│   └── chart_styles.json           # Chart visual styles (derived from Excel Chart Style Guide)
│
├── catalogs/
│   ├── feeds.json                  # All saved data feeds
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
│   ├── dashboard_viewer.py         # Renders a dashboard from its JSON config (landing page)
│   ├── data_explorer.py            # Browse sources, preview data, create/update feeds
│   ├── feed_manager.py             # View all feeds, edit metadata/tags, delete, link to Data Explorer
│   ├── chart_editor.py             # Browse charts + side-by-side build/edit (combined view)
│   ├── dashboard_builder.py        # Assemble/edit dashboard layouts
│   └── tag_manager.py              # Create/rename/merge/delete tags
│
├── components/                     # Reusable Streamlit UI components
│   ├── chart_renderer.py           # Renders a chart config → Plotly figure (applies styles)
│   ├── metric_card.py              # Single-value metric card with delta
│   ├── news_widget.py              # News/RSS display component
│   ├── feed_picker.py              # Reusable feed selection widget (for Chart Editor)
│   └── tag_picker.py               # Reusable tag selection widget (controlled vocabulary only)
│
└── scripts/
    └── refresh.py                  # CLI script for scheduled data refresh (cron)
```

### 2.3 Persistence & Storage

All persistence is local files:

| What | Format | Location |
|------|--------|----------|
| Feed definitions | JSON | `catalogs/feeds.json` |
| Chart definitions | JSON | `catalogs/charts.json` |
| Dashboard configs | JSON | `catalogs/dashboards/*.json` |
| Tag vocabulary | JSON | `config/tags.json` |
| Chart visual styles | JSON | `config/chart_styles.json` |
| App settings | YAML | `config/app_config.yaml` |
| Cached data | Parquet | `data/cache/{provider}/{key}.parquet` |
| Refresh log | JSON | `data/refresh_log.json` |

**Why Parquet for cache?** Efficient columnar storage, preserves dtypes (especially dates), fast to read with pandas, and smaller than CSV for wide time-series data. The Zillow ZIP-code file drops from ~50MB CSV to ~10MB Parquet.

**Why JSON for configs?** Human-readable and hand-editable, which is core to the hybrid workflow. Users can open `charts.json` in any text editor.

---

## 3. Data Model — JSON Schemas

### 3.1 Tags

```json
// config/tags.json
{
  "tags": [
    { "name": "labor", "color": "#1f77b4" },
    { "name": "housing", "color": "#ff7f0e" },
    { "name": "manufacturing", "color": "#2ca02c" },
    { "name": "inflation", "color": "#d62728" },
    { "name": "monetary-policy", "color": "#9467bd" },
    { "name": "construction", "color": "#8c564b" },
    { "name": "weekly", "color": "#e377c2" },
    { "name": "monthly", "color": "#7f7f7f" }
  ]
}
```

Tags have a `name` (lowercase, hyphenated) and an optional `color` for display. Tags can only be applied to feeds and charts if they exist in this file. The Tag Manager UI is the only way to create, rename, merge, or delete tags (though the JSON can also be hand-edited).

### 3.2 Data Feed

```json
{
  "feed_id": "fred_unrate",
  "provider": "fred",
  "name": "Unemployment Rate",
  "description": "Civilian unemployment rate, seasonally adjusted",
  "source": "U.S. Bureau of Labor Statistics",
  "release": "Employment Situation",
  "params": {
    "series_id": "UNRATE"
  },
  "frequency": "monthly",
  "dimensions": {
    "geography": null,
    "segment": null
  },
  "refresh_schedule": "daily",
  "tags": ["labor"],
  "created_at": "2026-02-27T10:00:00Z",
  "updated_at": "2026-02-27T10:00:00Z"
}
```

**New fields vs. prior spec:**
- `source`: The originating agency or organization (e.g., "U.S. Census Bureau", "Bureau of Labor Statistics", "Zillow Research"). For FRED feeds, this is auto-populated from the FRED API's source metadata.
- `release`: The specific statistical release or publication (e.g., "Manufacturer's Shipments, Inventories, and Orders (M3) Survey", "Employment Situation"). For FRED feeds, this is auto-populated from the FRED API's release metadata.

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
  "url": "https://files.zillowstatic.com/research/public_csvs/zhvi/...",
  "regions": ["New York, NY", "Los Angeles-Long Beach-Anaheim, CA"]
}

// RSS/News
{ "feed_url": "https://www.federalreserve.gov/feeds/press_all.xml" }

// Uploaded file
{ "file_path": "data/cache/files/custom_data.csv", "date_column": "Date", "value_column": "Value" }
```

### 3.3 Chart

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
    "show_range_slider": true,
    "height": 450,
    "annotations": []
  },
  "tags": ["labor", "weekly"],
  "dashboard_refs": [],
  "created_at": "2026-02-27T10:00:00Z",
  "updated_at": "2026-02-27T10:00:00Z"
}
```

**Chart option notes:**
- `show_range_slider`: When `true`, renders a Plotly range slider on the x-axis for interactive date scoping. This is a **slider-only control** (no miniature chart preview in the slider area). Implemented via `fig.update_layout(xaxis=dict(rangeslider=dict(visible=True, thickness=0.04)))` with minimal thickness and no secondary trace. See Section 8 for details.
- `dashboard_refs`: Populated dynamically at load time by scanning dashboard configs. Not stored — computed on read. Shown in the Chart Explorer for impact analysis.

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

### 3.4 Dashboard

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
        { "type": "chart", "chart_id": "mfg_correlation_heatmap", "width": 8 },
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
        """
        Return metadata: name, frequency, units, available date range, etc.
        For FRED: must include 'source' and 'release' fields.
        """

    def get_available_series(self) -> list[dict]:
        """
        Optional. For providers with a browsable catalog (e.g., Zillow registry),
        return list of available series with their params.
        Default: returns empty list (user must know the series ID).
        """
        return []

    def search(self, query: str) -> list[dict]:
        """
        Optional. For providers with search capability (e.g., FRED).
        Returns list of matching series with metadata.
        Default: returns empty list.
        """
        return []
```

### 4.2 Provider Implementations

#### FRED Provider (`fred_provider.py`)

- Uses `fredapi` Python package (already in use).
- `params`: `{ "series_id": "UNRATE" }`.
- `fetch()`: Calls FRED API, returns date/value DataFrame. Cached with `@st.cache_data(ttl=3600)` in the UI layer; raw responses also saved as Parquet in `data/cache/fred/`.
- `get_metadata()`: Returns series title, frequency, units, seasonal adjustment, last updated date, **source name**, and **release name** from the FRED API. Specifically:
  - Calls `fred.get_series_info(series_id)` for basic metadata.
  - Calls the FRED release endpoint (`/series/release`) to get the release name (e.g., "Manufacturer's Shipments, Inventories, and Orders (M3) Survey").
  - Calls the FRED source endpoint (`/source`) to get the source name (e.g., "U.S. Census Bureau").
  - These are auto-populated into the feed's `source` and `release` fields on creation.
- `search(query)`: Wraps `fred.search()`. Returns matching series with ID, title, frequency, units, popularity, **source**, and **release**. The Data Explorer displays source and release in search results so users understand where the data comes from before saving a feed.

#### BEA Provider (`bea_provider.py`)

- Uses BEA REST API with API key.
- `params`: `{ "dataset": "NIPA", "table_name": "T10101", "line_number": 1 }`.
- `fetch()`: Calls BEA API, parses response, returns date/value DataFrame.
- `get_metadata()`: Returns table description, line description, units, source (always "Bureau of Economic Analysis"), release (dataset name).
- Supports BEA's multi-line tables: a single table fetch can yield multiple series (one per line number). The provider caches the full table and extracts the requested line.

#### Zillow Provider (`zillow_provider.py`)

- Downloads CSVs from `files.zillowstatic.com`. No API key needed.
- Contains an embedded **registry** of all known Zillow datasets (the comprehensive URL catalog from the Zillow research page — ZHVI, ZORI, ZHVF, ZORF, listings, inventory, sales, etc. across all geography levels).
- `params`: `{ "metric_key": "zhvi", "filename": "Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv", "url": "...", "regions": [...] }`.
- `fetch()`: Downloads CSV if not cached (or stale), melts wide-format to long-format (Zillow CSVs have one column per date), optionally filters to specified regions. Returns DataFrame with `date`, `value`, `region` columns.
- `get_available_series()`: Returns the full registry for browsing in the Data Explorer.
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

```
📊 Macro Dashboard
─────────────────
[Dashboard Viewer ▼]   ← Dropdown of saved dashboards (landing page)
─────────────────
🔍 Data Explorer
📋 Feed Manager
📈 Chart Editor          ← Combined browse + edit view
🖥️ Dashboard Builder
─────────────────
🏷️ Tag Manager
⚙️ Settings
🔄 Refresh Data
```

The **Dashboard Viewer** is the default landing page — the most common action is viewing, not building.

### 6.2 Dashboard Viewer (`views/dashboard_viewer.py`)

**Purpose**: Render a saved dashboard from its JSON config. This is the landing page.

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

### 6.3 Data Explorer (`views/data_explorer.py`)

**Purpose**: The single entry point for discovering data sources and creating or updating feeds.

**Layout**: Breadcrumb navigation shows the current path, e.g., "Data Explorer > FRED > Search > UNRATE > [Save as Feed]".

**Mode 1 — Browse / Discover** (default):
- Top-level view shows provider cards: FRED, BEA, Zillow, Upload File, News/RSS.
- Clicking a provider opens its discovery interface:
  - **FRED**: Search box. Results show series ID, title, frequency, units, **source**, and **release** (e.g., "Source: U.S. Census Bureau | Release: M3 Survey"). Click a result to preview.
  - **BEA**: Progressive dropdowns: Dataset → Table → Line Number. Preview on selection.
  - **Zillow**: Browse registry grouped by category with expandable sections. Select dataset + geography. Region picker for multi-region data. Preview on selection.
  - **Upload File**: File upload widget. Auto-detect columns, map date and value columns. Preview.
  - **News/RSS**: URL input. Preview parsed headlines.
- **Preview pane**: For all providers, shows a quick time-series chart, summary stats (min, max, mean, latest value, date range, observation count), and a sample data table.
- **Save as Feed** button: Prominent, appears only after a valid preview. Opens a save dialog with: auto-generated feed ID (editable), name (pre-filled from metadata), description, tag picker (controlled vocabulary), refresh schedule. For FRED, source and release are pre-filled from the API. Confirm saves to `catalogs/feeds.json`.

**Mode 2 — Update Existing Feed** (entered via Feed Manager "Update" button):
- Data Explorer opens pre-populated with the existing feed's provider, params, and configuration.
- The user sees exactly what they had and can modify any parameter (e.g., change Zillow regions, switch FRED series).
- Preview updates live as changes are made.
- Two distinct action buttons:
  - **"Update Feed"**: Overwrites the existing feed config (same feed_id).
  - **"Save as New Feed"**: Creates a new feed with a new ID (preserves the original).
- Visual indicator makes clear which mode the user is in (e.g., "Updating: fred_unrate" banner at the top).

### 6.4 Feed Manager (`views/feed_manager.py`)

**Purpose**: Lightweight admin view for managing existing feeds. NOT for creating or modifying feed data configuration — that's the Data Explorer's job.

**Capabilities**:
- **Browse**: Searchable, filterable table of all saved feeds. Columns: name, provider, source, release, frequency, tags, last refreshed. Search works across name, source, release, and tags. Filter by tag, filter by provider.
- **Edit metadata**: Click a feed row to expand inline editing of: display name, description, tags (controlled vocabulary picker). These are metadata-only changes that don't affect what data is fetched.
- **Update data config**: "Update" button navigates to the Data Explorer in update mode (Mode 2) with the feed pre-populated. This is how users change what a feed actually pulls.
- **Delete**: Delete button with confirmation dialog. Warns if the feed is referenced by any charts (lists the chart names).
- **Refresh**: Per-feed "Refresh" button to re-fetch from source. Bulk refresh for selected feeds.
- **Staleness display**: Shows last refresh date for each feed. Amber indicator if stale (past 2x expected refresh interval).

### 6.5 Chart Editor (`views/chart_editor.py`) — Combined Browse + Edit

**Purpose**: Browse all charts AND create/edit charts in a single view with two modes.

**Mode 1 — Chart Explorer** (default, list/browse):
- Searchable, filterable grid of all charts from `catalogs/charts.json`.
- Each chart shows: thumbnail preview (small rendered version), name, chart type, tags, and **dashboard references** (which dashboards include this chart — computed by scanning dashboard configs).
- Filter by tag, filter by chart type.
- **Orphan indicator**: Charts not on any dashboard are marked so they're easy to find for cleanup.
- **Multi-select**: Checkboxes on charts. When 1+ charts are selected, action buttons appear:
  - **"Create Dashboard from Selected"**: Opens Dashboard Builder with the selected charts pre-loaded into a new dashboard layout.
  - **"Add to Existing Dashboard"**: Dropdown to pick a dashboard, then adds selected charts as new rows.
  - **"Bulk Tag"**: Apply tags to all selected charts.
  - **"Bulk Delete"**: With confirmation, warning about dashboard references.
- Click a chart to open it in Edit mode.

**Mode 2 — Chart Edit** (side-by-side builder):
- **Layout**: Left panel (approx 40% width) is the configuration form. Right panel (approx 60% width) is a live-rendered chart preview that updates as settings change.
- **Creating a new chart**:
  - Select chart type (time_series, bar, metric_card, heatmap, table).
  - Add feeds using the **feed picker** component (searchable dropdown of saved feeds only — feeds must exist before they can be charted).
  - For each feed: set display label, axis (left/right for time_series), color (from style guide palette), and optional transform.
  - Set chart options: title, date range, recession shading toggle, legend toggle, range slider toggle, height.
  - Tag picker (controlled vocabulary).
  - Live preview updates on every change.
  - **"Save Chart"** button.
- **Editing an existing chart**:
  - Load from JSON, populate form, edit, save.
  - **"Save As New"** button to duplicate and create a variant.
- **Back to Explorer**: Button or breadcrumb to return to the chart list.
- **Transform configuration**: For each feed, an optional transform dropdown. Transform params shown conditionally (e.g., window size for rolling avg, base date for indexing). Preview updates immediately.
- **Correlation heatmap special case**: When chart type is `heatmap`, shows multi-feed selector and date range picker.

### 6.6 Dashboard Builder (`views/dashboard_builder.py`)

**Purpose**: Assemble charts into a named dashboard layout.

**Workflows**:

1. **Create new dashboard**: Set name, description, tags. Add rows. For each row, add items by picking from saved charts (via chart picker with search/filter) or adding a news widget. Set column widths per item (must sum to 12). Preset layouts: "2 equal" (6+6), "3 equal" (4+4+4), "1/3 + 2/3" (4+8), "2/3 + 1/3" (8+4), "4 equal" (3+3+3+3). Reorder rows via up/down buttons. Full preview of assembled dashboard. Save.

2. **Edit existing dashboard**: Load from JSON, modify layout, save.

3. **Clone**: Create a copy for iteration.

4. **Pre-populated from Chart Explorer**: When the user clicks "Create Dashboard from Selected" in the Chart Explorer, the builder opens with those charts pre-loaded (one chart per row by default, user can rearrange).

### 6.7 Tag Manager (`views/tag_manager.py`)

**Purpose**: Manage the controlled tag vocabulary. Only tags created here can be applied to feeds and charts.

**Capabilities**:
- **View all tags**: List with name, color, and usage count (how many feeds + charts use this tag).
- **Create tag**: Inline form — type a name, pick a color. Validates uniqueness.
- **Rename tag**: Updates the tag name everywhere it's used (feeds.json, charts.json).
- **Merge tags**: Select two tags → merge into one. All references updated.
- **Delete tag**: With confirmation. Removes the tag from all feeds and charts that use it.
- **Color picker**: Simple color selection for each tag (used in tag pills throughout the UI).

**Design note**: While this is a dedicated view, tags can also be *applied* inline from any tag picker widget in the app (Feed Manager, Chart Editor). The picker only shows tags that exist in the vocabulary. If a user needs a new tag while editing a chart, they can click "Create new tag" in the picker, which opens a quick inline dialog (like GitHub's label creator) — this creates the tag in `tags.json` and immediately makes it available. This avoids forcing a trip to the Tag Manager for the common case.

### 6.8 Settings (`views/settings.py`)

- API key configuration (FRED, BEA).
- Default chart height, date range, refresh schedule.
- Chart style selection (see Section 8).
- Refresh all feeds manually.
- Cache management (clear cache, view cache size).

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
- If a feed hasn't been refreshed within 2x its expected schedule (e.g., a daily feed not refreshed in 2 days), show an amber warning indicator.
- Zillow-specific: if today is past the 16th and the cache is from before the 16th, show "New Zillow data may be available."

---

## 8. Chart Styling & Visual Standards

### 8.1 Style Guide Integration

The app applies the **Kennedy Lewis Chart Style Guide** to all charts. The following values have been extracted from `Excel Chart Style Guide.xlsx` and should be encoded into `config/chart_styles.json` as a Plotly template. The `chart_renderer.py` component must load and apply this template to every Plotly figure before rendering.

The following values were extracted from the Kennedy Lewis Excel Chart Style Guide (`Excel Chart Style Guide.xlsx`):

**Brand Colors:**

| Name | Hex | Role |
|------|-----|------|
| Harbor Depth | `#011E2F` | Primary color, text, Series 1 |
| Morning Veil | `#FAF9F9` | Chart background |
| East River Blue | `#44ADE2` | Accent only, Series 2 |
| Eastside Dusk | `#134C72` | Series 3 |
| Gallery White | `#F6F2EE` | Secondary background |
| Clouded Facade | `#E1DBD4` | Gridlines, axis lines, Series 6 |
| Warm Stone | `#ABA29A` | Series 5 |
| Steel Haze | `#9EA3AB` | Axis label text, Series 4 |

**Typography:**

| Element | Font | Size | Color | Weight |
|---------|------|------|-------|--------|
| Chart title | Arial | 13pt | Harbor Depth (#011E2F) | Regular (not bold) |
| Axis tick labels | Arial | 9pt | Steel Haze (#9EA3AB) | Regular |
| Data labels | Arial | 9pt | Harbor Depth (#011E2F) | Regular |
| Legend | Arial | 9pt | Harbor Depth (#011E2F) | Regular |

**Chart Formatting:**

| Element | Value |
|---------|-------|
| Background (paper) | Morning Veil (#FAF9F9) |
| Plot area background | Transparent (no fill) |
| Chart border | None (no fill on line) |
| Gridlines | Clouded Facade (#E1DBD4), solid, 0.75pt |
| Axis lines | Clouded Facade (#E1DBD4), solid, 0.75pt |
| Line weight (line charts) | 2.25pt |
| Legend position | Bottom |
| Series color sequence | #011E2F, #44ADE2, #134C72, #9EA3AB, #ABA29A, #E1DBD4 |

**Design Principles (from style guide):**
- Use Harbor Depth (#011E2F) as the primary/first series color in every chart
- East River Blue (#44ADE2) is reserved as an accent — use sparingly for emphasis or highlights
- Maintain restraint: limit charts to 3-4 colors when possible; avoid visual clutter
- Use Morning Veil (#FAF9F9) or white backgrounds; never use East River Blue as a background
- Gridlines should be subtle — use Clouded Facade (#E1DBD4) or remove entirely for a clean look
- Favor deep blues and warm neutrals; avoid bright or saturated colors outside the palette

The `chart_styles.json` encodes all of the above as a Plotly template:

```json
{
  "style_name": "kennedy_lewis",
  "brand_colors": {
    "harbor_depth": "#011E2F",
    "morning_veil": "#FAF9F9",
    "east_river_blue": "#44ADE2",
    "eastside_dusk": "#134C72",
    "gallery_white": "#F6F2EE",
    "clouded_facade": "#E1DBD4",
    "warm_stone": "#ABA29A",
    "steel_haze": "#9EA3AB"
  },
  "plotly_template": {
    "layout": {
      "font": {
        "family": "Arial, sans-serif",
        "size": 12,
        "color": "#011E2F"
      },
      "title": {
        "font": { "family": "Arial, sans-serif", "size": 16, "color": "#011E2F" },
        "x": 0.0,
        "xanchor": "left"
      },
      "xaxis": {
        "gridcolor": "#E1DBD4",
        "gridwidth": 1,
        "linecolor": "#E1DBD4",
        "linewidth": 1,
        "tickfont": { "family": "Arial, sans-serif", "size": 11, "color": "#9EA3AB" },
        "showgrid": false,
        "zeroline": false
      },
      "yaxis": {
        "gridcolor": "#E1DBD4",
        "gridwidth": 1,
        "linecolor": "#E1DBD4",
        "linewidth": 1,
        "tickfont": { "family": "Arial, sans-serif", "size": 11, "color": "#9EA3AB" },
        "showgrid": true,
        "zeroline": false
      },
      "plot_bgcolor": "rgba(0,0,0,0)",
      "paper_bgcolor": "#FAF9F9",
      "legend": {
        "font": { "family": "Arial, sans-serif", "size": 11, "color": "#011E2F" },
        "orientation": "h",
        "yanchor": "top",
        "y": -0.15,
        "xanchor": "center",
        "x": 0.5
      },
      "colorway": ["#011E2F", "#44ADE2", "#134C72", "#9EA3AB", "#ABA29A", "#E1DBD4"],
      "margin": { "t": 60, "b": 60, "l": 60, "r": 30 },
      "hovermode": "x unified"
    },
    "data": {
      "scatter": [{ "line": { "width": 2.25 } }]
    }
  },
  "recession_shading_color": "rgba(225, 219, 212, 0.35)",
  "metric_card_styles": {
    "positive_delta_color": "#44ADE2",
    "negative_delta_color": "#9EA3AB",
    "value_font_size": 28,
    "value_color": "#011E2F",
    "delta_font_size": 14,
    "background_color": "#FAF9F9",
    "border_color": "#E1DBD4"
  }
}
```

**Notes on Plotly adaptation:**
- Excel 13pt title maps to Plotly 16px (Plotly uses slightly different sizing than Excel points; 16px provides comparable visual weight on screen).
- Excel 9pt axis labels map to Plotly 11px for readability on dashboard-sized charts.
- Line width 2.25pt from Excel translates directly to Plotly's `line.width: 2.25`.
- Recession shading uses Clouded Facade at 35% opacity to stay subtle and on-brand.
- Metric card delta colors use East River Blue (positive) and Steel Haze (negative) rather than traditional green/red, staying within the brand palette.
- Legend is positioned at the bottom (`orientation: "h"`) matching the Excel chart legend placement.
```

### 8.2 Range Slider (X-Axis Scoping)

Time-series charts support an optional range slider at the bottom for interactively adjusting the visible date range. This is a **slider-only control** — it does NOT show a miniature version of the chart (the default Plotly rangeslider behavior).

Implementation:

```python
fig.update_layout(
    xaxis=dict(
        rangeslider=dict(
            visible=True,
            thickness=0.04,      # Thin slider bar, no room for a mini-chart
            bgcolor="#f0f0f0",
            bordercolor="#cccccc",
            borderwidth=1
        ),
        rangeselector=None       # No preset range buttons (optional, can add if desired)
    )
)

# Remove any secondary traces from the rangeslider.
# Plotly by default mirrors traces into the rangeslider area.
# Setting thickness to 0.04 effectively prevents the mini-chart from being visible.
# For extra safety, also set each trace's xaxis to only show on the main axis.
```

The range slider is toggled per chart via the `show_range_slider` option in the chart config. Default: `true` for time_series charts, `false` for all other types.

### 8.3 Color Assignment

When a chart has multiple series:
1. Colors are assigned from the style guide's `colorway` palette in order.
2. Users can override any series color in the Chart Editor.
3. Overridden colors are stored in the chart config per feed.
4. If no override, the palette cycles.

---

## 9. Pre-Built Template: US Reindustrialization Dashboard

The app ships with a complete template that demonstrates the full pipeline. On first run, it seeds the following:

### 9.1 Template Feeds

| Feed ID | Provider | Series | Source | Release | Description |
|---------|----------|--------|--------|---------|-------------|
| `fred_manemp` | fred | MANEMP | BLS | Employment Situation | Manufacturing employment (thousands) |
| `fred_ipman` | fred | IPMAN | Federal Reserve | Industrial Production and Capacity Utilization | Industrial production: manufacturing |
| `fred_pcuomfg` | fred | PCUOMFG | BLS | Producer Price Index | PPI: manufacturing |
| `fred_tlrescons` | fred | TLRESCONS | Census Bureau | Construction Spending | Total construction spending |
| `fred_amtmno` | fred | AMTMNO | Census Bureau | M3 Survey | Manufacturers' new orders |
| `fred_dgorder` | fred | DGORDER | Census Bureau | Advance Report on Durable Goods | Durable goods orders |
| `fred_mcumfn` | fred | MCUMFN | Federal Reserve | Industrial Production and Capacity Utilization | Manufacturing capacity utilization |
| `fred_napm` | fred | NAPM | ISM | ISM Report on Business | ISM Manufacturing PMI |
| `rss_fed` | news | Fed RSS URL | — | — | Federal Reserve press releases |

### 9.2 Template Charts

A set of charts combining these feeds into time series, metric cards, and a correlation heatmap, all pre-configured with appropriate transforms, date ranges, recession shading, and the standard chart style.

### 9.3 Template Dashboard Layout

A 3–4 row layout with:
- Row 1: Two time-series charts (employment + construction spending)
- Row 2: Four metric cards (PMI, IP, capacity utilization, durable goods)
- Row 3: Correlation heatmap + Fed news feed

---

## 10. Standard Workflows & Use Cases

### Workflow 1: "I want to track a new FRED series"
1. Go to **Data Explorer** → select FRED provider
2. Search for series (e.g., "consumer price index")
3. See results with source and release info (e.g., "Source: BLS | Release: CPI")
4. Click to preview chart and summary stats
5. Click **"Save as Feed"** → auto-filled name, source, release; pick tags; save
6. Go to **Chart Editor** → create new time series chart → pick the feed from the feed picker
7. Configure title, transforms, recession shading; see live preview
8. Save chart
9. Go to **Dashboard Builder** → add chart to a dashboard row
10. View on **Dashboard Viewer**

### Workflow 2: "I want to update what data a feed pulls"
1. Go to **Feed Manager** → find the feed → click **"Update"**
2. Data Explorer opens pre-populated with the feed's current config
3. Modify params (e.g., change FRED series ID, add Zillow regions)
4. Preview the updated data
5. Click **"Update Feed"** to overwrite, or **"Save as New Feed"** to keep both

### Workflow 3: "I want to relabel or retag a feed"
1. Go to **Feed Manager** → find the feed → click to expand
2. Edit the display name, description, or tags inline
3. Save — no trip to the Data Explorer needed since data config hasn't changed

### Workflow 4: "I want to compare housing values across metros"
1. Data Explorer → Zillow → browse registry → select ZHVI All Homes, Metro
2. Pick regions: New York, LA, Chicago, Miami
3. Preview multi-line chart
4. Save as Feed
5. Chart Editor → new time series → pick the Zillow feed
6. Apply "Index to Date" transform to normalize for comparison
7. Save chart → add to a "Housing" dashboard

### Workflow 5: "I want to build a dashboard from several charts I just created"
1. Go to **Chart Editor** (opens in Explorer/browse mode)
2. Check the boxes on 6 charts
3. Click **"Create Dashboard from Selected"**
4. Dashboard Builder opens with the 6 charts pre-loaded (one per row)
5. Rearrange into 2-column layouts, adjust widths, name the dashboard
6. Save

### Workflow 6: "I want to see which dashboards use a specific chart"
1. Go to **Chart Editor** (Explorer mode)
2. Each chart's card shows its dashboard references (e.g., "On: Reindustrialization, Housing")
3. Orphaned charts (not on any dashboard) are visually marked

### Workflow 7: "I want to organize my feeds and charts with tags"
1. Go to **Tag Manager** → create tags: "labor", "housing", "manufacturing", "weekly"
2. In **Feed Manager**, tag each feed with relevant tags
3. In **Chart Editor**, tag each chart
4. Now in any browse view, filter by tag to quickly find what you need

### Workflow 8: "I want to bulk-create feeds via JSON"
1. Open `catalogs/feeds.json` in a text editor
2. Copy an existing FRED feed entry, change `feed_id`, `params.series_id`, `name`
3. Repeat for N series
4. Save file, reload app — all feeds appear in the Feed Manager
5. Run `python scripts/refresh.py` to fetch data for all new feeds

### Workflow 9: "Data refreshes automatically overnight"
1. Set up cron: `0 6 * * * cd /path/to/app && python scripts/refresh.py`
2. The refresh script reads the feed catalog, checks staleness, re-fetches as needed
3. Next morning, open the dashboard — all charts show latest data
4. Stale-data warnings appear if any feed failed to refresh

### Workflow 10: "I want to add a news feed to my dashboard"
1. Data Explorer → News/RSS → enter URL → preview parsed headlines → Save as Feed
2. Dashboard Builder → add a news widget to any row, referencing the feed
3. Dashboard Viewer shows latest headlines with links

### Workflow 11: "I want to add charts to an existing dashboard"
1. Go to **Chart Editor** (Explorer mode)
2. Check the boxes on 3 charts
3. Click **"Add to Existing Dashboard"** → select "Reindustrialization" from dropdown
4. Charts are appended as new rows to the dashboard
5. Go to **Dashboard Builder** to rearrange if needed

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
| Tag deleted that is in use | Remove tag from all feeds/charts that use it (with confirmation listing affected items) |
| Feed updated with incompatible params | Charts using the feed re-render with new data; if data shape changes, transforms may need reconfiguration |

---

## 12. Implementation Phases

### Phase 1: Core Pipeline (MVP)
- Provider base class + FRED provider (with source/release metadata)
- Tag system (`config/tags.json`, Tag Manager view, tag picker component)
- Feed JSON schema + Data Explorer (FRED discovery with source/release display, preview, save as feed)
- Feed Manager (browse, edit metadata, delete, "Update" link to Data Explorer)
- Chart JSON schema + Chart Editor (combined explorer + side-by-side editor; time_series + metric_card types)
- Chart style system (`config/chart_styles.json` derived from Excel Chart Style Guide, chart renderer with style application, range slider without mini-chart)
- Dashboard JSON schema + Dashboard Viewer (render from config, landing page)
- Dashboard Builder (assemble charts into rows)
- Reindustrialization template dashboard (seeded on first run with source/release metadata)
- Manual refresh per feed and per dashboard

### Phase 2: Full Provider Coverage
- BEA provider (refactored from existing code)
- Zillow provider with full registry (refactored from existing code)
- File provider (refactored from existing code)
- News provider (refactored from existing code)
- Zillow registry browser in Data Explorer
- File upload flow in Data Explorer

### Phase 3: Automation & Polish
- `scripts/refresh.py` for cron-based scheduled refresh
- Staleness indicators on dashboard
- Bar chart, heatmap/correlation, and table chart types
- All transforms: YoY, MoM, rolling avg, index to date, recession shading
- Chart "Save As New" / clone
- Dashboard clone
- Multi-select chart actions in Chart Explorer (create dashboard, add to existing dashboard, bulk tag, bulk delete)
- Dashboard references on chart cards
- Orphan chart indicators

### Phase 4: Advanced Features
- Rolling correlation charts
- Annotation support on time series
- Export dashboard as PDF/PNG
- Web-scraped HTML tables (if needed)
- Ad-hoc data exploration mode in Data Explorer

---

## 13. Migration from Current App

The current app has working code for FRED, BEA, Zillow, file upload, web scraping, news, charts, and dashboards. The refactor should:

1. **Extract** existing data-fetching logic from current loaders into the new provider classes. Don't rewrite from scratch — wrap the working code in the new provider interface.
2. **Migrate** any existing dashboard JSON configs to the new schema (likely requires a one-time conversion script).
3. **Preserve** the Reindustrialization dashboard content — it should appear as a template in the new system.
4. **Deprecate** the old `modules/` directory structure once the new `providers/`, `transforms/`, `views/`, `components/` structure is in place.
5. **Apply the Kennedy Lewis Chart Style Guide**: The style values have been fully extracted and are documented in Section 8.1 of this spec, including the complete `chart_styles.json` content. Create `config/chart_styles.json` using the exact Plotly template JSON provided there. Ensure `chart_renderer.py` loads this template and applies it to every figure.

The migration can be done incrementally: stand up the new skeleton, port one provider at a time, and keep the old views accessible until the new ones are complete.
