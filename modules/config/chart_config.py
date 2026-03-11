"""
Chart configuration storage layer.

Charts and cards are stored in catalogs/charts.json as a flat list.
Each item has a unique "id" and a "type" (chart or card).
Charts reference feeds by feed_id in their series definitions.

Item schema:
{
    "id": "item_<8hex>",
    "type": "chart" | "card",
    "title": "Unemployment Rate",
    "tags": ["labor"],

    # Chart-specific fields:
    "series": [...],
    "chart_subtype": "Time Series",
    "y_axis": {"min": null, "max": null},
    "y_axis2": {"min": null, "max": null},
    "show_legend": true,
    "default_range_years": null,

    # Card-specific fields:
    "feed_id": "feed_xxx",
    "value_format": ",.2f",
    "value_suffix": "%",
    "delta_type": "period",

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


def _ensure_dir() -> None:
    _CHARTS_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_all() -> List[Dict[str, Any]]:
    if not _CHARTS_PATH.exists():
        return []
    try:
        with open(_CHARTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_all(items: List[Dict[str, Any]]) -> None:
    _ensure_dir()
    with open(_CHARTS_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_items(
    item_type: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Return all items, optionally filtered by type and/or tags."""
    items = _load_all()
    if item_type:
        items = [i for i in items if i.get("type") == item_type]
    if tags:
        tag_set = set(t.lower() for t in tags)
        items = [
            i for i in items
            if tag_set & set(t.lower() for t in i.get("tags", []))
        ]
    items.sort(key=lambda i: i.get("title", "").lower())
    return items


def get_item(item_id: str) -> Optional[Dict[str, Any]]:
    """Return a single item by ID, or None."""
    for i in _load_all():
        if i.get("id") == item_id:
            return i
    return None


def upsert_item(item_dict: Dict[str, Any]) -> str:
    """
    Create or update an item. If item_dict has an "id" that exists, update it.
    Otherwise create a new item with a generated ID.
    Returns the item ID.
    """
    items = _load_all()
    now = datetime.now().isoformat()

    item_id = item_dict.get("id")
    if item_id:
        for idx, existing in enumerate(items):
            if existing.get("id") == item_id:
                # Update: merge new fields into existing
                existing.update(item_dict)
                existing["updated_at"] = now
                items[idx] = existing
                _save_all(items)
                return item_id

    # Create new
    if not item_id:
        item_id = f"item_{uuid.uuid4().hex[:8]}"
        item_dict["id"] = item_id
    item_dict.setdefault("created_at", now)
    item_dict["updated_at"] = now
    items.append(item_dict)
    _save_all(items)
    return item_id


def delete_item(item_id: str) -> bool:
    """Delete an item by ID. Returns True if deleted."""
    items = _load_all()
    new_items = [i for i in items if i.get("id") != item_id]
    if len(new_items) == len(items):
        return False
    _save_all(new_items)
    return True


def item_count() -> int:
    """Return total number of items."""
    return len(_load_all())
