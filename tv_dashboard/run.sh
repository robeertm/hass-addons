#!/usr/bin/env sh
set -e

CONFIG_PATH=/data/options.json

PROFILE=$(jq -r '.profile // "mike"' "$CONFIG_PATH" 2>/dev/null || echo "mike")
REFRESH=$(jq -r '.refresh_seconds // 15' "$CONFIG_PATH" 2>/dev/null || echo 15)
ROTATE=$(jq -r '.page_rotate_seconds // 22' "$CONFIG_PATH" 2>/dev/null || echo 22)

export TV_PROFILE="$PROFILE"
export REFRESH_INTERVAL_SEC="$REFRESH"
export PAGE_ROTATE_SEC="$ROTATE"

# Supervisor injects SUPERVISOR_TOKEN; use Supervisor proxy for HA API
export HA_BASE_URL="http://supervisor/core"
export HA_TOKEN="${SUPERVISOR_TOKEN:-}"

echo "[run] profile=$PROFILE refresh=${REFRESH}s rotate=${ROTATE}s"
echo "[run] HA_BASE_URL=$HA_BASE_URL"

cd /app
exec gunicorn -w 2 --threads 4 -b 0.0.0.0:8765 app:app
