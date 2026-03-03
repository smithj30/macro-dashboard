"""
Data Feed catalog storage layer.

Feeds are the core abstraction in v2 — a named, tagged, refreshable reference
to a data series from any provider. Instead of embedding series IDs directly
in chart configs, charts reference feed_ids from this catalog.

Storage: catalogs/feeds.json — a flat list of feed objects.

Feed schema:
{
    "id": "feed_<8hex>",
    "name": "Unemployment Rate",
    "provider": "fred",          # key in PROVIDERS registry
    "series_id": "UNRATE",       # provider-specific identifier
    "frequency": "Monthly",
    "units": "Percent",
    "tags": ["labor", "unemployment"],
    "refresh_schedule": "daily",  # daily / weekly / monthly / manual
    "provider_metadata": {},      # cached metadata from provider
    "created_at": "...",
    "updated_at": "...",
    "last_refreshed": null,
    "kwargs": {}                  # extra provider-specific params (e.g. regions for Zillow)
}
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_FEEDS_PATH = Path(__file__).parent.parent.parent / "catalogs" / "feeds.json"


def _ensure_dir() -> None:
    _FEEDS_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_all() -> List[Dict[str, Any]]:
    """Load the full feeds list from disk."""
    if not _FEEDS_PATH.exists():
        return []
    try:
        with open(_FEEDS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_all(feeds: List[Dict[str, Any]]) -> None:
    """Write the full feeds list to disk."""
    _ensure_dir()
    with open(_FEEDS_PATH, "w", encoding="utf-8") as f:
        json.dump(feeds, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_feeds(
    provider: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Return all feeds, optionally filtered by provider and/or tags.
    Returns summary dicts (no heavy metadata).
    """
    feeds = _load_all()
    if provider:
        feeds = [f for f in feeds if f.get("provider") == provider]
    if tags:
        tag_set = set(t.lower() for t in tags)
        feeds = [
            f for f in feeds
            if tag_set & set(t.lower() for t in f.get("tags", []))
        ]
    feeds.sort(key=lambda f: f.get("name", "").lower())
    return feeds


def get_feed(feed_id: str) -> Optional[Dict[str, Any]]:
    """Return a single feed by ID, or None."""
    for f in _load_all():
        if f.get("id") == feed_id:
            return f
    return None


def find_feed(provider: str, series_id: str) -> Optional[Dict[str, Any]]:
    """Find a feed by provider + series_id combination."""
    for f in _load_all():
        if f.get("provider") == provider and f.get("series_id") == series_id:
            return f
    return None


def create_feed(
    name: str,
    provider: str,
    series_id: str,
    frequency: str = "",
    units: str = "",
    tags: Optional[List[str]] = None,
    refresh_schedule: str = "daily",
    provider_metadata: Optional[Dict[str, Any]] = None,
    kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create and persist a new feed. Returns the feed dict."""
    feeds = _load_all()
    now = datetime.now().isoformat()
    feed = {
        "id": f"feed_{uuid.uuid4().hex[:8]}",
        "name": name.strip(),
        "provider": provider,
        "series_id": series_id,
        "frequency": frequency,
        "units": units,
        "tags": tags or [],
        "refresh_schedule": refresh_schedule,
        "provider_metadata": provider_metadata or {},
        "created_at": now,
        "updated_at": now,
        "last_refreshed": None,
        "kwargs": kwargs or {},
    }
    feeds.append(feed)
    _save_all(feeds)
    return feed


def update_feed(feed_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Update a feed's fields. Returns the updated feed, or None if not found.
    Protected fields (id, created_at) cannot be changed.
    """
    feeds = _load_all()
    for i, f in enumerate(feeds):
        if f.get("id") == feed_id:
            protected = {"id", "created_at"}
            for k, v in updates.items():
                if k not in protected:
                    f[k] = v
            f["updated_at"] = datetime.now().isoformat()
            feeds[i] = f
            _save_all(feeds)
            return f
    return None


def delete_feed(feed_id: str) -> bool:
    """Delete a feed by ID. Returns True if deleted."""
    feeds = _load_all()
    new_feeds = [f for f in feeds if f.get("id") != feed_id]
    if len(new_feeds) == len(feeds):
        return False
    _save_all(new_feeds)
    return True


def bulk_create_feeds(feed_defs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Create multiple feeds at once. Each def should have at minimum:
    name, provider, series_id.
    Returns list of created feed dicts.
    """
    feeds = _load_all()
    created = []
    now = datetime.now().isoformat()
    for defn in feed_defs:
        feed = {
            "id": f"feed_{uuid.uuid4().hex[:8]}",
            "name": defn.get("name", defn.get("series_id", "")),
            "provider": defn["provider"],
            "series_id": defn["series_id"],
            "frequency": defn.get("frequency", ""),
            "units": defn.get("units", ""),
            "tags": defn.get("tags", []),
            "refresh_schedule": defn.get("refresh_schedule", "daily"),
            "provider_metadata": defn.get("provider_metadata", {}),
            "created_at": now,
            "updated_at": now,
            "last_refreshed": None,
            "kwargs": defn.get("kwargs", {}),
        }
        feeds.append(feed)
        created.append(feed)
    _save_all(feeds)
    return created


def mark_refreshed(feed_id: str) -> None:
    """Update last_refreshed timestamp for a feed."""
    update_feed(feed_id, {"last_refreshed": datetime.now().isoformat()})


def feed_count() -> int:
    """Return total number of registered feeds."""
    return len(_load_all())
