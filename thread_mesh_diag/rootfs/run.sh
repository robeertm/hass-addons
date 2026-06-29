#!/usr/bin/with-contenv bashio
set -e

LOG_LEVEL=$(bashio::config 'log_level')
MJS_HOST=$(bashio::config 'matterjs.host')
MJS_PORT=$(bashio::config 'matterjs.port')
INTERVAL=$(bashio::config 'poll.interval_seconds')
SENSOR_PREFIX=$(bashio::config 'sensor_prefix')

# Convert log level to Python compatible
case "${LOG_LEVEL}" in
  trace|debug) PYLOG=DEBUG ;;
  info|notice) PYLOG=INFO ;;
  warning) PYLOG=WARNING ;;
  error) PYLOG=ERROR ;;
  fatal) PYLOG=CRITICAL ;;
  *) PYLOG=INFO ;;
esac

# Name overrides → serialized as JSON for the Python side
NAME_OVERRIDES_JSON=$(bashio::config 'name_overrides' | jq -c '.')

bashio::log.info "Thread Mesh Diagnostics starting"
bashio::log.info "  matter.js: ws://${MJS_HOST}:${MJS_PORT}/ws"
bashio::log.info "  interval:  ${INTERVAL} s"
bashio::log.info "  prefix:    sensor.${SENSOR_PREFIX}_*"
bashio::log.info "  overrides: ${NAME_OVERRIDES_JSON}"

export MJS_HOST MJS_PORT INTERVAL SENSOR_PREFIX NAME_OVERRIDES_JSON
export PYLOG SUPERVISOR_TOKEN
exec python3 -u /usr/local/bin/thread_mesh_diag.py
