# Shelly Energy Analyzer — Home Assistant Add-on

Self-hosted energy monitoring for Shelly EM / 3EM devices. Includes 23 dashboards, dynamic spot tariffs, real ENTSO-E CO₂ intensity, PV/solar, NILM appliance detection, MQTT/Home Assistant auto-discovery.

Upstream project: <https://github.com/robeertm/shelly-energy-analyzer>

## Installation

1. **Settings → Add-ons → Add-on Store → ⋮ → Repositories** and add `https://github.com/robeertm/hass-addons` if not already present.
2. Refresh the store, install **Shelly Energy Analyzer**.
3. Open **Configuration**, enter your Shelly devices and (optionally) MQTT settings.
4. **Start** the add-on. Watch logs until you see `Starting analyzer on 0.0.0.0:8765`.
5. Open the Web UI at `http://<HOMEASSISTANT_IP>:8765/`.

## Configuration

```yaml
log_level: info
devices:
  - key: shelly1
    name: Haus           # Friendly name shown in dashboard
    host: 192.168.1.100  # Shelly EM/3EM IP (or hostname)
    em_id: 0             # EM channel index — 0 for single-EM, 0..2 for 3EM
mqtt:
  enabled: true          # Set true to publish to HA via MQTT
  broker: core-mosquitto # Use HA Mosquitto add-on hostname, or your broker IP
  port: 1883
  username: ""           # Leave empty to use HA-issued credentials
  password: ""
  topic_prefix: shelly_analyzer
  ha_discovery: true
  ha_discovery_prefix: homeassistant
  publish_interval_seconds: 10
ui:
  language: de           # de | en
  live_poll_seconds: 1
  live_window_minutes: 10
  live_retention_minutes: 120
electricity_price_eur_per_kwh: 0.30
```

### MQTT integration

If `mqtt.enabled: true` and you leave `mqtt.username`/`mqtt.password` empty, the add-on uses the credentials from the **MQTT** service in Home Assistant (typically managed by the Mosquitto add-on). HA auto-discovery is published under the prefix `homeassistant/` by default — your Shelly readings will appear as MQTT sensors in Home Assistant automatically.

### Persistence

Configuration, CSV history, NILM state etc. are stored under the add-on's `/data` directory, which Home Assistant backs up automatically.

## Web UI

Port `8765/tcp` is exposed. The dashboard runs **HTTP** inside the add-on (SSL is best handled by an HA reverse proxy or the Nginx add-on).

## Updating

Push a new version of the analyzer? Bump `version:` in `config.yaml` and `ANALYZER_VERSION:` in `build.yaml`, then HA shows an update in the add-on store.
