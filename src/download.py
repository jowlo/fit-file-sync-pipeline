"""Download FIT files from intervals.icu API."""

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


def download_fits(config: AppConfig, oldest_date: str | None = None, newest_date: str | None = None) -> int:
    """Download FIT files from intervals.icu. Returns number of files downloaded."""
    logger.info("=== Starting Download from intervals.icu ===")

    download_dir = config.download_dir
    processed_dir = config.processed_dir
    download_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    headers = _get_auth_header(config.intervals.api_key)

    # Calculate date range
    if not oldest_date:
        oldest_date = (datetime.now() - timedelta(days=config.sync.lookback_days)).strftime("%Y-%m-%d")

    # Build URL - omit newest when not specified so API defaults to "now"
    url = f"{API_BASE}/athlete/0/activities?oldest={oldest_date}"
    if newest_date:
        url += f"&newest={newest_date}"
        logger.info(f"Date range: {oldest_date} to {newest_date}")
    else:
        logger.info(f"Date range: {oldest_date} to now")

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        activities = resp.json()
    except requests.RequestException as e:
        logger.error(f"ERROR fetching activities: {e}")
        return 0

    logger.info(f"API response: {len(activities)} total activities")

    if activities:
        activity_ids = [a["id"] for a in activities]
        logger.debug(f"Activity IDs: {', '.join(str(aid) for aid in activity_ids)}")

    # Filter to activities with files
    activities_with_files = [a for a in activities if a.get("file_type")]
    logger.info(f"Activities with files: {len(activities_with_files)}")

    # Filter by source if configured
    if config.sync.sources:
        before_count = len(activities_with_files)
        activities_with_files = [
            a for a in activities_with_files
            if (a.get("source") or "").upper() in config.sync.sources
        ]
        logger.info(f"After source filter ({', '.join(config.sync.sources)}): {len(activities_with_files)}/{before_count}")

    activities_without_files = [a for a in activities if not a.get("file_type")]
    if activities_without_files:
        missing_ids = [a["id"] for a in activities_without_files]
        logger.warning(f"Activities WITHOUT file_type (cannot download): {', '.join(str(mid) for mid in missing_ids)}")

    if not activities_with_files:
        logger.warning("No activities with files found")
        return 0

    success = 0
    total = len(activities_with_files)

    for i, activity in enumerate(activities_with_files, 1):
        activity_id = activity["id"]
        date = activity["start_date_local"][:10]
        output_file = download_dir / f"{date}-{activity_id}.fit"

        # Skip if already downloaded
        if output_file.exists():
            logger.info(f"[{i}/{total}] Skipping {activity_id} (already exists)")
            continue

        # Skip if already processed
        processed_file = processed_dir / f"{date}-{activity_id}.uploaded.fit"
        if processed_file.exists():
            logger.info(f"[{i}/{total}] Skipping {activity_id} (already processed)")
            continue

        logger.info(f"[{i}/{total}] Downloading {activity_id} - {date}")

        try:
            file_url = f"{API_BASE}/activity/{activity_id}/file"
            file_resp = requests.get(file_url, headers=headers, timeout=60)
            file_resp.raise_for_status()

            output_file.write_bytes(file_resp.content)

            file_size = output_file.stat().st_size
            if file_size > 0:
                logger.info(f"  SUCCESS: {file_size} bytes")
                success += 1
            else:
                logger.error("  File is empty")
                output_file.unlink()
        except requests.RequestException as e:
            logger.error(f"  ERROR: {e}")
            if output_file.exists():
                output_file.unlink()

        time.sleep(config.sync.delay_between_files_ms / 1000.0)

    logger.info(f"Download complete: {success}/{total} files")
    return success
