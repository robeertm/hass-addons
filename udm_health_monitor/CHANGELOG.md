# Changelog

## 1.0.0 — 2026-06-28

Initial release.

- Polls UDM `/proxy/network/api/s/default/stat/device` every N seconds
- Publishes 20 sensors via MQTT Auto-Discovery
- CPU/Mem/Temp/Load/Uptime/Power/Clients
- Configurable temp-alert thresholds → `temp_status` derived sensor
- Auto-detects HA-managed MQTT credentials via Supervisor `services.mqtt`
- Multi-instance friendly via `device.id_suffix`
