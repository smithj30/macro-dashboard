# Test Plan — Post-Refactor Smoke Tests

Run against `http://localhost:8501`. The server should already be running via:
```
python3 -m streamlit run app.py --server.port 8501 --server.headless true
```

## 1. Navigation & Page Loading

- [ ] App loads without errors on the default page (should be a dashboard)
- [ ] Sidebar shows two sections: **Dashboards** (Labor Market, Manufacturing) and **Tools**
- [ ] "Chart Catalogs" does NOT appear in the sidebar (was removed)
- [ ] Click each sidebar nav item — every page loads without errors

## 2. Labor Market Dashboard

- [ ] Click "Labor Market" in sidebar — dashboard renders
- [ ] **Card row** at top shows 4 metric cards: All Employees Total Nonfarm, Unemployment Rate, Initial Claims, Continued Claims
- [ ] Each card shows a numeric value and a delta (YoY or period change)
- [ ] **Unemployment Rate chart** renders below the cards with data and a line
- [ ] Gear icon (⚙) appears next to the chart title
- [ ] Click the gear icon — popover opens with Chart type, Y min/max controls
- [ ] Change Y max to a value, click "Save settings" — chart re-renders with the new axis bound
- [ ] Click "Refresh" button in toolbar — page reloads data without errors

## 3. Manufacturing Dashboard

- [ ] Click "Manufacturing" in sidebar — dashboard renders
- [ ] Two charts render side by side (half-width layout)
- [ ] "Manufacturing New Orders & Shipments" chart shows data with correct Y-axis bounds (-10 to 15)
- [ ] Second chart ("Time Series") renders with data
- [ ] Gear icons work on both charts

## 4. Chart Builder — Load Saved Chart

- [ ] Click "Chart Builder" in sidebar — page loads
- [ ] Expand "Load saved chart/card" section
- [ ] Dropdown shows items like "Unemployment Rate [chart]", "Initial Claims [card]", etc.
- [ ] Select "Unemployment Rate [chart]" and click "Load Item"
- [ ] Chart Builder populates: series list shows the chart's series, preview chart renders
- [ ] Status bar shows "Editing: Unemployment Rate"
- [ ] Click "New (clear)" — form resets, status clears

## 5. Chart Builder — Create New Chart from Feed

- [ ] In Chart Builder, go to "Add Series" tab
- [ ] Feed picker dropdown shows registered feeds (filter by tag works)
- [ ] Select a feed, set a label, click "+ Add Series"
- [ ] Series appears in the series list above
- [ ] Preview chart renders with the new series
- [ ] Enter a chart title, click "Save" — toast confirms save
- [ ] Form clears after save (ready for next chart)

## 6. Chart Builder — Create New Card

- [ ] Switch item type to "Card" (radio button at top)
- [ ] Feed picker shows available feeds
- [ ] Select a feed — live preview shows the latest value and delta
- [ ] Set title, format, suffix, delta type
- [ ] Click "Save" — toast confirms, form clears

## 7. Chart Builder — Saved Charts List

- [ ] Scroll to bottom of Chart Builder — "Saved Charts & Cards" section appears
- [ ] Shows all 7+ items with type filter (All / Charts / Cards)
- [ ] Filter by "Cards" — only card items shown
- [ ] Filter by "Charts" — only chart items shown
- [ ] Click "Edit" on an item — Chart Builder loads it for editing
- [ ] Click "Delete" on an item — "Confirm" button appears, clicking confirms deletion
- [ ] Deleted item disappears from the list

## 8. Chart Builder — Save As New

- [ ] Load an existing chart (via "Load saved chart/card")
- [ ] Modify something (e.g., change title)
- [ ] Click "Save As New" — creates a new item (different ID) without overwriting original
- [ ] Both original and copy appear in the saved charts list

## 9. Dashboard Builder

- [ ] Click "Dashboard Builder" in sidebar — page loads
- [ ] Existing dashboards listed: Labor Market, Manufacturing
- [ ] Click "Edit" on Labor Market — step 1 (Details) loads with title pre-filled
- [ ] Click "Next: Add Sections" — step 2 shows current sections
- [ ] Sections display correctly: card row shows card names, chart sections show chart titles
- [ ] "Open" button on a chart section navigates to Chart Builder with that chart loaded

## 10. Dashboard Builder — Add Section

- [ ] In step 2, select "Saved Chart" radio — dropdown shows saved charts
- [ ] Select a chart, choose layout (half/full), click "Add Chart Section"
- [ ] New section appears in the section list
- [ ] Select "Card Row" radio — multiselect shows saved cards
- [ ] Select 2-3 cards, click "Add Card Row Section"
- [ ] Card row section appears in the list
- [ ] Click "Next: Preview & Save" — preview renders the dashboard with new sections
- [ ] Click "Save Dashboard" — saves without errors

## 11. Dashboard Builder — Clone & Delete

- [ ] Back on step 0, click "Clone" on a dashboard — copy appears in the list
- [ ] Click "Delete" on the copy — "Confirm" appears, click to delete
- [ ] Cloned dashboard removed from list

## 12. Feed Manager

- [ ] Click "Feed Manager" in sidebar — page loads, shows registered feeds
- [ ] Feed count displayed at top
- [ ] Each feed shows name, provider, tags
- [ ] Computed feeds show formula subtitle (e.g., "= A / B")
- [ ] Click "Preview" on a feed — data loads, chart renders, data table shown
- [ ] Click "Edit" — edit form loads with current values

## 13. Data Explorer

- [ ] Click "Data Explorer" in sidebar — page loads
- [ ] FRED tab: enter a search term, press Enter — results appear
- [ ] Check a series ID checkbox — "Load Series" populates preview below
- [ ] Preview shows chart and "Save as Feed" form
- [ ] Fill in tags, click "Save as Feed" — feed saved, appears in Feed Manager

## 14. Tag Manager

- [ ] Click "Tag Manager" in sidebar — page loads
- [ ] Shows existing tags with usage counts
- [ ] Can create a new tag, assign a color
- [ ] Tag appears in feed picker filters across other pages

## 15. Regression & Analysis

- [ ] Click "Regression & Analysis" — page loads
- [ ] If no data in session catalog, shows info message (expected)
- [ ] If data loaded via Data Explorer, OLS/Rolling Correlation/Transforms tabs work

## 16. Data Table

- [ ] Click "Data Table" — page loads
- [ ] If no data in session catalog, shows info message (expected)
- [ ] If data loaded, table displays with column/date filters

## 17. Cross-Page Navigation

- [ ] From Dashboard Builder step 2, click "Open" on a chart section → lands on Chart Builder with chart loaded
- [ ] From Feed Manager, click "Edit Formula" on a computed feed → lands on Data Explorer with formula pre-loaded
- [ ] From a dashboard, click "Edit" toolbar button → lands on Dashboard Builder step 2

## 18. Error Resilience

- [ ] Check Streamlit server logs (`/tmp/streamlit.log`) — no Python exceptions or tracebacks
- [ ] No broken references: all chart_ids in dashboard JSONs resolve to items in catalogs/charts.json
