#!/usr/bin/env sh
set -e

CONFIG_PATH=/data/options.json

PROFILE=$(jq -r '.profile // "mike"' "$CONFIG_PATH" 2>/dev/null || echo "mike")
REFRESH=$(jq -r '.refresh_seconds // 15' "$CONFIG_PATH" 2>/dev/null || echo 15)
ROTATE=$(jq -r '.page_rotate_seconds // 22' "$CONFIG_PATH" 2>/dev/null || echo 22)
USER_TOKEN=$(jq -r '.ha_token // ""' "$CONFIG_PATH" 2>/dev/null || echo "")
USER_URL=$(jq -r '.ha_base_url // ""' "$CONFIG_PATH" 2>/dev/null || echo "")

export TV_PROFILE="$PROFILE"
export REFRESH_INTERVAL_SEC="$REFRESH"
export PAGE_ROTATE_SEC="$ROTATE"

# Prefer user-provided Long-Lived Token + base URL (works around Supervisor token not auth'ing for HA Core API)
if [ -n "$USER_TOKEN" ]; then
  export HA_TOKEN="$USER_TOKEN"
  export HA_BASE_URL="${USER_URL:-http://homeassistant.local.hass.io:8123}"
else
  export HA_BASE_URL="${USER_URL:-http://supervisor/core}"
  export HA_TOKEN="${SUPERVISOR_TOKEN:-}"
fi

echo "[run] tv_dashboard v1.0.2 profile=$PROFILE refresh=${REFRESH}s rotate=${ROTATE}s"
echo "[run] HA_BASE_URL=$HA_BASE_URL TOKEN_LEN=${#HA_TOKEN}"

cd /app
exec gunicorn -w 2 --threads 4 -b 0.0.0.0:8765 app:app
