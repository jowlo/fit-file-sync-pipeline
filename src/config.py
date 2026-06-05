"""Configuration loading and validation."""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class IntervalsConfig:
    api_key: str = ""


@dataclass
class SyncConfig:
    interval_minutes: int = 60
    lookback_days: int = 7
    delay_between_files_ms: int = 100
    dry_run: bool = False
    sources: list[str] | None = None  # Filter by source, e.g. ["WAHOO", "HAMMERHEAD"]


@dataclass
class DeviceConfig:
    manufacturer: int = 1  # 1 = Garmin
    device: int = 3121  # 3121 = Edge 1030
    serial_number: int | str = 3982691993
    software_version: int | None = None


@dataclass
class FitFileFakerConfig:
    garmin_username: str = ""
    garmin_password: str = ""
    device: DeviceConfig = field(default_factory=DeviceConfig)


@dataclass
class AppConfig:
    intervals: IntervalsConfig = field(default_factory=IntervalsConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)
    fit_file_faker: FitFileFakerConfig = field(default_factory=FitFileFakerConfig)

    # Resolved paths
    data_dir: Path = Path("/app/data")
    log_dir: Path = Path("/app/logs")
    state_dir: Path = Path("/app/state")

    @property
    def download_dir(self) -> Path:
        return self.data_dir / "downloaded"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def error_dir(self) -> Path:
        return self.data_dir / "errors"


def load_config(config_path: Path) -> AppConfig:
    """Load configuration from YAML file, with env var overrides for secrets."""
    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    config = AppConfig()

    # Intervals config
    intervals_raw = raw.get("intervals", {})
    config.intervals.api_key = (
        os.environ.get("INTERVALS_API_KEY") or intervals_raw.get("api_key", "")
    )

    # Sync config
    sync_raw = raw.get("sync", {})
    config.sync.interval_minutes = sync_raw.get("interval_minutes", 60)
    config.sync.lookback_days = sync_raw.get("lookback_days", 7)
    config.sync.delay_between_files_ms = sync_raw.get("delay_between_files_ms", 100)
    config.sync.dry_run = sync_raw.get("dry_run", False)
    sources = sync_raw.get("sources", None)
    if sources:
        config.sync.sources = [s.upper() for s in sources]

    # Fit-File-Faker config
    fff_raw = raw.get("fit_file_faker", {})
    config.fit_file_faker.garmin_username = (
        os.environ.get("GARMIN_USERNAME") or fff_raw.get("garmin_username", "")
    )
    config.fit_file_faker.garmin_password = (
        os.environ.get("GARMIN_PASSWORD") or fff_raw.get("garmin_password", "")
    )
    device_raw = fff_raw.get("device", {})
    config.fit_file_faker.device.manufacturer = device_raw.get("manufacturer", 1)
    config.fit_file_faker.device.device = device_raw.get("device", 3121)
    config.fit_file_faker.device.serial_number = device_raw.get("serial_number", 3982691993)
    config.fit_file_faker.device.software_version = device_raw.get("software_version", None)

    # Paths (allow override via env)
    config.data_dir = Path(os.environ.get("DATA_DIR", "/app/data"))
    config.log_dir = Path(os.environ.get("LOG_DIR", "/app/logs"))
    config.state_dir = Path(os.environ.get("STATE_DIR", "/app/state"))

    return config


def validate_config(config: AppConfig) -> list[str]:
    """Validate configuration, return list of errors."""
    errors = []

    if not config.intervals.api_key:
        errors.append("intervals.api_key is required (set in config or INTERVALS_API_KEY env var)")

    if not config.fit_file_faker.garmin_username:
        errors.append("fit_file_faker.garmin_username is required (set in config or GARMIN_USERNAME env var)")

    if not config.fit_file_faker.garmin_password:
        errors.append("fit_file_faker.garmin_password is required (set in config or GARMIN_PASSWORD env var)")

    return errors
