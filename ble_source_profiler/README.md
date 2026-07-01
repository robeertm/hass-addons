# BLE Source Profiler

Custom Home Assistant add-on that quantifies the reception quality of each of
your BLE receivers (Raspberry Pi USB dongle, ESPHome BLE-Proxies, etc.) so
you can decide which one wins for which device and where the coverage gap is.

## What it does

- Subscribes to HA's `bluetooth/subscribe_advertisements` WebSocket stream for
  `sweep_seconds` at a time (default 50s), every `poll_interval_seconds`
  (default 60s).
- Aggregates per source MAC:
  - Total advert events observed
  - Count of unique BLE addresses seen
  - Best / worst / average RSSI (dBm)
- Computes per named BLE device (Eve*, Govee* etc.):
  - Which source picked up its strongest signal
  - RSSI per source for direct comparison

## Sensors

For each entry in `sources[]` (identified by MAC):

- `sensor.<device_prefix>_<key>_adverts`
- `sensor.<device_prefix>_<key>_unique_devices`
- `sensor.<device_prefix>_<key>_rssi_avg`
- `sensor.<device_prefix>_<key>_rssi_best`
- `sensor.<device_prefix>_<key>_rssi_worst`

Plus one aggregate sensor:

- `sensor.<device_prefix>_snapshot` — state is the last-update timestamp,
  attributes carry `sources`, `named_devices`, `n_sources`, etc.

## Config

```yaml
ha:
  url: "ws://homeassistant.local.hass.io:8123/api/websocket"
  token: ""                    # leave empty to use Supervisor token
sample:
  sweep_seconds: 50
  poll_interval_seconds: 60
sources:
  - mac: "14:08:08:53:8C:CA"
    name: "Atom Wohnzimmer"
    key: "atom_wohnzimmer"
  - mac: "2C:CF:67:B9:5C:F3"
    name: "Pi BlueZ Dongle"
    key: "pi_bluez"
mqtt:
  broker: core-mosquitto
  port: 1883
  discovery_prefix: homeassistant
  device_prefix: mike_ble_source
```

Origin: HAOS-add-on port of Robert's Pi-cron `dump_ble_sources.py`.
