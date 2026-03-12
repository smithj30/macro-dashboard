# Macro Dashboard User Guide

## How to Create a Chart

1. **Navigate** to **Chart Builder** in the sidebar
2. You'll land on the **Chart Explorer** — click **"New Chart"** to enter edit mode
3. **Add series data** using one of three tabs:
   - **From Feed** — pick a registered feed from the feed picker dropdown, then click "Add Series"
   - **From Catalog** — select a dataset loaded in the current session
   - **From FRED** — enter a FRED series ID directly
4. Each added series appears in the series list where you can set:
   - **Label** — display name on the chart
   - **Transform** — none, YoY, MoM, rolling average, etc.
   - **Axis** — primary (left) or secondary (right) y-axis
   - **Chart type** — line, bar, area
5. Configure **chart options**: title, y-axis bounds, recession shading, range slider, legend
6. The chart **previews live** as you configure it
7. Click **"Save Chart"** (or **"Save As New"** when editing an existing chart)
8. You're returned to the **Chart Explorer** where the new chart appears in the list

## How to Create a Metric Card

1. From **New Chart** mode, switch to the **Card** tab (at the top of the edit view)
2. Pick a data source (feed or FRED series)
3. Set the **value format** (e.g., `,.0f`), **suffix** (e.g., `%`, `K`), and **delta type**
4. Click **Save Card**

## Bulk Actions in Chart Explorer

- **Checkboxes** on each item allow multi-select
- **Select All / Deselect All** buttons for quick selection
- Bulk action bar appears when items are selected:
  - **Create Dashboard** — creates a new dashboard pre-filled with the selected charts
  - **Add to Dashboard** — appends selected charts to an existing dashboard
  - **Bulk Tag** — apply tags to all selected charts at once
  - **Bulk Delete** — delete selected charts with confirmation

## Staleness Indicators on Dashboards

When viewing a dashboard, each chart and card row shows a **"Last updated"** caption indicating data freshness:

- **No indicator** — the chart's feeds are fresh (within their expected schedule interval)
- **Amber dot** — one or more feeds are **stale** (past their schedule but within 2x the interval)
- **Red dot** — one or more feeds are **very stale** (past 2x the interval) or have **never been refreshed**

Staleness thresholds are based on each feed's `refresh_schedule`:
- **Daily** feeds: fresh < 24h, stale 24–40h, very stale > 40h
- **Weekly** feeds: fresh < 7d, stale 7–12d, very stale > 12d
- **Monthly** feeds: fresh < 31d, stale 31–50d, very stale > 50d
- **Manual** feeds: always shown as fresh

## Refreshing Dashboard Data

Click the **Refresh** button in the dashboard toolbar to re-fetch all feed data:

1. The button collects every unique feed referenced by charts and cards on the dashboard
2. Each feed is re-fetched from its provider (FRED, BEA, etc.) with a progress bar
3. `last_refreshed` timestamps are updated in `feeds.json` for each successful fetch
4. If a feed fails to refresh, the error is shown but remaining feeds continue
5. The page automatically reloads to display the updated data and fresh staleness indicators
