# FIT File Sync Pipeline

Automated pipeline that syncs workout data from intervals.icu to Garmin Connect by leveraging [Fit-File-Faker](https://github.com/jat255/Fit-File-Faker) to transform FIT files from non-Garmin devices into Garmin-compatible format.

Runs as a Docker container on Linux with automatic scheduled syncing.

## Why This Tool?

**The Problem:** Many athletes use non-Garmin devices (Coros, Hammerhead, Wahoo, etc.) but want to access Garmin's ecosystem:
- Training Status and Training Readiness
- Body Battery and HRV Status
- Performance metrics (VO2 max, Training Load, etc.)
- Garmin Coach training plans
- Complete activity history in one place

**The Solution:** This pipeline automatically:
1. Downloads your workout FIT files from intervals.icu
2. Processes them with Fit-File-Faker to appear as Garmin-created files
3. Uploads them to Garmin Connect
4. Runs on a schedule to keep everything in sync

## How It Works
```
intervals.icu → Download → Fit-File-Faker → Garmin Connect
                  ↓           (Transform)         ↓
              downloaded/                    All Garmin
                  ↓                          Metrics Available
              processed/ ✓
                  ↓
              errors/ ✗
```

**Key Component:** [Fit-File-Faker](https://github.com/jat255/Fit-File-Faker) does the heavy lifting by modifying FIT file device information so Garmin Connect accepts files from non-Garmin devices. This pipeline automates the entire workflow.

## Features

- 📥 **Automated Downloads** - Pulls original FIT files from intervals.icu API
- 🔧 **Device Transformation** - Uses Fit-File-Faker to make files Garmin-compatible
- 📤 **Automatic Upload** - Sends processed files to Garmin Connect
- 🔄 **Scheduled Sync** - Runs on a configurable interval (default: hourly)
- 🐳 **Docker Compose** - Simple deployment on any Linux host
- 📋 **Detailed Logging** - Tracks all operations (stdout + daily log files)
- ❌ **Error Handling** - Quarantines problematic files for manual review
- ⏸️ **Rate Limit Protection** - Detects Garmin rate limiting and retries next cycle
- 🛑 **Graceful Shutdown** - Handles SIGTERM cleanly for container restarts

## Prerequisites

- **Docker** and **Docker Compose**
- **intervals.icu account** with API key ([get here](https://intervals.icu/settings))
- **Garmin Connect account** (username and password)

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/jowlo/fit-file-sync-pipeline.git
cd fit-file-sync-pipeline

# 2. Create your configuration
cp config/config.example.yaml config/config.yaml

# 3. Edit config.yaml with your settings
nano config/config.yaml

# 4. Test with a single sync cycle
docker compose run --rm sync --run-once

# 5. Start the service (runs continuously)
docker compose up -d
```

## Usage

### Running the Service
```bash
# Start in background (restarts automatically)
docker compose up -d

# View logs
docker compose logs -f

# Stop the service
docker compose down
```

### Manual Operations
```bash
# Run a single sync cycle
docker compose run --rm sync --run-once

# Dry run (no uploads)
docker compose run --rm sync --run-once --dry-run

# Use a custom config path
docker compose run --rm sync --config /app/config/config.yaml --run-once
```

## Configuration

Edit `config/config.yaml`:
```yaml
intervals:
  api_key: "your_intervals_api_key"

sync:
  interval_minutes: 60       # How often to sync
  lookback_days: 7           # How far back to check
  delay_between_files_ms: 100
  dry_run: false

fit_file_faker:
  garmin_username: "your@email.com"
  garmin_password: "your_password"
  device:
    manufacturer: "garmin"
    product: "edge1030"
    serial_number: "3982691993"
```

Secrets can also be provided via environment variables (`INTERVALS_API_KEY`, `GARMIN_USERNAME`, `GARMIN_PASSWORD`) which override the config file values.

## Folder Structure
```
fit-file-sync-pipeline/
├── docker-compose.yml         # Container orchestration
├── Dockerfile                 # Container image definition
├── requirements.txt           # Python dependencies
├── config/
│   ├── config.example.yaml    # Configuration template
│   └── config.yaml            # Your config (not in git)
├── src/
│   ├── main.py                # Entry point with scheduler loop
│   ├── config.py              # Configuration loading
│   ├── download.py            # intervals.icu API integration
│   ├── process.py             # Fit-File-Faker processing
│   └── logger.py              # Logging setup
├── data/
│   ├── downloaded/            # Raw FIT files from intervals.icu
│   ├── processed/             # Successfully uploaded files
│   └── errors/                # Files that failed processing
├── logs/                      # Daily log files
└── state/                     # Garth tokens and runtime state
```

## Docker Volumes

| Mount | Purpose |
|-------|---------|
| `./config:/app/config:ro` | Configuration file (read-only) |
| `./data:/app/data` | FIT files (downloaded, processed, errors) |
| `./logs:/app/logs` | Daily log files |
| `./state:/app/state` | Garmin auth tokens (persisted across restarts) |

## Supported Devices

Any device that produces FIT files and syncs to intervals.icu:
- ✅ Coros (Pace, Apex, Vertix, Dura, etc.)
- ✅ Hammerhead (Karoo)
- ✅ Wahoo (ELEMNT, RIVAL)
- ✅ Polar (Vantage, Grit, Pacer)
- ✅ Suunto
- ✅ Any other FIT-compatible device

## Troubleshooting

### View Logs
```bash
# Live container logs
docker compose logs -f

# Today's log file
cat logs/sync-$(date +%Y-%m-%d).log
```

### Common Issues

**Authentication errors:**
- Verify Garmin credentials in `config/config.yaml`
- Delete `state/` directory to force re-authentication
- Check that your Garmin account isn't locked

**No activities downloaded:**
- Verify your intervals.icu API key
- Ensure activities have original FIT files (check intervals.icu for "Download original" option)
- Increase `lookback_days` if activities are delayed

**Rate limiting:**
- The pipeline automatically pauses and retries next cycle
- Avoid running multiple instances simultaneously

**Container won't start:**
- Check `docker compose logs` for startup validation errors
- Ensure `config/config.yaml` exists and is valid YAML

### Files in `data/errors/`
```bash
# Move error files back for retry
mv data/errors/*.fit data/downloaded/

# Run a single cycle to reprocess
docker compose run --rm sync --run-once
```

## Limitations

- **intervals.icu required** - Must have activities in intervals.icu
- **Garmin Connect account** - Required for uploads
- **Original FIT files** - Only activities with original files can be processed
- **⚠️ Coros Dura gear assignment** - Activities upload successfully but show no gear in Garmin Connect due to a non-standard FIT file format. Training metrics are unaffected.
- **⚠️ Duplicate activities on connected services** - Services connected to both your device AND Garmin Connect may receive duplicate activities. Strava and Ride with GPS handle this automatically; TrainingPeaks requires you to disable Garmin auto-sync.

## Related Projects

- **[Fit-File-Faker](https://github.com/jat255/Fit-File-Faker)** - The core tool that makes this possible
- **[intervals.icu](https://intervals.icu)** - Excellent training analysis platform
- **[GarminDB](https://github.com/tcgoetz/GarminDB)** - Alternative for Garmin data analysis

## License

MIT License - see [LICENSE](LICENSE)

## Acknowledgments

- **[Original project](https://github.com/nothingshocking/fit-file-sync-pipeline)** by [@nothingshocking](https://github.com/nothingshocking) - The original Windows/PowerShell pipeline this fork is based on
- **[Fit-File-Faker](https://github.com/jat255/Fit-File-Faker)** by [@jat255](https://github.com/jat255) - The essential tool that enables device-agnostic uploads to Garmin Connect
- **[intervals.icu](https://intervals.icu)** by [@david](https://intervals.icu) - Excellent API and training platform
- The endurance sports open-source community

## Disclaimer

This tool is for personal use. Ensure you comply with the terms of service for intervals.icu and Garmin Connect. This project is not affiliated with Garmin, intervals.icu, or Fit-File-Faker.

---

**Questions?** Open an [issue](https://github.com/jowlo/fit-file-sync-pipeline/issues)
