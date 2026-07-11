#!/usr/bin/env sh
set -e

CONFIG_PATH=/data/options.json
get(){ jq -r ".$1 // \"$2\"" "$CONFIG_PATH" 2>/dev/null || echo "$2"; }

# single-house Mike profile — everything local (host_network:true → 127.0.0.1)
export COCKPIT_PROFILE=mike
export HA_URL="$(get ha_base_url http://127.0.0.1:8123)"
export HA_TOKEN="$(get ha_token '')"
export MQTT_HOST="$(get mqtt_host 127.0.0.1)"
export MQTT_PORT="$(get mqtt_port 1883)"
export MQTT_USER="$(get mqtt_user ha)"
export MQTT_PASS="$(get mqtt_pass '')"
export FLOWCOL_URL="$(get flowcol_url http://127.0.0.1:3002)"
export MIKE_FLOWCOL_URL="$FLOWCOL_URL"
export REFRESH_SEC="$(get refresh_seconds 4)"
export PORT=8099
export MQTT_CLIENT_ID="haus-cockpit-mike-addon"

echo "[run] haus_cockpit (Klipphausen) · profile=mike · HA=$HA_URL · MQTT=$MQTT_HOST:$MQTT_PORT · flow=$FLOWCOL_URL · token_len=${#HA_TOKEN}"

cd /app
exec gunicorn -w 1 --threads 8 -b 0.0.0.0:8099 app:app
