# Thread Mesh Diagnostics

HAOS Add-on. Reads per-Matter-node Thread mesh neighbor data (RSSI, LQI) directly from your local matter.js Server's WebSocket and publishes Home Assistant sensors via the Supervisor proxy.

No OTBR shell access, no `docker exec`, no Pi-cron scripts. Pure HAOS-friendly.

## What you get

For each commissioned Matter node:
- `sensor.thread_rssi_<slug>` — best-neighbor RSSI in dBm. Attributes include neighbor count, avg/worst, routing role, fabric, serial.

Aggregates across the whole fabric:
- `sensor.thread_rssi_best` / `_worst` / `_avg`
- `sensor.thread_sleepy_rssi_best` / `_worst` / `_avg` (battery devices only)
- `sensor.thread_mesh_nodes` (count of nodes seen)

## Configuration

```yaml
log_level: info
matterjs:
  host: a35e7931-matterjs      # add-on slug-DNS hostname
  port: 5580
poll:
  interval_seconds: 300        # default 5 min
sensor_prefix: thread_rssi     # → sensor.thread_rssi_<slug>
name_overrides:
  "10": "eve_energy_wohnzimmer"
  "11": "eve_thermo_schlafzimmer"
  "14": "eve_door_schlafzimmer_rechts"
  "15": "eve_door_schlafzimmer_links"
```

`name_overrides` maps matter.js node IDs to slug names used in the sensor entity_id. Without an override the add-on derives a slug from the device's product / vendor.

## Architecture

```
matter.js Server (WS 5580)
   ├── start_listening → node list
   └── read_attribute "0/53/7" per node → NeighborTable struct
            ↓
       extract avg/last RSSI + LQI + RouterRole
            ↓
       POST sensor states via http://supervisor/core/api/states/sensor.…
```

NeighborTable struct fields (Matter spec):
- 0: ExtAddress
- 1: Age (s)
- 2: Rloc16
- 5: LQI
- 6: AverageRssi (int8)
- 7: LastRssi (int8)
- 13: IsChild

## Limitations

- Only sees Matter-commissioned nodes. Apple HomePod TBRs and other non-Matter Thread devices are not in the snapshot.
- Routers' neighbor tables can include router-IDs you don't have Matter visibility into — those show as raw extaddr/rloc16 attributes.
- RSSI is parent-side only — the receiving node's view, not the network-wide path quality.

## Compared to Robert's Pi-cron stack

Roberts `dump_mesh.py` uses `docker exec otbr ot-ctl meshdiag childtable` which gives the **OTBR's view** (full child + sleepy tables across all routers). This add-on uses the **per-node view** via matter.js — complementary, but only covers Matter nodes.

For Apple-HomePod-TBR neighbor RSSI you'd still want OTBR access via REST (`/diagnostics` endpoint) — possible future addition.

## License

Same as repo.
