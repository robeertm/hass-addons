#!/usr/bin/env sh
set -e

CONFIG_PATH=/data/options.json
get(){ jq -r ".$1 // \"$2\"" "$CONFIG_PATH" 2>/dev/null || echo "$2"; }

export COLLECTOR_HOST=0.0.0.0
export COLLECTOR_PORT=2055
export HTTP_PORT=3002
export GEOIP_DB=/app/geoip/GeoLite2-Country.mmdb
export HA_URL="$(get ha_base_url http://127.0.0.1:8123)"
export HA_TOKEN="$(get ha_token '')"
export TOP_N="$(get top_n 30)"
export HOSTNAME_REFRESH_SEC="$(get hostname_refresh_sec 120)"
export HISTORY_BUCKETS="$(get history_buckets 144)"
export HISTORY_BUCKET_SEC=300
# these options hold JSON text; `get` returns the raw string for json.loads()
export VLAN_NAMES_JSON="$(get vlan_names_json '{}')"
export SUBNET_VLAN_JSON="$(get subnet_vlan_json '{}')"
export LOCAL_V6_GUA="$(get local_v6_gua '')"
# MQTT: enabled when mqtt_host is set (empty → collector keeps MQTT off, HTTP-only).
export MQTT_HOST="$(get mqtt_host '')"
export MQTT_PORT="$(get mqtt_port 1883)"
export MQTT_USER="$(get mqtt_user '')"
export MQTT_PASS="$(get mqtt_pass '')"
export MQTT_DISCOVERY_PREFIX="$(get mqtt_discovery_prefix homeassistant)"
export MQTT_PUBLISH_SEC="$(get mqtt_publish_sec 60)"
export DEVICE_PURGE_DAYS="$(get device_purge_days 7)"

echo "[run] flow_collector · UDP $COLLECTOR_PORT → HTTP $HTTP_PORT · HA=$HA_URL token_len=${#HA_TOKEN} · top_n=$TOP_N · mqtt=${MQTT_HOST:-off}"
echo "[run] VLAN_NAMES=$VLAN_NAMES_JSON SUBNET_VLAN=$SUBNET_VLAN_JSON GUA=$LOCAL_V6_GUA"

cd /app
exec python3 collector.py
