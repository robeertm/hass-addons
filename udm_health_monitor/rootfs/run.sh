#!/usr/bin/with-contenv bashio
set -e

CFG=/data/options.json

bashio::log.info "UDM Health Monitor starting"

# Auto-discover MQTT credentials from HA Supervisor if blank
if bashio::config.is_empty 'mqtt.username' && bashio::services.available 'mqtt'; then
  bashio::log.info "Using HA-supplied MQTT credentials"
  MQTT_HOST=$(bashio::services mqtt "host")
  MQTT_PORT=$(bashio::services mqtt "port")
  MQTT_USER=$(bashio::services mqtt "username")
  MQTT_PASS=$(bashio::services mqtt "password")
  export UDM_MQTT_BROKER="${MQTT_HOST}"
  export UDM_MQTT_PORT="${MQTT_PORT}"
  export UDM_MQTT_USER="${MQTT_USER}"
  export UDM_MQTT_PASS="${MQTT_PASS}"
fi

exec python3 /usr/local/bin/udm_monitor.py "$CFG"
