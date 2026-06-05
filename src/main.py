"""Main entry point for the FIT File Sync Pipeline."""

import argparse
import json
import signal
import shutil
import sys
import threading
from pathlib import Path

from .config import load_config, validate_config, AppConfig
from .download import download_fits
from .logger import setup_logging
from .process import process_fits

# Global shutdown event for graceful termination
shutdown_event = threading.Event()


def handle_signal(signum, frame):
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    shutdown_event.set()


def setup_fit_file_faker(config: AppConfig) -> None:
    """Generate fit-file-faker config from our config into state dir.
    
    Skips if a config already exists (e.g. from interactive --config-menu).
    """
    fff_config_dir = config.state_dir / ".config" / "FitFileFaker"
    config_file = fff_config_dir / ".config.json"

    if config_file.exists():
        return

    fff_config_dir.mkdir(parents=True, exist_ok=True)

    fff_config = {
        "profiles": [
            {
                "name": "default",
                "app_type": "custom",
                "garmin_username": config.fit_file_faker.garmin_username,
                "garmin_password": config.fit_file_faker.garmin_password,
                "fitfiles_path": str(config.download_dir),
                "manufacturer": config.fit_file_faker.device.manufacturer,
                "device": config.fit_file_faker.device.device,
                "serial_number": config.fit_file_faker.device.serial_number,
                "software_version": config.fit_file_faker.device.software_version,
            }
        ],
        "default_profile": "default",
    }

    config_file.write_text(json.dumps(fff_config, indent=2))


def validate_environment(config: AppConfig) -> list[str]:
    """Validate runtime environment. Returns list of errors."""
    errors = []

    if not shutil.which("fit-file-faker"):
        errors.append("fit-file-faker not found on PATH")

    # Create all required directories
    for d in [config.download_dir, config.processed_dir, config.error_dir, config.log_dir, config.state_dir]:
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            errors.append(f"Cannot create directory {d}: {e}")

    return errors


def run_sync_cycle(config: AppConfig, logger) -> None:
    """Execute one full sync cycle (download + process)."""
    logger.info("=== Starting Sync Cycle ===")

    # Step 1: Download
    logger.info("Step 1: Downloading from intervals.icu")
    downloaded = download_fits(config)

    # Step 2: Process and upload
    logger.info("Step 2: Processing and uploading to Garmin")
    counts = process_fits(config)

    logger.info(
        f"=== Sync Cycle Complete === "
        f"(downloaded: {downloaded}, uploaded: {counts['success']}, "
        f"duplicates: {counts['duplicates']}, errors: {counts['errors']})"
    )


def main():
    parser = argparse.ArgumentParser(description="FIT File Sync Pipeline")
    parser.add_argument("--run-once", action="store_true", help="Run a single sync cycle and exit")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual uploads")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show debug output on console")
    parser.add_argument("--config", type=Path, default=Path("/app/config/config.yaml"), help="Path to config file")
    args = parser.parse_args()

    # Load and validate config
    config = load_config(args.config)
    if args.dry_run:
        config.sync.dry_run = True

    config_errors = validate_config(config)
    if config_errors:
        for err in config_errors:
            print(f"CONFIG ERROR: {err}", file=sys.stderr)
        sys.exit(1)

    # Validate environment and create directories (must happen before logging setup)
    env_errors = validate_environment(config)
    if env_errors:
        for err in env_errors:
            print(f"ENVIRONMENT ERROR: {err}", file=sys.stderr)
        sys.exit(1)

    # Setup logging (dirs guaranteed to exist now)
    logger = setup_logging(config.log_dir, verbose=args.verbose)

    # Generate fit-file-faker config
    setup_fit_file_faker(config)

    # Set HOME so garth/fit-file-faker store tokens in state dir
    import os
    os.environ["HOME"] = str(config.state_dir)
    # Also set XDG dirs to keep state contained
    os.environ["XDG_CONFIG_HOME"] = str(config.state_dir / ".config")
    os.environ["XDG_DATA_HOME"] = str(config.state_dir / ".local" / "share")

    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    logger.info("FIT Sync Pipeline started")
    logger.info(f"Sync interval: {config.sync.interval_minutes} minutes")
    if config.sync.dry_run:
        logger.info("DRY RUN mode enabled - no uploads will be performed")

    while True:
        run_sync_cycle(config, logger)

        if args.run_once:
            break

        wait_seconds = config.sync.interval_minutes * 60
        logger.info(f"Waiting {config.sync.interval_minutes} minutes until next sync...")

        if shutdown_event.wait(timeout=wait_seconds):
            logger.info("Shutdown signal received, exiting gracefully")
            break

    logger.info("FIT Sync Pipeline stopped")


if __name__ == "__main__":
    main()
