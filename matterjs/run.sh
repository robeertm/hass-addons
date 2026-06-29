#!/usr/bin/with-contenv bashio
set -e

OPTS=/data/options.json

LOG_LEVEL=$(jq -r '.log_level // "info"' "${OPTS}")
BT_ADAPTER=$(jq -r '.bluetooth_adapter // 0' "${OPTS}")
FABRIC_ID=$(jq -r '.fabric_id // 2' "${OPTS}")
VENDOR_ID=$(jq -r '.vendor_id // 65521' "${OPTS}")
PRIMARY_IF=$(jq -r '.primary_interface // ""' "${OPTS}")

bashio::log.info "matter.js Server starting"
bashio::log.info "  log_level: ${LOG_LEVEL}"
bashio::log.info "  bluetooth_adapter: ${BT_ADAPTER}"
bashio::log.info "  fabric_id: ${FABRIC_ID}"
bashio::log.info "  vendor_id: ${VENDOR_ID}"
bashio::log.info "  primary_interface: ${PRIMARY_IF:-<auto>}"

mkdir -p /data

# Probe BlueZ access (don't fail if missing — log clearly)
if [ -S /var/run/dbus/system_bus_socket ]; then
  bashio::log.info "BlueZ DBus socket present at /var/run/dbus/system_bus_socket"
else
  bashio::log.warning "BlueZ DBus socket NOT present at /var/run/dbus/system_bus_socket"
fi

# Build argv
ARGS=( "--storage-path" "/data" \
       "--port" "5580" \
       "--log-level" "${LOG_LEVEL}" \
       "--fabricid" "${FABRIC_ID}" \
       "--vendorid" "${VENDOR_ID}" \
       "--bluetooth-adapter" "${BT_ADAPTER}" )

if [ -n "${PRIMARY_IF}" ]; then
  ARGS+=( "--primary-interface" "${PRIMARY_IF}" )
fi

bashio::log.info "Exec: node --enable-source-maps /app/node_modules/matter-server/dist/esm/MatterServer.js ${ARGS[*]}"
exec node --enable-source-maps /app/node_modules/matter-server/dist/esm/MatterServer.js "${ARGS[@]}"
