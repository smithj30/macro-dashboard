"""
Chart Catalog storage layer.

All catalog configs live in chart_catalogs/<id>.json relative to the project root.
This module provides read/write helpers used by the Chart Builder and dashboard renderers.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_CATALOGS_DIR = Path(__file__).parent.parent.parent / "chart_catalogs"


def _ensure_dir() -> None:
    _CATALOGS_DIR.mkdir(parents=True, exist_ok=True)


def _catalog_path(catalog_id: str) -> Path:
    return _CATALOGS_DIR / f"{catalog_id}.json"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_catalogs() -> List[Dict[str, Any]]:
    """Return summary list of all catalogs: id, title, description, item_count."""
    if not _CATALOGS_DIR.exists():
        return []
    results = []
    for p in _CATALOGS_DIR.glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                cat = json.load(f)
            results.append(
                {
                    "id": cat.get("id", p.stem),
                    "title": cat.get("title", p.stem),
                    "description": cat.get("description", ""),
                    "item_count": len(cat.get("items", [])),
                }
            )
        except (json.JSONDecodeError, OSError):
            continue
    results.sort(key=lambda c: c.get("title", "").lower())
    return results


def load_catalog(catalog_id: str) -> Optional[Dict[str, Any]]:
    """Return the parsed catalog dict, or None if not found."""
    path = _catalog_path(catalog_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_catalog(catalog: Dict[str, Any]) -> None:
    """Write catalog to disk (overwrites if exists)."""
    _ensure_dir()
    catalog_id = catalog.get("id", "unknown")
    path = _catalog_path(catalog_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, default=str)


def create_catalog(title: str, description: str = "") -> Dict[str, Any]:
    """Create and persist a new empty catalog. Returns the new catalog dict."""
    base_id = title.strip().lower().replace(" ", "_").replace("-", "_")
    # Remove non-alphanumeric chars (except underscores)
    base_id = "".join(c if (c.isalnum() or c == "_") else "_" for c in base_id)
    catalog_id = base_id
    counter = 1
    while _catalog_path(catalog_id).exists():
        catalog_id = f"{base_id}_{counter}"
        counter += 1
    now = datetime.now().isoformat()
    catalog = {
        "id": catalog_id,
        "title": title.strip(),
        "description": description.strip(),
        "created_at": now,
        "updated_at": now,
        "items": [],
    }
    save_catalog(catalog)
    return catalog


def delete_catalog(catalog_id: str) -> bool:
    """Delete the catalog file. Returns True if deleted."""
    path = _catalog_path(catalog_id)
    if path.exists():
        path.unlink()
        return True
    return False


def get_item(catalog_id: str, item_id: str) -> Optional[Dict[str, Any]]:
    """Return a single item from a catalog, or None if not found."""
    cat = load_catalog(catalog_id)
    if cat is None:
        return None
    for item in cat.get("items", []):
        if item.get("id") == item_id:
            return item
    return None


def upsert_item(catalog_id: str, item: Dict[str, Any]) -> str:
    """
    Insert or update an item in a catalog. Returns the item_id.

    If item has no 'id', a new id is generated and the item is inserted.
    If item has an 'id' matching an existing item, that item is updated in place.
    If item has an 'id' not found in the catalog, it is inserted as new.
    """
    cat = load_catalog(catalog_id)
    if cat is None:
        return ""

    now = datetime.now().isoformat()
    items: List[Dict[str, Any]] = cat.get("items", [])
    item_id = item.get("id")

    if item_id:
        # Try to update in place
        for i, existing in enumerate(items):
            if existing.get("id") == item_id:
                item["updated_at"] = now
                item.setdefault("created_at", existing.get("created_at", now))
                items[i] = item
                break
        else:
            # id provided but not found → insert as new with that id
            item["created_at"] = now
            item["updated_at"] = now
            items.append(item)
    else:
        # New item — generate id
        item_id = f"item_{uuid.uuid4().hex[:8]}"
        item["id"] = item_id
        item["created_at"] = now
        item["updated_at"] = now
        items.append(item)

    cat["items"] = items
    cat["updated_at"] = now
    save_catalog(cat)
    return item["id"]


def delete_item(catalog_id: str, item_id: str) -> bool:
    """Remove an item from a catalog. Returns True if removed."""
    cat = load_catalog(catalog_id)
    if cat is None:
        return False
    items = cat.get("items", [])
    new_items = [it for it in items if it.get("id") != item_id]
    if len(new_items) == len(items):
        return False
    cat["items"] = new_items
    cat["updated_at"] = datetime.now().isoformat()
    save_catalog(cat)
    return True
