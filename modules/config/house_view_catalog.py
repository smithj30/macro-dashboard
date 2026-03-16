"""
House View catalog storage layer.

Manages the living House View document — a structured set of macro theme
sections with bullets and supporting chart references.

Storage: catalogs/house_view.json
Backup:  catalogs/house_view_backup.json (auto-created before each save)
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_HV_PATH = Path(__file__).parent.parent.parent / "catalogs" / "house_view.json"
_BACKUP_PATH = _HV_PATH.parent / "house_view_backup.json"


def _ensure_dir() -> None:
    _HV_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_house_view() -> Dict[str, Any]:
    """Load the House View document from disk."""
    if not _HV_PATH.exists():
        return {
            "title": "Kennedy Lewis \u2014 House View",
            "last_updated": None,
            "sections": [],
        }
    try:
        with open(_HV_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"title": "Kennedy Lewis \u2014 House View", "last_updated": None, "sections": []}
        data.setdefault("sections", [])
        return data
    except (json.JSONDecodeError, OSError):
        # Try backup
        if _BACKUP_PATH.exists():
            try:
                with open(_BACKUP_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"title": "Kennedy Lewis \u2014 House View", "last_updated": None, "sections": []}


def save_house_view(data: Dict[str, Any]) -> None:
    """Save the House View document. Auto-backs up before writing."""
    _ensure_dir()
    # Auto-backup
    if _HV_PATH.exists():
        shutil.copy2(_HV_PATH, _BACKUP_PATH)
    data["last_updated"] = datetime.now().isoformat()
    with open(_HV_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Section helpers
# ---------------------------------------------------------------------------


def _find_section(data: Dict[str, Any], theme: str) -> Optional[Dict[str, Any]]:
    for sec in data.get("sections", []):
        if sec.get("theme") == theme:
            return sec
    return None


def add_section(theme: str, title: str) -> Dict[str, Any]:
    """Add a new section. Returns the updated document."""
    data = load_house_view()
    if _find_section(data, theme):
        return data  # already exists
    data["sections"].append({
        "theme": theme,
        "title": title,
        "bullets": [],
    })
    save_house_view(data)
    return data


def delete_section(theme: str) -> Dict[str, Any]:
    """Delete a section by theme. Returns the updated document."""
    data = load_house_view()
    data["sections"] = [s for s in data["sections"] if s.get("theme") != theme]
    save_house_view(data)
    return data


# ---------------------------------------------------------------------------
# Bullet helpers
# ---------------------------------------------------------------------------


def add_bullet(theme: str, text: str) -> Dict[str, Any]:
    """Add a bullet to a section. Returns the updated document."""
    data = load_house_view()
    sec = _find_section(data, theme)
    if sec is None:
        return data
    sec["bullets"].append({
        "text": text,
        "updated_at": datetime.now().isoformat(),
        "supporting_charts": [],
    })
    save_house_view(data)
    return data


def update_bullet(theme: str, index: int, text: str) -> Dict[str, Any]:
    """Update a bullet's text. Returns the updated document."""
    data = load_house_view()
    sec = _find_section(data, theme)
    if sec is None or index < 0 or index >= len(sec["bullets"]):
        return data
    sec["bullets"][index]["text"] = text
    sec["bullets"][index]["updated_at"] = datetime.now().isoformat()
    save_house_view(data)
    return data


def delete_bullet(theme: str, index: int) -> Dict[str, Any]:
    """Delete a bullet from a section. Returns the updated document."""
    data = load_house_view()
    sec = _find_section(data, theme)
    if sec is None or index < 0 or index >= len(sec["bullets"]):
        return data
    sec["bullets"].pop(index)
    save_house_view(data)
    return data


def attach_chart_to_bullet(
    theme: str, bullet_index: int, chart_ref: str
) -> Dict[str, Any]:
    """Attach a chart reference to a bullet. Returns the updated document."""
    data = load_house_view()
    sec = _find_section(data, theme)
    if sec is None or bullet_index < 0 or bullet_index >= len(sec["bullets"]):
        return data
    charts = sec["bullets"][bullet_index].setdefault("supporting_charts", [])
    if chart_ref not in charts:
        charts.append(chart_ref)
    save_house_view(data)
    return data


def detach_chart_from_bullet(
    theme: str, bullet_index: int, chart_ref: str
) -> Dict[str, Any]:
    """Remove a chart reference from a bullet. Returns the updated document."""
    data = load_house_view()
    sec = _find_section(data, theme)
    if sec is None or bullet_index < 0 or bullet_index >= len(sec["bullets"]):
        return data
    charts = sec["bullets"][bullet_index].get("supporting_charts", [])
    if chart_ref in charts:
        charts.remove(chart_ref)
    save_house_view(data)
    return data
