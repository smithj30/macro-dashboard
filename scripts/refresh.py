#!/usr/bin/env python3
"""
Feed Refresh Script — can be run via cron or manually.

Usage:
    python scripts/refresh.py              # refresh all feeds due for update
    python scripts/refresh.py --all        # refresh all feeds regardless
    python scripts/refresh.py --feed ID    # refresh a specific feed
    python scripts/refresh.py --provider X # refresh all feeds from provider X

The script loads feed definitions from catalogs/feeds.json, fetches fresh
data via the appropriate provider, caches it to disk, and logs results
to data/refresh_log.json.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.config.feed_catalog import list_feeds, get_feed, mark_refreshed
from providers import get_provider


# ---------------------------------------------------------------------------
# Refresh log
# ---------------------------------------------------------------------------

_LOG_PATH = PROJECT_ROOT / "data" / "refresh_log.json"


def _load_log() -> list:
    if not _LOG_PATH.exists():
        return []
    try:
        with open(_LOG_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _append_log(entry: dict) -> None:
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log = _load_log()
    log.append(entry)
    # Keep last 500 entries
    if len(log) > 500:
        log = log[-500:]
    with open(_LOG_PATH, "w") as f:
        json.dump(log, f, indent=2, default=str)


def get_refresh_log(limit: int = 50) -> list:
    """Return recent refresh log entries."""
    log = _load_log()
    return log[-limit:]


# ---------------------------------------------------------------------------
# Schedule logic
# ---------------------------------------------------------------------------

_SCHEDULE_DELTAS = {
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
    "monthly": timedelta(days=28),
}


def _is_due(feed: dict) -> bool:
    """Check if a feed is due for refresh based on its schedule."""
    schedule = feed.get("refresh_schedule", "daily")
    if schedule == "manual":
        return False

    # Re-read from disk to get current last_refreshed
    fresh = get_feed(feed["id"])
    last_refreshed = (fresh or feed).get("last_refreshed")
    if not last_refreshed:
        return True

    try:
        last_dt = datetime.fromisoformat(last_refreshed)
    except (ValueError, TypeError):
        return True

    delta = _SCHEDULE_DELTAS.get(schedule, timedelta(days=1))
    return datetime.now() - last_dt > delta


# ---------------------------------------------------------------------------
# Cache to disk
# ---------------------------------------------------------------------------

_CACHE_DIR = PROJECT_ROOT / "data" / "cache"


def _cache_feed_data(feed: dict, df) -> str:
    """Cache feed data to disk. Returns the cache path."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{feed['provider']}_{feed['series_id'].replace('/', '_')}"

    # Try Parquet first, fall back to CSV
    try:
        path = _CACHE_DIR / f"{filename}.parquet"
        df.to_parquet(path)
        return str(path)
    except Exception:
        path = _CACHE_DIR / f"{filename}.csv"
        df.to_csv(path)
        return str(path)


# ---------------------------------------------------------------------------
# Refresh execution
# ---------------------------------------------------------------------------

def refresh_feed(feed: dict, force: bool = False) -> dict:
    """
    Refresh a single feed. Returns a result dict.
    """
    feed_id = feed["id"]
    result = {
        "feed_id": feed_id,
        "feed_name": feed["name"],
        "provider": feed["provider"],
        "series_id": feed["series_id"],
        "timestamp": datetime.now().isoformat(),
        "success": False,
        "error": None,
        "rows": 0,
        "cache_path": None,
    }

    if not force and not _is_due(feed):
        result["error"] = "not_due"
        return result

    try:
        provider = get_provider(feed["provider"])
        kwargs = feed.get("kwargs", {})
        df = provider.fetch_series(feed["series_id"], **kwargs)

        if df is not None and not df.empty:
            cache_path = _cache_feed_data(feed, df)
            mark_refreshed(feed_id)
            result["success"] = True
            result["rows"] = len(df)
            result["cache_path"] = cache_path
        else:
            result["error"] = "empty_data"

    except Exception as e:
        result["error"] = str(e)

    _append_log(result)
    return result


def refresh_all(force: bool = False, provider_filter: str = None) -> list:
    """Refresh all feeds (or all from a specific provider). Returns list of results."""
    feeds = list_feeds(provider=provider_filter)
    results = []
    for feed in feeds:
        result = refresh_feed(feed, force=force)
        results.append(result)
        status = "OK" if result["success"] else result.get("error", "failed")
        print(f"  {feed['name']} ({feed['provider']}:{feed['series_id']}): {status}")
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Refresh data feeds")
    parser.add_argument("--all", action="store_true", help="Refresh all feeds regardless of schedule")
    parser.add_argument("--feed", type=str, help="Refresh a specific feed by ID")
    parser.add_argument("--provider", type=str, help="Refresh all feeds from a specific provider")
    args = parser.parse_args()

    print(f"Feed refresh started at {datetime.now().isoformat()}")
    print("-" * 60)

    if args.feed:
        feed = get_feed(args.feed)
        if not feed:
            print(f"Feed not found: {args.feed}")
            sys.exit(1)
        result = refresh_feed(feed, force=True)
        status = "OK" if result["success"] else result.get("error", "failed")
        print(f"  {feed['name']}: {status}")
    else:
        results = refresh_all(force=args.all, provider_filter=args.provider)
        ok = sum(1 for r in results if r["success"])
        skipped = sum(1 for r in results if r.get("error") == "not_due")
        failed = sum(1 for r in results if not r["success"] and r.get("error") != "not_due")
        print("-" * 60)
        print(f"Done: {ok} refreshed, {skipped} skipped (not due), {failed} failed")


if __name__ == "__main__":
    main()
