#!/usr/bin/with-contenv bashio
set -e

bashio::log.info "BLE Source Profiler starting"

# Auto-discover Supervisor URL / token — Supervisor injects SUPERVISOR_TOKEN
# and http://supervisor/core resolves to Core inside the add-on network.
if bashio::config.is_empty 'ha.token' && [ -n "${SUPERVISOR_TOKEN:-}" ]; then
  bashio::log.info "Using SUPERVISOR_TOKEN for HA websocket auth"
  export BLE_HA_TOKEN="${SUPERVISOR_TOKEN}"
else
  export BLE_HA_TOKEN="$(bashio::config 'ha.token')"
fi

# Auto-discover MQTT credentials from Mosquitto add-on if blank
if bashio::config.is_empty 'mqtt.username' && bashio::services.available 'mqtt'; then
  bashio::log.info "Using HA-supplied MQTT credentials"
  export BLE_MQTT_BROKER=$(bashio::services mqtt "host")
  export BLE_MQTT_PORT=$(bashio::services mqtt "port")
  export BLE_MQTT_USER=$(bashio::services mqtt "username")
  export BLE_MQTT_PASS=$(bashio::services mqtt "password")
fi

exec python3 /usr/local/bin/ble_source_profiler.py /data/options.json
