"""
Dashboard configuration storage layer.

All dashboard configs live in dashboards/<id>.json relative to the project root.
This module provides read/write helpers used by both the static dashboard overrides
and the dynamic Dashboard Builder.

Supports two layout formats:
1. Legacy "sections" format (backward compat):
   { "sections": [{ "id": "sec_xxx", "title": "...", "layout": "half", "series": [...] }] }

2. New row-based 12-column grid format (spec Section 3.4):
   { "layout": [{ "row": 1, "items": [{ "type": "chart", "chart_id": "...", "width": 6 }] }] }
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Resolve dashboards/ relative to this file (project_root/modules/config/../../dashboards/)
_DASHBOARDS_DIR = Path(__file__).parent.parent.parent / "dashboards"


def _ensure_dir() -> None:
    _DASHBOARDS_DIR.mkdir(parents=True, exist_ok=True)


def _config_path(dashboard_id: str) -> Path:
    return _DASHBOARDS_DIR / f"{dashboard_id}.json"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(dashboard_id: str) -> Optional[Dict[str, Any]]:
    """Return the parsed JSON config for *dashboard_id*, or None if not found."""
    path = _config_path(dashboard_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_config(config: Dict[str, Any]) -> None:
    """Write *config* to dashboards/<id>.json (overwrites if exists)."""
    _ensure_dir()
    dashboard_id = config.get("id") or config.get("dashboard_id", "unknown")
    path = _config_path(dashboard_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, default=str)


def list_dashboards() -> List[Dict[str, Any]]:
    """Return summary info for all dashboards, sorted by title/name."""
    if not _DASHBOARDS_DIR.exists():
        return []
    results = []
    for p in _DASHBOARDS_DIR.glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            results.append({
                "id": cfg.get("id") or cfg.get("dashboard_id", p.stem),
                "name": cfg.get("name") or cfg.get("title", p.stem),
                "description": cfg.get("description", ""),
                "type": cfg.get("type", "unknown"),
                "tags": cfg.get("tags", []),
                "has_layout": bool(cfg.get("layout")),
                "has_sections": bool(cfg.get("sections")),
            })
        except (json.JSONDecodeError, OSError):
            continue
    results.sort(key=lambda c: c.get("name", "").lower())
    return results


def list_dynamic_dashboards() -> List[Dict[str, Any]]:
    """Return all configs with type=='dynamic', sorted by title."""
    if not _DASHBOARDS_DIR.exists():
        return []
    results = []
    for p in _DASHBOARDS_DIR.glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if cfg.get("type") == "dynamic":
                results.append(cfg)
        except (json.JSONDecodeError, OSError):
            continue
    results.sort(key=lambda c: c.get("title", "").lower())
    return results


def delete_config(dashboard_id: str) -> bool:
    """Delete the config file for *dashboard_id*. Returns True if deleted."""
    path = _config_path(dashboard_id)
    if path.exists():
        path.unlink()
        return True
    return False


def save_section_override(
    dashboard_id: str,
    section_id: str,
    overrides: Dict[str, Any],
) -> None:
    """
    Load-merge-save: update a single section's overrides without touching others.

    For static dashboards, sections is a dict keyed by section_id.
    Creates the config file (with minimal defaults) if it doesn't exist.
    """
    cfg = load_config(dashboard_id)
    if cfg is None:
        cfg = {"id": dashboard_id, "type": "static", "sections": {}}

    sections = cfg.setdefault("sections", {})
    existing = sections.get(section_id, {})
    existing.update(overrides)
    sections[section_id] = existing

    save_config(cfg)


# ---------------------------------------------------------------------------
# New row-based layout helpers
# ---------------------------------------------------------------------------


def create_dashboard(
    name: str,
    description: str = "",
    layout: Optional[List[Dict[str, Any]]] = None,
    tags: Optional[List[str]] = None,
    dashboard_id: Optional[str] = None,
    auto_refresh: bool = True,
) -> Dict[str, Any]:
    """Create and save a new v2 dashboard with row-based layout."""
    now = datetime.now().isoformat()
    config = {
        "id": dashboard_id or f"dash_{uuid.uuid4().hex[:8]}",
        "dashboard_id": dashboard_id or f"dash_{uuid.uuid4().hex[:8]}",
        "type": "dynamic",
        "name": name.strip(),
        "title": name.strip(),
        "description": description,
        "layout": layout or [],
        "auto_refresh": auto_refresh,
        "tags": tags or [],
        "created_at": now,
        "updated_at": now,
    }
    # Keep id and dashboard_id in sync
    config["dashboard_id"] = config["id"]
    save_config(config)
    return config


def is_row_layout(config: Dict[str, Any]) -> bool:
    """Check if a dashboard uses the new row-based layout format."""
    layout = config.get("layout")
    if not layout or not isinstance(layout, list):
        return False
    # Row-based layout has dicts with "row" and "items" keys
    if layout and isinstance(layout[0], dict) and "items" in layout[0]:
        return True
    return False


def is_sections_layout(config: Dict[str, Any]) -> bool:
    """Check if a dashboard uses the legacy sections format."""
    sections = config.get("sections")
    return bool(sections and isinstance(sections, list))


def add_row(
    dashboard_id: str,
    items: List[Dict[str, Any]],
    row_number: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Add a row to a dashboard's layout.
    Items should be dicts with at least {type, chart_id/config, width}.
    Widths should sum to 12.
    """
    config = load_config(dashboard_id)
    if config is None:
        return None

    layout = config.setdefault("layout", [])

    # Determine row number
    if row_number is None:
        existing_rows = [r.get("row", 0) for r in layout if isinstance(r, dict)]
        row_number = max(existing_rows, default=0) + 1

    row = {"row": row_number, "items": items}
    layout.append(row)
    layout.sort(key=lambda r: r.get("row", 0) if isinstance(r, dict) else 0)

    config["updated_at"] = datetime.now().isoformat()
    save_config(config)
    return config


def get_dashboard_chart_ids(config: Dict[str, Any]) -> List[str]:
    """Extract all chart_ids referenced by a dashboard config."""
    chart_ids = []

    # New row-based layout
    for row in config.get("layout", []):
        if isinstance(row, dict):
            for item in row.get("items", []):
                cid = item.get("chart_id")
                if cid:
                    chart_ids.append(cid)

    # Legacy sections
    for section in config.get("sections", []):
        if isinstance(section, dict):
            for series in section.get("series", []):
                cid = series.get("chart_id")
                if cid:
                    chart_ids.append(cid)

    return chart_ids
