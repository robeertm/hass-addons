# Changelog

## 16.41.4 — 2026-06-17

- Initial add-on release. Wraps upstream [shelly-energy-analyzer v16.41.4](https://github.com/robeertm/shelly-energy-analyzer/releases/tag/v16.41.4).
- Supports `aarch64`, `amd64`, `armv7`, `armhf`.
- MQTT auto-discovery integrates with the HA Mosquitto add-on (auto-pulls credentials from HA service registry when add-on options leave `username`/`password` empty).
- Persistent state under `/data`.
