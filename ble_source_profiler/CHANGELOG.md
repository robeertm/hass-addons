# Changelog

## 1.0.0 — 2026-07-01
- Initial release.
- HA WebSocket `bluetooth/subscribe_advertisements` subscription for a
  configurable sweep window every N seconds.
- Per configured source (BLE-Proxy / BlueZ dongle MAC): adverts count,
  unique BLE addresses seen, RSSI min/avg/max.
- Aggregate `snapshot` sensor whose attributes carry the full
  named-devices list with best-source picker — feeds Lovelace markdown
  comparison tables.
- MQTT Auto-Discovery, availability topics per source, retained state.
- Auto-uses Supervisor token for HA WS auth when running as HAOS add-on.
