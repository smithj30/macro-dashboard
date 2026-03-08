"""
Chart configuration storage layer (v2).

Charts are stored in catalogs/charts.json as a flat list of chart objects.
Each chart references feeds by feed_id and contains display options.

Chart schema (spec Section 3.3):
{
    "chart_id": "unemployment_vs_claims",
    "name": "Unemployment Rate vs. Initial Claims",
    "chart_type": "time_series",           # time_series | bar | metric_card | heatmap | table
    "feeds": [
        {
            "feed_id": "fred_unrate",
            "label": "Unemployment Rate (%)",
            "axis": "left",                # left | right
            "color": "#1f77b4",            # optional override
            "transform": null              # null | {"type": "rolling_avg", "window": 4}
        }
    ],
    "options": {
        "title": "Labor Market Overview",
        "date_range": {"start": "2019-01-01", "end": null},
        "recession_shading": true,
        "show_legend": true,
        "show_range_slider": true,
        "height": 450,
        "annotations": []
    },
    "tags": ["labor", "weekly"],
    "created_at": "...",
    "updated_at": "..."
}
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_CHARTS_PATH = Path(__file__).parent.parent.parent / "catalogs" / "charts.json"
_DASHBOARDS_DIR = Path(__file__).parent.parent.parent / "dashboards"


def _ensure_dir() -> None:
    _CHARTS_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_all() -> List[Dict[str, Any]]:
    """Load the full charts list from disk."""
    if not _CHARTS_PATH.exists():
        return []
    try:
        with open(_CHARTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_all(charts: List[Dict[str, Any]]) -> None:
    """Write the full charts list to disk."""
    _ensure_dir()
    with open(_CHARTS_PATH, "w", encoding="utf-8") as f:
        json.dump(charts, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_charts(
    tags: Optional[List[str]] = None,
    chart_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Return all charts, optionally filtered by tags and/or chart_type.
    """
    charts = _load_all()
    if chart_type:
        charts = [c for c in charts if c.get("chart_type") == chart_type]
    if tags:
        tag_set = set(t.lower() for t in tags)
        charts = [
            c for c in charts
            if tag_set & set(t.lower() for t in c.get("tags", []))
        ]
    charts.sort(key=lambda c: c.get("name", "").lower())
    return charts


def get_chart(chart_id: str) -> Optional[Dict[str, Any]]:
    """Return a single chart by chart_id, or None."""
    for c in _load_all():
        if c.get("chart_id") == chart_id:
            return c
    return None


def create_chart(
    name: str,
    chart_type: str = "time_series",
    feeds: Optional[List[Dict[str, Any]]] = None,
    options: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
    chart_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create and persist a new chart. Returns the chart dict."""
    charts = _load_all()
    now = datetime.now().isoformat()
    chart = {
        "chart_id": chart_id or f"chart_{uuid.uuid4().hex[:8]}",
        "name": name.strip(),
        "chart_type": chart_type,
        "feeds": feeds or [],
        "options": options or {
            "title": name.strip(),
            "date_range": {"start": None, "end": None},
            "recession_shading": False,
            "show_legend": True,
            "show_range_slider": True,
            "height": 450,
            "annotations": [],
        },
        "tags": tags or [],
        "created_at": now,
        "updated_at": now,
    }
    charts.append(chart)
    _save_all(charts)
    return chart


def update_chart(chart_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Update a chart's fields. Returns the updated chart, or None if not found.
    Protected fields: chart_id, created_at.
    """
    charts = _load_all()
    for i, c in enumerate(charts):
        if c.get("chart_id") == chart_id:
            protected = {"chart_id", "created_at"}
            for k, v in updates.items():
                if k not in protected:
                    c[k] = v
            c["updated_at"] = datetime.now().isoformat()
            charts[i] = c
            _save_all(charts)
            return c
    return None


def delete_chart(chart_id: str) -> bool:
    """Delete a chart by chart_id. Returns True if deleted."""
    charts = _load_all()
    new_charts = [c for c in charts if c.get("chart_id") != chart_id]
    if len(new_charts) == len(charts):
        return False
    _save_all(new_charts)
    return True


def find_charts_by_tag(tag: str) -> List[Dict[str, Any]]:
    """Find all charts that have a specific tag."""
    return [c for c in _load_all() if tag in c.get("tags", [])]


def find_charts_by_feed(feed_id: str) -> List[Dict[str, Any]]:
    """Find all charts that reference a specific feed_id."""
    results = []
    for c in _load_all():
        for f in c.get("feeds", []):
            if f.get("feed_id") == feed_id:
                results.append(c)
                break
    return results


def get_dashboard_refs(chart_id: str) -> List[str]:
    """
    Return list of dashboard IDs that reference this chart.
    Scans all dashboard JSON files.
    """
    refs = []
    if not _DASHBOARDS_DIR.exists():
        return refs

    for p in _DASHBOARDS_DIR.glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                cfg = json.load(f)

            # Check new row-based layout
            for row in cfg.get("layout", []):
                if isinstance(row, dict):
                    for item in row.get("items", []):
                        if item.get("chart_id") == chart_id:
                            refs.append(cfg.get("id") or cfg.get("dashboard_id", p.stem))
                            break

            # Check legacy sections format
            for section in cfg.get("sections", []):
                if isinstance(section, dict):
                    # Sections might reference catalog items
                    for series in section.get("series", []):
                        if series.get("chart_id") == chart_id:
                            refs.append(cfg.get("id", p.stem))
                            break
        except (json.JSONDecodeError, OSError):
            continue

    return list(set(refs))


def chart_count() -> int:
    """Return total number of charts."""
    return len(_load_all())
