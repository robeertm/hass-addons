#!/usr/bin/with-contenv bashio
set -e

CFG=/data/options.json

bashio::log.info "RPi Health Monitor starting"

# Optional one-shot: patch HA configuration.yaml recorder.commit_interval
if bashio::config.true 'config_patcher.enabled'; then
  bashio::log.info "config_patcher enabled — running one-shot"
  python3 /usr/local/bin/config_patcher.py || true
fi

# Auto-discover MQTT credentials from HA Supervisor if blank
if bashio::config.is_empty 'mqtt.username' && bashio::services.available 'mqtt'; then
  bashio::log.info "Using HA-supplied MQTT credentials"
  export RPI_MQTT_BROKER=$(bashio::services mqtt "host")
  export RPI_MQTT_PORT=$(bashio::services mqtt "port")
  export RPI_MQTT_USER=$(bashio::services mqtt "username")
  export RPI_MQTT_PASS=$(bashio::services mqtt "password")
fi

exec python3 /usr/local/bin/rpi_monitor.py "$CFG"
