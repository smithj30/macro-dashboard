"""
Content piece catalog storage layer.

Manages content pieces (emails, distributions, posts) for the Content Composer.

Storage: catalogs/content_pieces.json — a flat JSON array of content piece dicts.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_CATALOG_PATH = Path(__file__).parent.parent.parent / "catalogs" / "content_pieces.json"


def _ensure_dir() -> None:
    _CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_all() -> List[Dict[str, Any]]:
    if not _CATALOG_PATH.exists():
        _ensure_dir()
        with open(_CATALOG_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)
        return []
    try:
        with open(_CATALOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_all(items: List[Dict[str, Any]]) -> None:
    _ensure_dir()
    with open(_CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, default=str)


def _gen_id() -> str:
    return f"cp_{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_content_pieces(
    content_type: Optional[str] = None,
    status: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Return all content pieces, optionally filtered."""
    items = _load_all()
    if content_type:
        items = [i for i in items if i.get("type") == content_type]
    if status:
        items = [i for i in items if i.get("status") == status]
    if tags:
        tag_set = set(t.lower() for t in tags)
        items = [
            i for i in items
            if tag_set & set(t.lower() for t in i.get("tags", []))
        ]
    items.sort(key=lambda i: i.get("updated_at", ""), reverse=True)
    return items


def get_content_piece(piece_id: str) -> Optional[Dict[str, Any]]:
    """Return a single content piece by ID, or None."""
    for item in _load_all():
        if item.get("id") == piece_id:
            return item
    return None


def save_content_piece(piece: Dict[str, Any]) -> str:
    """Create or update a content piece. Returns the piece ID."""
    items = _load_all()
    now = datetime.now().isoformat()

    piece_id = piece.get("id")
    if piece_id:
        for idx, existing in enumerate(items):
            if existing.get("id") == piece_id:
                existing.update(piece)
                existing["updated_at"] = now
                items[idx] = existing
                _save_all(items)
                return piece_id

    # Create new
    if not piece_id:
        piece_id = _gen_id()
        piece["id"] = piece_id
    piece.setdefault("created_at", now)
    piece["updated_at"] = now
    piece.setdefault("status", "draft")
    piece.setdefault("charts", [])
    piece.setdefault("commentary", [])
    piece.setdefault("export_history", [])
    piece.setdefault("tags", [])
    items.append(piece)
    _save_all(items)
    return piece_id


def delete_content_piece(piece_id: str) -> bool:
    """Delete a content piece by ID. Returns True if deleted."""
    items = _load_all()
    new_items = [i for i in items if i.get("id") != piece_id]
    if len(new_items) == len(items):
        return False
    _save_all(new_items)
    return True
