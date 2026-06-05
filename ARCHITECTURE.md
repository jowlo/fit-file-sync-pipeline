# Architecture Documentation

## System Overview

The FIT File Sync Pipeline is an automated data synchronization system that bridges non-Garmin fitness devices with Garmin Connect's ecosystem. It runs as a Docker container on Linux.

### Data Flow

```
┌─────────────────┐
│  Coros Dura     │
│  Hammerhead K2  │
└────────┬────────┘
         │
         │ (native sync)
         ▼
┌─────────────────┐
│ intervals.icu   │ ◄─── Original FIT files stored here
└────────┬────────┘
         │
         │ (API download)
         ▼
┌─────────────────┐
│  This Pipeline  │
│   downloaded/   │
└────────┬────────┘
         │
         │ (Fit-File-Faker processing)
         ▼
┌─────────────────┐
│ Garmin Connect  │ ◄─── Access to Garmin metrics
└─────────────────┘
```

### Component Architecture

```
┌──────────────────────────────────────────────────┐
│            Docker Container                       │
│         (loop with sleep)                        │
└───────────────────┬──────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────┐
│              src/main.py                          │
│        (Orchestration + scheduler)               │
└───────┬─────────────────────┬────────────────────┘
        │                     │
        ▼                     ▼
┌─────────────────┐   ┌─────────────────┐
│ src/download.py │   │ src/process.py  │
└────┬────────────┘   └────┬────────────┘
     │                     │
     ▼                     ▼
┌─────────────────┐   ┌─────────────────┐
│ intervals.icu   │   │ Fit-File-Faker  │
│      API        │   │  (subprocess)   │
└─────────────────┘   └────┬────────────┘
                           │
                           ▼
                    ┌─────────────────┐
                    │ Garmin Connect  │
                    │   (via garth)   │
                    └─────────────────┘
```

---

## Module Architecture

### src/main.py

**Purpose:** Entry point, CLI args, scheduler loop, signal handling.

**Responsibilities:**
- Parse `--run-once`, `--dry-run`, `--config` arguments
- Load and validate configuration
- Generate fit-file-faker config at startup
- Set HOME/XDG env vars to contain state in `/app/state`
- Run sync cycles in a loop with interruptible sleep
- Handle SIGTERM/SIGINT for graceful shutdown

### src/config.py

**Purpose:** Configuration loading and validation.

**Responsibilities:**
- Load YAML config from mounted file
- Override secrets from environment variables
- Validate required fields
- Provide typed dataclass config objects

### src/download.py

**Purpose:** Download FIT files from intervals.icu API.

**Logic Flow:**
1. Build Basic Auth header from API key
2. Calculate date range (default: last N days to now)
3. Query activities API (omit `newest` to avoid midnight truncation)
4. Filter to activities with `file_type` field
5. Skip already downloaded or processed files
6. Download each file, validate non-empty
7. Configurable delay between requests

### src/process.py

**Purpose:** Process FIT files with fit-file-faker and upload to Garmin Connect.

**Logic Flow:**
1. Scan `downloaded/` for `*.fit` files (exclude `*_modified.fit`)
2. For each file, call `fit-file-faker <file> --upload` via subprocess
3. Analyze stdout/stderr for result:
   - Rate limit → stop processing, leave in downloaded/ for retry
   - Duplicate → move to processed/ (expected behavior)
   - Success → move to processed/
   - Error → move to errors/
4. Clean up temporary `*_modified.fit` files

**Detection Patterns:**
```python
# Rate limit (check first)
r"429|rate limit|All login strategies exhausted"

# Duplicate
r"activity already exists|HTTP conflict|Received HTTP conflict|API Error 409|Duplicate Activity"

# Success
r"Uploading.*using garth|Uploading.*to Garmin Connect|Successfully uploaded"

# Genuine error (narrow)
r"Login failed"
```

### src/logger.py

**Purpose:** Logging configuration.

**Output:**
- stdout (for `docker logs`)
- Daily file in `/app/logs/sync-YYYY-MM-DD.log`

---

## External Dependencies

### Fit-File-Faker

**Installation:** Installed in Docker image via pip
**Called via:** `subprocess.run(["fit-file-faker", filepath, "--upload"])`
**Config:** Generated at startup into `/app/state/.fit_file_faker/config.json`
**Auth tokens:** Stored by garth in `$HOME` (set to `/app/state`)

### intervals.icu API

**Base URL:** `https://intervals.icu/api/v1`
**Authentication:** Basic Auth with `API_KEY:{key}`

**Key Endpoints:**
1. `GET /athlete/0/activities?oldest={date}` - List activities
2. `GET /activity/{id}/file` - Download FIT file

### Garmin Connect

**API:** Not directly used (via Fit-File-Faker/garth)
**Behavior:** Returns HTTP 409 for duplicate activities

---

## Docker Architecture

### Volumes

| Mount | Purpose | Mode |
|-------|---------|------|
| `/app/config` | User config YAML | read-only |
| `/app/data` | FIT files (downloaded/processed/errors) | read-write |
| `/app/logs` | Daily log files | read-write |
| `/app/state` | garth tokens, fit-file-faker config | read-write |

### Container Lifecycle

1. **Startup:** Validate config → validate environment → generate fff config → set HOME
2. **Running:** Loop (sync cycle → sleep with interruptible wait)
3. **Shutdown:** SIGTERM → event set → current sleep interrupted → clean exit

### Security

- Container runs as non-root `appuser`
- Config mounted read-only
- Secrets can come from env vars instead of config file
- No secrets baked into image layers

---

## File Naming Conventions

| Type | Format | Example |
|------|--------|---------|
| Downloaded | `YYYY-MM-DD-iACTIVITYID.fit` | `2026-01-13-i117880666.fit` |
| Processed | `YYYY-MM-DD-iACTIVITYID.uploaded.fit` | `2026-01-13-i117880666.uploaded.fit` |
| Modified (temp) | `YYYY-MM-DD-iACTIVITYID_modified.fit` | Auto-cleaned |
| Logs | `sync-YYYY-MM-DD.log` | `sync-2026-06-05.log` |

---

## Error Recovery

### Automatic
- Network failures: Individual file failures don't stop batch
- Duplicates: Detected and handled as success
- Rate limits: Stop processing, retry next cycle
- Temporary files: Cleaned up automatically
- Container restart: `restart: unless-stopped` in compose

### Manual
- Files in `errors/`: Move back to `downloaded/`, run `--run-once`
- Auth failures: Delete `state/` directory, restart container
- Stuck downloads: Delete from `downloaded/`, will re-download

---

*Document Version: 2.0*
*Last Updated: June 2026*
