## 1.0.0 - 2026-06-29

Initial release.

- Polls matter.js Server WebSocket (`a35e7931-matterjs:5580/ws`) every 5 min by default
- Reads ThreadNetworkDiagnostics cluster (`0/53/7` NeighborTable) per commissioned node
- Extracts per-neighbor avg/last RSSI + LQI + frame-error-rate
- Publishes per-node best-RSSI sensors `sensor.thread_rssi_<slug>` with full neighbor list as attributes
- Computes aggregate sensors:
  - `sensor.thread_rssi_best` / `_worst` / `_avg`
  - `sensor.thread_sleepy_rssi_best` / `_worst` / `_avg` (battery-powered only)
  - `sensor.thread_mesh_nodes` (count)
- Uses Supervisor proxy (`http://supervisor/core/api/states/…`) with the add-on's auto-issued `SUPERVISOR_TOKEN` — no HA long-lived token needed
- Sleepy-vs-router classification via RoutingRole attribute (`0/53/1`)
- Configurable node-id → slug overrides via UI options (`name_overrides`)

Mike-Variante von Roberts Pi-cron `dump_mesh.py` — HAOS-kompatibel ohne `docker exec`.
