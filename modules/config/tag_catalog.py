"""
Tag catalog — controlled vocabulary for organizing feeds and charts.

Tags are stored in config/tags.json as a list of {name, color} objects.
Only tags in this vocabulary can be applied to feeds and charts.

CRUD operations here cascade to feeds.json and charts.json when
tags are renamed, merged, or deleted.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_TAGS_PATH = Path(__file__).parent.parent.parent / "config" / "tags.json"
_FEEDS_PATH = Path(__file__).parent.parent.parent / "catalogs" / "feeds.json"
_CHARTS_PATH = Path(__file__).parent.parent.parent / "catalogs" / "charts.json"


def _load_tags() -> List[Dict[str, str]]:
    """Load the tags list from disk."""
    if not _TAGS_PATH.exists():
        return []
    try:
        with open(_TAGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("tags", []) if isinstance(data, dict) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_tags(tags: List[Dict[str, str]]) -> None:
    """Write the tags list to disk."""
    _TAGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_TAGS_PATH, "w", encoding="utf-8") as f:
        json.dump({"tags": tags}, f, indent=2)


def _load_json_list(path: Path) -> List[Dict[str, Any]]:
    """Load a JSON file that contains a list."""
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_json_list(path: Path, data: List[Dict[str, Any]]) -> None:
    """Write a list to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def _rename_tag_in_items(items: List[Dict[str, Any]], old: str, new: str) -> bool:
    """Rename a tag in a list of feed/chart dicts. Returns True if any changed."""
    changed = False
    for item in items:
        tags = item.get("tags", [])
        if old in tags:
            tags = [new if t == old else t for t in tags]
            # Deduplicate
            seen = set()
            deduped = []
            for t in tags:
                if t not in seen:
                    seen.add(t)
                    deduped.append(t)
            item["tags"] = deduped
            changed = True
    return changed


def _remove_tag_from_items(items: List[Dict[str, Any]], tag_name: str) -> bool:
    """Remove a tag from a list of feed/chart dicts. Returns True if any changed."""
    changed = False
    for item in items:
        tags = item.get("tags", [])
        if tag_name in tags:
            item["tags"] = [t for t in tags if t != tag_name]
            changed = True
    return changed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_tags() -> List[Dict[str, str]]:
    """Return all tags sorted by name."""
    tags = _load_tags()
    tags.sort(key=lambda t: t.get("name", "").lower())
    return tags


def get_tag(name: str) -> Optional[Dict[str, str]]:
    """Return a single tag by name, or None."""
    for t in _load_tags():
        if t.get("name") == name:
            return t
    return None


def tag_names() -> List[str]:
    """Return just the tag names as a sorted list."""
    return [t["name"] for t in list_tags()]


def create_tag(name: str, color: str = "#888888") -> Dict[str, str]:
    """Create a new tag. Raises ValueError if name already exists."""
    name = name.strip().lower().replace(" ", "-")
    if not name:
        raise ValueError("Tag name cannot be empty")
    tags = _load_tags()
    if any(t["name"] == name for t in tags):
        raise ValueError(f"Tag '{name}' already exists")
    tag = {"name": name, "color": color}
    tags.append(tag)
    _save_tags(tags)
    return tag


def rename_tag(old_name: str, new_name: str) -> bool:
    """
    Rename a tag. Cascades to feeds.json and charts.json.
    Returns True if the tag was found and renamed.
    """
    new_name = new_name.strip().lower().replace(" ", "-")
    if not new_name:
        raise ValueError("New tag name cannot be empty")

    tags = _load_tags()
    found = False
    for t in tags:
        if t["name"] == old_name:
            t["name"] = new_name
            found = True
            break

    if not found:
        return False

    # Check for duplicate after rename
    names = [t["name"] for t in tags]
    if names.count(new_name) > 1:
        raise ValueError(f"Tag '{new_name}' already exists")

    _save_tags(tags)

    # Cascade to feeds
    feeds = _load_json_list(_FEEDS_PATH)
    if _rename_tag_in_items(feeds, old_name, new_name):
        _save_json_list(_FEEDS_PATH, feeds)

    # Cascade to charts
    charts = _load_json_list(_CHARTS_PATH)
    if _rename_tag_in_items(charts, old_name, new_name):
        _save_json_list(_CHARTS_PATH, charts)

    return True


def merge_tags(source_name: str, target_name: str) -> bool:
    """
    Merge source tag into target tag. Source is deleted; all references
    to source become target. Returns True if both tags existed.
    """
    tags = _load_tags()
    source_exists = any(t["name"] == source_name for t in tags)
    target_exists = any(t["name"] == target_name for t in tags)

    if not source_exists or not target_exists:
        return False

    # Remove source tag from vocabulary
    tags = [t for t in tags if t["name"] != source_name]
    _save_tags(tags)

    # Rename source → target in feeds and charts (handles dedup)
    feeds = _load_json_list(_FEEDS_PATH)
    if _rename_tag_in_items(feeds, source_name, target_name):
        _save_json_list(_FEEDS_PATH, feeds)

    charts = _load_json_list(_CHARTS_PATH)
    if _rename_tag_in_items(charts, source_name, target_name):
        _save_json_list(_CHARTS_PATH, charts)

    return True


def delete_tag(name: str) -> bool:
    """
    Delete a tag from the vocabulary and remove it from all feeds/charts.
    Returns True if the tag existed.
    """
    tags = _load_tags()
    new_tags = [t for t in tags if t["name"] != name]
    if len(new_tags) == len(tags):
        return False

    _save_tags(new_tags)

    # Remove from feeds
    feeds = _load_json_list(_FEEDS_PATH)
    if _remove_tag_from_items(feeds, name):
        _save_json_list(_FEEDS_PATH, feeds)

    # Remove from charts
    charts = _load_json_list(_CHARTS_PATH)
    if _remove_tag_from_items(charts, name):
        _save_json_list(_CHARTS_PATH, charts)

    return True


def update_tag_color(name: str, color: str) -> bool:
    """Update a tag's color. Returns True if found."""
    tags = _load_tags()
    for t in tags:
        if t["name"] == name:
            t["color"] = color
            _save_tags(tags)
            return True
    return False


def get_tag_usage(name: str) -> Dict[str, int]:
    """Return usage counts for a tag across feeds and charts."""
    feeds = _load_json_list(_FEEDS_PATH)
    charts = _load_json_list(_CHARTS_PATH)

    feed_count = sum(1 for f in feeds if name in f.get("tags", []))
    chart_count = sum(1 for c in charts if name in c.get("tags", []))

    return {"feeds": feed_count, "charts": chart_count, "total": feed_count + chart_count}


def validate_tags(tag_list: List[str]) -> List[str]:
    """
    Filter a list of tag names to only those in the controlled vocabulary.
    Returns the valid subset.
    """
    valid = set(tag_names())
    return [t for t in tag_list if t in valid]
