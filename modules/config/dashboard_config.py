"""
Dashboard configuration storage layer.

All dashboard configs live in dashboards/<id>.json relative to the project root.
This module provides read/write helpers used by both the static dashboard overrides
and the dynamic Dashboard Builder.
"""

from __future__ import annotations

import json
import os
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
    dashboard_id = config.get("id", "unknown")
    path = _config_path(dashboard_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, default=str)


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
