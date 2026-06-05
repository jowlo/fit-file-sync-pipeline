"""Deduplicate activities on intervals.icu after Garmin upload.

When we upload a modified FIT file to Garmin Connect, Garmin syncs it back
to intervals.icu as a GARMIN_CONNECT activity. This creates a duplicate of
the original OAUTH_CLIENT activity. This module detects and removes those
duplicates by matching start times of processed files against GARMIN_CONNECT
activities.
"""

import base64
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

from .config import AppConfig

logger = logging.getLogger("fit-sync")

API_BASE = "https://intervals.icu/api/v1"


def _get_auth_header(api_key: str) -> dict[str, str]:
    """Build Basic Auth header for intervals.icu API."""
    token = base64.b64encode(f"API_KEY:{api_key}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _parse_processed_dates(processed_dir: Path) -> list[str]:
    """Extract activity IDs from processed filenames.
    
    Filenames are like: 2026-06-03-i154042128.uploaded.fit
    Returns list of activity IDs like 'i154042128'.
    """
    ids = []
    for f in processed_dir.glob("*.uploaded.fit"):
        # Parse: YYYY-MM-DD-{activity_id}.uploaded.fit
        parts = f.stem.replace(".uploaded", "").split("-", 3)
        if len(parts) >= 4:
            ids.append(parts[3])
    return ids


def deduplicate_intervals(config: AppConfig) -> int:
    """Find and delete GARMIN_CONNECT duplicates of our uploaded activities.
    
    Logic:
    1. Get start times of all processed (uploaded) activities from intervals.icu
    2. Find GARMIN_CONNECT activities with matching start times (within 2 min)
    3. Delete the GARMIN_CONNECT duplicates
    
    Returns number of duplicates deleted.
    """
    logger.info("=== Checking for duplicates on intervals.icu ===")
    
    headers = _get_auth_header(config.intervals.api_key)
    processed_dir = config.processed_dir

    # Get IDs of activities we've processed
    processed_ids = _parse_processed_dates(processed_dir)
    if not processed_ids:
        logger.info("No processed files found, skipping dedup")
        return 0

    logger.debug(f"Processed activity IDs: {processed_ids}")

    # Fetch recent activities from intervals.icu
    oldest_date = (datetime.now() - timedelta(days=config.sync.lookback_days)).strftime("%Y-%m-%d")
    url = f"{API_BASE}/athlete/0/activities?oldest={oldest_date}"

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        activities = resp.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch activities for dedup: {e}")
        return 0

    # Build lookup: start_time -> OAUTH_CLIENT activities (our originals)
    original_times = {}
    garmin_activities = []

    for a in activities:
        source = (a.get("source") or "").upper()
        activity_id = a.get("id", "")
        start = a.get("start_date_local", "")

        if activity_id in processed_ids and source != "GARMIN_CONNECT":
            # This is one of our original activities that we uploaded
            original_times[start[:16]] = a  # Match to the minute
        elif source == "GARMIN_CONNECT":
            garmin_activities.append(a)

    if not original_times:
        logger.info("No matching original activities found, skipping dedup")
        return 0

    logger.debug(f"Original activity times: {list(original_times.keys())}")
    logger.debug(f"GARMIN_CONNECT activities to check: {len(garmin_activities)}")

    # Find GARMIN_CONNECT duplicates (same start time within 2 minutes)
    duplicates = []
    for ga in garmin_activities:
        ga_start = ga.get("start_date_local", "")[:16]
        ga_type = ga.get("type", "")

        for orig_time, orig in original_times.items():
            # Check if start times match within 2 minutes
            try:
                ga_dt = datetime.fromisoformat(ga_start)
                orig_dt = datetime.fromisoformat(orig_time)
                diff = abs((ga_dt - orig_dt).total_seconds())
                if diff <= 120:  # Within 2 minutes
                    duplicates.append(ga)
                    logger.info(
                        f"  Duplicate found: {ga['id']} (GARMIN_CONNECT, {ga_start}) "
                        f"matches {orig['id']} (diff: {int(diff)}s)"
                    )
                    break
            except (ValueError, TypeError):
                continue

    if not duplicates:
        logger.info("No duplicates found")
        return 0

    # Delete duplicates
    deleted = 0
    for dup in duplicates:
        dup_id = dup["id"]
        if config.sync.dry_run:
            logger.info(f"  DRY RUN: Would delete {dup_id}")
            deleted += 1
            continue

        try:
            del_url = f"{API_BASE}/activity/{dup_id}"
            del_resp = requests.delete(del_url, headers=headers, timeout=30)
            del_resp.raise_for_status()
            logger.info(f"  Deleted duplicate: {dup_id}")
            deleted += 1
            time.sleep(0.5)  # Rate limiting
        except requests.RequestException as e:
            logger.error(f"  Failed to delete {dup_id}: {e}")

    logger.info(f"Deduplication complete: {deleted} duplicates removed")
    return deleted
