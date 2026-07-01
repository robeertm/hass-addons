# Changelog

## 1.0.2 — 2026-07-01
- Optional idempotent HA `configuration.yaml` patcher (`config_patcher.enabled: true`).
  Sets `recorder.commit_interval` to a target value (default 60) to reduce SQLite
  WAL write amplification on SD cards. Creates a timestamped backup before writing.
  Safe to re-run — no-ops when target value is already present. Requires
  `homeassistant_config:rw` map (added).
- HA restart required after first apply to activate new recorder config.

## 1.0.1 — 2026-06-30
- Drop `raspberrypi-utils` from Dockerfile (not available on Alpine aarch64). Pi-specific health (throttling, voltage) reads `/sys` directly with graceful fallback when vcgencmd is absent.

## 1.0.0 — 2026-06-30
- Initial release
- 38 sensors + 6 binary_sensors
- CPU/Memory/Disk/SD-IO/Network/Voltage/Throttling/Health-Score
- Daily SD-write tracking + endurance estimation
- vcgencmd integration (Pi-specific)
- Falls back gracefully on non-Pi hardware
