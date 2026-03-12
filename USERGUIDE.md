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
