"""Process FIT files with fit-file-faker and upload to Garmin Connect."""

import logging
import re
import shutil
import subprocess
from pathlib import Path

from .config import AppConfig

logger = logging.getLogger("fit-sync")


def process_fits(config: AppConfig) -> dict[str, int]:
    """Process downloaded FIT files. Returns dict with counts."""
    logger.info("=== Starting FIT File Processing ===")

    download_dir = config.download_dir
    processed_dir = config.processed_dir
    error_dir = config.error_dir

    processed_dir.mkdir(parents=True, exist_ok=True)
    error_dir.mkdir(parents=True, exist_ok=True)

    # Get files to process (exclude _modified.fit files)
    fit_files = sorted(
        f for f in download_dir.glob("*.fit")
        if not f.name.endswith("_modified.fit")
    )

    if not fit_files:
        logger.info("No files to process - skipping Garmin upload")
        return {"success": 0, "duplicates": 0, "errors": 0, "rate_limited": 0}

    logger.info(f"Found {len(fit_files)} files to process")

    success = 0
    errors = 0
    duplicates = 0
    rate_limited = False

    for i, fit_file in enumerate(fit_files, 1):
        logger.info(f"[{i}/{len(fit_files)}] Processing: {fit_file.name}")

        if rate_limited:
            logger.warning("  Skipping - Garmin rate limit active, will retry next cycle")
            continue

        if config.sync.dry_run:
            logger.warning("  Skipping (DryRun mode enabled)")
            continue

        try:
            result = subprocess.run(
                ["fit-file-faker", str(fit_file), "--upload"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )

            output = result.stdout + "\n" + result.stderr

            # Log full output at debug level, and abbreviated at info level
            logger.debug(f"  fit-file-faker stdout: {result.stdout.strip()}")
            logger.debug(f"  fit-file-faker stderr: {result.stderr.strip()}")
            logger.info(f"  Exit code: {result.returncode}")
            if result.returncode != 0:
                # Show last few lines of output on non-zero exit
                output_lines = output.strip().splitlines()
                for line in output_lines[-5:]:
                    logger.info(f"  | {line}")

            # Check for rate limiting (429) or Garmin temporary rejection (403 after successful uploads)
            is_rate_limited = bool(re.search(
                r"429|rate limit|All login strategies exhausted|API Error 403", output, re.IGNORECASE
            ))
            if is_rate_limited:
                rate_limited = True
                logger.warning("  Garmin rate limit detected - file will remain in downloaded for next cycle")
                continue

            # Check for duplicate
            is_duplicate = bool(re.search(
                r"activity already exists|HTTP conflict|Received HTTP conflict|API Error 409|Duplicate Activity",
                output, re.IGNORECASE
            ))

            # Check for upload success
            # Only match actual log output lines, not source code in tracebacks
            # Successful upload produces a line starting with log prefix containing the success message
            upload_success = is_duplicate

            if result.returncode == 0:
                # Exit code 0 means fit-file-faker completed successfully
                upload_success = True

            logger.debug(f"  Detection: rate_limited={is_rate_limited}, duplicate={is_duplicate}, upload_success={upload_success}")

            # Check for genuine errors (narrow patterns only)
            has_exception = bool(re.search(r"Login failed|No profiles configured", output, re.IGNORECASE))

            if has_exception and not upload_success:
                raise RuntimeError(f"Fit-File-Faker error: {output.strip()[-200:]}")

            # If no success indicator and no duplicate, treat as error
            if not upload_success and not is_duplicate:
                raise RuntimeError(f"No upload confirmation in output: {output.strip()[-200:]}")

            # Move to processed
            new_name = f"{fit_file.stem}.uploaded{fit_file.suffix}"
            destination = processed_dir / new_name
            shutil.move(str(fit_file), str(destination))

            # Clean up _modified.fit file if it exists
            modified_file = fit_file.parent / f"{fit_file.stem}_modified{fit_file.suffix}"
            if modified_file.exists():
                modified_file.unlink()

            if is_duplicate:
                logger.warning("  Already uploaded (duplicate detected)")
                logger.info("  Moved to processed/ (was duplicate)")
                duplicates += 1
            else:
                logger.info("  SUCCESS: Uploaded and moved to processed/")
                success += 1

        except (subprocess.TimeoutExpired, RuntimeError, OSError) as e:
            logger.error(f"  ERROR: {e}")
            destination = error_dir / fit_file.name
            shutil.move(str(fit_file), str(destination))
            logger.warning("  Moved to errors/")
            errors += 1

    counts = {"success": success, "duplicates": duplicates, "errors": errors, "rate_limited": int(rate_limited)}

    if rate_limited:
        logger.warning(
            f"Sync incomplete - Garmin rate limit active. "
            f"{success} uploaded, {duplicates} duplicates, {errors} errors. "
            f"Remaining files will retry next cycle."
        )
    else:
        logger.info(f"Processing complete: {success} uploaded, {duplicates} duplicates, {errors} errors")

    return counts
