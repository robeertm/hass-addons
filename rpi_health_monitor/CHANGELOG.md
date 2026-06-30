# Changelog

## 1.0.1 — 2026-06-30
- Drop `raspberrypi-utils` from Dockerfile (not available on Alpine aarch64). Pi-specific health (throttling, voltage) reads `/sys` directly with graceful fallback when vcgencmd is absent.

## 1.0.0 — 2026-06-30
- Initial release
- 38 sensors + 6 binary_sensors
- CPU/Memory/Disk/SD-IO/Network/Voltage/Throttling/Health-Score
- Daily SD-write tracking + endurance estimation
- vcgencmd integration (Pi-specific)
- Falls back gracefully on non-Pi hardware
