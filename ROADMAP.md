# Roadmap

## Current Status: v2.0.0

The pipeline has been rewritten in Python and runs as a Docker Compose service on Linux.

---

## Changelog

### v2.0.0 (June 2026)

* **Major:** Complete rewrite from PowerShell to Python
* **Major:** Docker Compose deployment (replaces Windows Task Scheduler)
* **Add:** YAML configuration file
* **Add:** Environment variable overrides for secrets
* **Add:** Graceful shutdown (SIGTERM handling)
* **Add:** Startup validation (config, environment, dependencies)
* **Add:** `--run-once` and `--dry-run` CLI flags
* **Add:** Non-root container execution
* **Add:** Persistent state volume for garth auth tokens
* **Remove:** All PowerShell scripts and Windows-specific tooling
* **Remove:** Windows Task Scheduler documentation

### v1.4.1 (June 2026)

* Enhance: Added diagnostic logging of activity IDs
* Fix: Use `[string]::Join()` for PowerShell compatibility

### v1.4.0 (June 2026)

* Fix: Removed `newest` parameter from default API query
* Fix: Download script checks `processed/` folder before downloading
* Fix: Skip log messages changed to INFO level

### v1.3.0 (May 2026)

* Fix: Corrected false rate limit detection
* Fix: Better duplicate detection patterns

### v1.2.0 (May 2026)

* Fix: Fit-File-Faker v2.1.5 compatibility
* Add: Garmin rate limit detection

### v1.0.0 (February 2026)

* Initial release (PowerShell/Windows)

---

## Future Enhancements

### Short-term
- [ ] Retry logic with exponential backoff
- [ ] Activity type filtering (cycling only, etc.)
- [ ] Email/webhook notifications on errors
- [ ] Resolve Coros Dura gear assignment (pending Fit-File-Faker fix)
- [ ] Log rotation (auto-cleanup old log files)

### Long-term
- [ ] Direct integration with other platforms (Strava, TrainingPeaks)
- [ ] Web dashboard for monitoring
- [ ] Database for activity tracking
- [ ] Health check endpoint

---

## Contributing

Contributions welcome! Open an [issue](https://github.com/nothingshocking/fit-file-sync-pipeline/issues) or submit a PR.

