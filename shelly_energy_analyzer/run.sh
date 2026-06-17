#!/usr/bin/with-contenv bashio
set -e

CFG=/data/config.json
DATA_DIR=/data

bashio::log.info "Shelly Energy Analyzer add-on starting (v${ANALYZER_VERSION})"

# --- Resolve MQTT defaults from HA services if not overridden ---
MQTT_ENABLED="$(bashio::config 'mqtt.enabled')"
MQTT_BROKER="$(bashio::config 'mqtt.broker')"
MQTT_PORT="$(bashio::config 'mqtt.port')"
MQTT_USER="$(bashio::config 'mqtt.username')"
MQTT_PASS="$(bashio::config 'mqtt.password')"

if [ "${MQTT_ENABLED}" = "true" ] && bashio::services.available "mqtt"; then
  if [ -z "${MQTT_USER}" ]; then
    MQTT_USER="$(bashio::services 'mqtt' 'username')"
    bashio::log.info "Using MQTT username from HA services: ${MQTT_USER}"
  fi
  if [ -z "${MQTT_PASS}" ]; then
    MQTT_PASS="$(bashio::services 'mqtt' 'password')"
    bashio::log.info "Using MQTT password from HA services"
  fi
fi

# --- Build config.json from add-on options ---
bashio::log.info "Rendering ${CFG} from add-on options..."

DEVICES_JSON="$(bashio::config 'devices')"
LANG_VAL="$(bashio::config 'ui.language')"
POLL_VAL="$(bashio::config 'ui.live_poll_seconds')"
WIN_VAL="$(bashio::config 'ui.live_window_minutes')"
RET_VAL="$(bashio::config 'ui.live_retention_minutes')"
PRICE_VAL="$(bashio::config 'electricity_price_eur_per_kwh')"
TOPIC_PREFIX="$(bashio::config 'mqtt.topic_prefix')"
HA_DISC="$(bashio::config 'mqtt.ha_discovery')"
HA_DISC_PREFIX="$(bashio::config 'mqtt.ha_discovery_prefix')"
PUB_INT="$(bashio::config 'mqtt.publish_interval_seconds')"

jq -n \
  --arg version "${ANALYZER_VERSION}" \
  --argjson devices "${DEVICES_JSON}" \
  --arg lang "${LANG_VAL}" \
  --argjson poll "${POLL_VAL}" \
  --argjson win "${WIN_VAL}" \
  --argjson ret "${RET_VAL}" \
  --argjson price "${PRICE_VAL}" \
  --argjson mqtt_enabled "${MQTT_ENABLED}" \
  --arg mqtt_broker "${MQTT_BROKER}" \
  --argjson mqtt_port "${MQTT_PORT}" \
  --arg mqtt_user "${MQTT_USER}" \
  --arg mqtt_pass "${MQTT_PASS}" \
  --arg mqtt_topic "${TOPIC_PREFIX}" \
  --argjson mqtt_disc "${HA_DISC}" \
  --arg mqtt_disc_prefix "${HA_DISC_PREFIX}" \
  --argjson mqtt_pub_int "${PUB_INT}" \
  '{
    version: $version,
    devices: $devices,
    download: {
      chunk_seconds: 43200,
      overlap_seconds: 60,
      timeout_seconds: 8,
      retries: 3,
      backoff_base_seconds: 1.5
    },
    csv_pack: {
      threshold_count: 120,
      max_megabytes: 20,
      remove_merged: false
    },
    ui: {
      live_poll_seconds: $poll,
      plot_redraw_seconds: 0.5,
      live_window_minutes: $win,
      live_retention_minutes: $ret,
      language: $lang,
      plot_theme_mode: "auto",
      live_web_enabled: true,
      live_web_port: 8765,
      live_web_ssl_mode: "off",
      live_web_refresh_seconds: 1,
      autosync_enabled: true,
      autosync_interval_hours: 12,
      autosync_mode: "incremental"
    },
    pricing: {
      electricity_price_eur_per_kwh: $price,
      price_includes_vat: true,
      vat_enabled: true,
      vat_rate_percent: 19.0
    },
    mqtt: {
      enabled: $mqtt_enabled,
      broker: $mqtt_broker,
      port: $mqtt_port,
      username: $mqtt_user,
      password: $mqtt_pass,
      topic_prefix: $mqtt_topic,
      ha_discovery: $mqtt_disc,
      ha_discovery_prefix: $mqtt_disc_prefix,
      publish_interval_seconds: $mqtt_pub_int,
      use_tls: false
    }
  }' > "${CFG}"

bashio::log.info "Effective config (secrets redacted):"
jq 'del(.mqtt.password) | .mqtt.password = (if (.mqtt.password // "") == "" then "" else "***" end)' "${CFG}"

# --- Run analyzer ---
cd "${DATA_DIR}"
bashio::log.info "Starting analyzer on 0.0.0.0:8765 (HTTP)..."
exec python3 -m shelly_analyzer --config "${CFG}" --no-ssl --host 0.0.0.0 --port 8765
