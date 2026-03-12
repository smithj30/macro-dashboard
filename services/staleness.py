"""
Feed staleness utilities.

Determines whether a feed's data is stale based on its refresh_schedule
and last_refreshed timestamp.

Thresholds:
  - daily:   fresh <24h, stale 24–40h, very_stale >40h
  - weekly:  fresh <7d,  stale 7–12d,  very_stale >12d
  - monthly: fresh <31d, stale 31–50d, very_stale >50d
  - manual:  always fresh
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Literal

# (expected_hours, very_stale_hours)
_SCHEDULE_THRESHOLDS: Dict[str, tuple[float, float]] = {
    "daily":   (24, 40),
    "weekly":  (7 * 24, 12 * 24),
    "monthly": (31 * 24, 50 * 24),
}


def _parse_last_refreshed(feed: Dict[str, Any]) -> Optional[datetime]:
    """Parse the last_refreshed field from a feed dict."""
    lr = feed.get("last_refreshed")
    if lr is None:
        return None
    if isinstance(lr, datetime):
        return lr
    try:
        return datetime.fromisoformat(str(lr))
    except (ValueError, TypeError):
        return None


def staleness_level(feed: Dict[str, Any]) -> Literal["fresh", "stale", "very_stale"]:
    """Return the staleness level of a feed.

    - "fresh":      within expected schedule interval
    - "stale":      past schedule but within 2x threshold
    - "very_stale": past 2x threshold or never refreshed
    """
    schedule = feed.get("refresh_schedule", "daily").lower()
    if schedule == "manual":
        return "fresh"

    lr = _parse_last_refreshed(feed)
    if lr is None:
        return "very_stale"

    thresholds = _SCHEDULE_THRESHOLDS.get(schedule, _SCHEDULE_THRESHOLDS["daily"])
    expected_hours, very_stale_hours = thresholds
    elapsed = (datetime.now() - lr).total_seconds() / 3600

    if elapsed <= expected_hours:
        return "fresh"
    elif elapsed <= very_stale_hours:
        return "stale"
    else:
        return "very_stale"


def is_stale(feed: Dict[str, Any]) -> bool:
    """Return True if a feed is stale or very_stale."""
    return staleness_level(feed) != "fresh"


def last_refreshed_dt(feed: Dict[str, Any]) -> Optional[datetime]:
    """Return the parsed last_refreshed datetime, or None."""
    return _parse_last_refreshed(feed)
