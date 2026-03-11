#!/usr/bin/env python3
"""
Feed Refresh Script — standalone CLI, no Streamlit dependency.

Usage:
    python scripts/refresh.py              # refresh all stale feeds
    python scripts/refresh.py --force      # refresh all non-manual feeds
    python scripts/refresh.py --dry-run    # report what would refresh
    python scripts/refresh.py --provider X # only feeds from provider X
    python scripts/refresh.py --feed ID    # refresh a specific feed

Staleness rules:
    daily   — stale if last_refreshed is null or >20 hours ago
    weekly  — stale if null or >6 days ago
    monthly — stale if null or >25 days ago
    manual  — never auto-refreshed
"""

import argparse
import json
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
    "daily": timedelta(hours=20),
    "weekly": timedelta(days=6),
    "monthly": timedelta(days=25),
}


def _is_stale(feed: dict) -> bool:
    """Check if a feed is stale based on its refresh_schedule and last_refreshed."""
    schedule = feed.get("refresh_schedule", "daily")
    if schedule == "manual":
        return False

    last_refreshed = feed.get("last_refreshed")
    if not last_refreshed:
        return True

    try:
        last_dt = datetime.fromisoformat(last_refreshed)
    except (ValueError, TypeError):
        return True

    delta = _SCHEDULE_DELTAS.get(schedule, timedelta(hours=20))
    return datetime.now() - last_dt > delta


# ---------------------------------------------------------------------------
# Cache to disk
# ---------------------------------------------------------------------------

_CACHE_DIR = PROJECT_ROOT / "data" / "cache"


def _cache_feed_data(feed: dict, df) -> str:
    """Save DataFrame as parquet to data/cache/{provider}/{feed_id}.parquet."""
    provider_dir = _CACHE_DIR / feed["provider"]
    provider_dir.mkdir(parents=True, exist_ok=True)
    path = provider_dir / f"{feed['id']}.parquet"
    df.to_parquet(path)
    return str(path)


# ---------------------------------------------------------------------------
# Refresh execution
# ---------------------------------------------------------------------------

def refresh_feed(feed: dict, force: bool = False, dry_run: bool = False) -> dict:
    """
    Refresh a single feed. Returns a result dict.
    """
    feed_id = feed["id"]
    stale = _is_stale(feed)
    result = {
        "feed_id": feed_id,
        "feed_name": feed["name"],
        "provider": feed["provider"],
        "series_id": feed["series_id"],
        "timestamp": datetime.now().isoformat(),
        "success": False,
        "skipped": False,
        "error": None,
        "rows": 0,
        "cache_path": None,
    }

    # Skip manual feeds unless forced with --feed (handled by caller)
    if feed.get("refresh_schedule") == "manual" and not force:
        result["skipped"] = True
        result["error"] = "manual_schedule"
        return result

    # Skip non-stale feeds unless forced
    if not stale and not force:
        result["skipped"] = True
        result["error"] = "not_stale"
        return result

    if dry_run:
        result["error"] = "dry_run"
        return result

    try:
        provider = get_provider(feed["provider"])
        params = feed.get("params", {})
        # Remove series_id from params if present — it's passed as first arg
        params_copy = {k: v for k, v in params.items() if k != "series_id"}
        df = provider.fetch_series(feed["series_id"], **params_copy)

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


def refresh_all(
    force: bool = False,
    dry_run: bool = False,
    provider_filter: str = None,
) -> list:
    """Refresh all feeds (or filtered by provider). Returns list of results."""
    feeds = list_feeds(provider=provider_filter)
    results = []
    for feed in feeds:
        result = refresh_feed(feed, force=force, dry_run=dry_run)
        results.append(result)

        # Print per-feed status
        if result["skipped"]:
            reason = result.get("error", "skipped")
            print(f"  SKIP  {feed['name']} [{feed['provider']}] — {reason}")
        elif result.get("error") == "dry_run":
            print(f"  WOULD {feed['name']} [{feed['provider']}]")
        elif result["success"]:
            print(f"  OK    {feed['name']} [{feed['provider']}] — {result['rows']} rows")
        else:
            print(f"  FAIL  {feed['name']} [{feed['provider']}] — {result['error']}")

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Refresh data feeds")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report what would refresh without doing it",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Refresh all non-manual feeds regardless of staleness",
    )
    parser.add_argument(
        "--provider", type=str,
        help="Only refresh feeds from this provider",
    )
    parser.add_argument(
        "--feed", type=str,
        help="Refresh a specific feed by ID",
    )
    args = parser.parse_args()

    print(f"Feed refresh — {datetime.now().isoformat()}")
    if args.dry_run:
        print("(DRY RUN — no data will be fetched or saved)")
    print("-" * 60)

    if args.feed:
        feed = get_feed(args.feed)
        if not feed:
            print(f"Feed not found: {args.feed}")
            sys.exit(1)
        result = refresh_feed(feed, force=True, dry_run=args.dry_run)
        if result.get("error") == "dry_run":
            print(f"  WOULD {feed['name']} [{feed['provider']}]")
        elif result["success"]:
            print(f"  OK    {feed['name']} — {result['rows']} rows")
        else:
            print(f"  FAIL  {feed['name']} — {result['error']}")
        results = [result]
    else:
        results = refresh_all(
            force=args.force, dry_run=args.dry_run, provider_filter=args.provider,
        )

    # Summary
    checked = len(results)
    refreshed = sum(1 for r in results if r["success"])
    skipped = sum(1 for r in results if r.get("skipped"))
    dry = sum(1 for r in results if r.get("error") == "dry_run")
    failures = [r for r in results if not r["success"] and not r.get("skipped") and r.get("error") != "dry_run"]

    print("-" * 60)
    parts = [f"{checked} checked"]
    if refreshed:
        parts.append(f"{refreshed} refreshed")
    if skipped:
        parts.append(f"{skipped} skipped")
    if dry:
        parts.append(f"{dry} would refresh")
    if failures:
        parts.append(f"{len(failures)} failed")
    print(f"Summary: {', '.join(parts)}")

    if failures:
        print("\nFailures:")
        for r in failures:
            print(f"  - {r['feed_name']} ({r['provider']}:{r['series_id']}): {r['error']}")


if __name__ == "__main__":
    main()
