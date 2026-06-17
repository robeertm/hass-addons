#!/usr/bin/with-contenv bashio
set -e

CFG=/data/config.json
OPTS=/data/options.json
DATA_DIR=/data

bashio::log.info "Shelly Energy Analyzer add-on starting (v${ANALYZER_VERSION})"
bashio::log.info "Raw options snapshot (passwords redacted):"
jq 'walk(if type == "object" and (has("password")) then .password = (if (.password // "") == "" then "" else "***" end) else . end)' "${OPTS}"

# --- Pull MQTT credentials from HA's MQTT service registry if user left them blank ---
MQTT_USER=""
MQTT_PASS=""
if [ "$(jq -r '.mqtt.enabled // false' "${OPTS}")" = "true" ] && bashio::services.available "mqtt"; then
  if [ "$(jq -r '.mqtt.username // ""' "${OPTS}")" = "" ]; then
    MQTT_USER="$(bashio::services 'mqtt' 'username')"
    bashio::log.info "Pulling MQTT username from HA services: ${MQTT_USER}"
  fi
  if [ "$(jq -r '.mqtt.password // ""' "${OPTS}")" = "" ]; then
    MQTT_PASS="$(bashio::services 'mqtt' 'password')"
    bashio::log.info "Pulling MQTT password from HA services"
  fi
fi

# --- Render config.json directly from /data/options.json via jq ---
bashio::log.info "Rendering ${CFG} from /data/options.json..."

jq \
  --arg version "${ANALYZER_VERSION}" \
  --arg fallback_mqtt_user "${MQTT_USER}" \
  --arg fallback_mqtt_pass "${MQTT_PASS}" \
  '{
    version: $version,
    devices: (.devices // []),
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
      live_poll_seconds: (.ui.live_poll_seconds // 1.0),
      plot_redraw_seconds: 0.5,
      live_window_minutes: (.ui.live_window_minutes // 10),
      live_retention_minutes: (.ui.live_retention_minutes // 120),
      language: (.ui.language // "de"),
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
      electricity_price_eur_per_kwh: (.electricity_price_eur_per_kwh // 0.30),
      price_includes_vat: true,
      vat_enabled: true,
      vat_rate_percent: 19.0
    },
    mqtt: {
      enabled: (.mqtt.enabled // false),
      broker: (.mqtt.broker // "core-mosquitto"),
      port: (.mqtt.port // 1883),
      username: (if (.mqtt.username // "") == "" then $fallback_mqtt_user else .mqtt.username end),
      password: (if (.mqtt.password // "") == "" then $fallback_mqtt_pass else .mqtt.password end),
      topic_prefix: (.mqtt.topic_prefix // "shelly_analyzer"),
      ha_discovery: (.mqtt.ha_discovery // true),
      ha_discovery_prefix: (.mqtt.ha_discovery_prefix // "homeassistant"),
      publish_interval_seconds: (.mqtt.publish_interval_seconds // 10),
      use_tls: false
    }
  }' "${OPTS}" > "${CFG}"

bashio::log.info "Rendered config.json (passwords redacted):"
jq 'walk(if type == "object" and (has("password")) then .password = (if (.password // "") == "" then "" else "***" end) else . end)' "${CFG}"

# --- Run analyzer ---
cd "${DATA_DIR}"
bashio::log.info "Starting analyzer on 0.0.0.0:8765 (HTTP)..."
exec python3 -m shelly_analyzer --config "${CFG}" --no-ssl --host 0.0.0.0 --port 8765
