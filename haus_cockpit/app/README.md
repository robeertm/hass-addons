# haus-cockpit 🛰️

A live, animated **ops control board** for Robert's (and — via the Phase-2b MQTT
bridge — Mike's) home infrastructure. It is a **read-only observer** of the MQTT
health feeds the Pi's services already publish; it never actuates anything.

Phase 2 of the Ops-Cockpit project (Phase 1 = [`haus-resilience`](../haus-resilience)).

Runs in Docker on the Pi (`pironman5`), `network_mode: host`, port **8099** →
`http://100.104.211.12:8099` / `http://pironman5:8099`.

## What it shows

- **Service-Registry** — flow-collector, rpi-health-monitor, udm-monitor,
  shelly-energy-analyzer. Each card computes **up / stale / down** from the feed's
  own timestamp + availability (LWT) topic and shows a live-ticking "vor Xs" age.
  This makes the Phase-1 resilience work *visible*: a feed that goes stale pulses
  amber, a down feed pulses red, and a toast fires on any transition.
- **Raspberry Pi 5** — health-score ring, 8 radial gauges (CPU, temp, RAM, disk,
  NVMe °C/spare, swap, SD-wear), throttle LEDs, load, uptime, net, NVMe TBW.
- **UDM Pro SE** — client count, CPU/RAM/temp gauges, WAN IP, power, uptime.
- **Energie (Shelly)** — live total power, per-device bars (Haus/Wallbox/Boiler/
  Weihnacht), cost today, spot & tariff price, grid CO₂.
- **Netzwerk** — top talkers from flow-collector (name, VLAN, v4/v6 MB, flows).
- **Docker-Stack** — every container's state + health via the read-only socket.
- **Klipphausen (Mike)** — a second house tab, multi-house-ready, showing the
  planned bridge until `mike/#` feeds arrive.

## Architecture

```
 MQTT broker (mosquitto @ 127.0.0.1:1883 on the Pi)
   ├─ flowcol/status · flowcol/heartbeat · flowcol/dev/<mac>/attrs
   ├─ rpi_health/robert_pi/{availability,state}
   ├─ udm_health/radeberg/state{,/availability}
   └─ shelly_analyzer/<dev>/state · shelly_analyzer/netz/state
            │  (subscribe #, read-only user "cockpit")
            ▼
   services/mqtt_ingest.py   in-memory snapshot + broker-rx timestamps
            ▼
   services/registry.py      freshness → up/stale/down, transform per house
            ▼
   app.py (Flask)  /api/state (JSON)  ·  / (cockpit.html)
            ▼
   static/js/cockpit.js  polls every 4 s, animates gauges/bars, ticks ages,
                         keyed reconciler (no flicker), toasts on state flips
```

## Resilience

- **Layer 1** — `connect_async` + `loop_start`, resubscribe in `on_connect`
  (broker restart re-arms all topics), `reconnect_delay_set`.
- **Layer 2** — `restart: unless-stopped` (Docker) → survives crashes & host
  reboot. Proven: `kill -9` the gunicorn master → container auto-restarts, MQTT
  reconnects, full state restored.
- Freshness itself is the point: even if the whole cockpit is fine, a *source*
  feed going stale is surfaced immediately (up → stale → down).

## Run

```bash
cp .env.example .env    # put the cockpit MQTT user's password in MQTT_PASS
docker compose up -d --build
curl -s localhost:8099/healthz          # {"ok":true,...}
python selftest.py                      # offline transform test → ALL PASS
```

## Files

| file | role |
|---|---|
| `app.py` | Flask: `/`, `/api/state`, `/healthz`; starts the ingest thread |
| `services/mqtt_ingest.py` | resilient read-only subscriber + snapshot store |
| `services/registry.py` | freshness + transform → per-house state |
| `services/docker_probe.py` | container list over the unix socket (fails soft) |
| `config.py` | env config, service registry, houses, thresholds |
| `templates/cockpit.html` · `static/css` · `static/js` | the animated UI |
| `selftest.py` | offline transform test (fresh / stale / offline-LWT) |
