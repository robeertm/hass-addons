#!/bin/bash
# matter.js Server add-on entrypoint.
# Base image is ghcr.io/matter-js/matterjs-server (Debian bookworm) — NOT
# the HAOS s6-overlay base, so we don't use bashio/with-contenv. Plain jq
# reads /data/options.json and we exec matter-server directly.
set -e

OPTS=/data/options.json

LOG_LEVEL=$(jq -r '.log_level // "info"' "${OPTS}")
BT_ADAPTER=$(jq -r '.bluetooth_adapter // 0' "${OPTS}")
FABRIC_ID=$(jq -r '.fabric_id // 2' "${OPTS}")
VENDOR_ID=$(jq -r '.vendor_id // 65521' "${OPTS}")
PRIMARY_IF=$(jq -r '.primary_interface // ""' "${OPTS}")

ts() { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "$(ts) [matterjs-addon] $*"; }

log "matter.js Server starting"
log "  log_level: ${LOG_LEVEL}"
log "  bluetooth_adapter: ${BT_ADAPTER}"
log "  fabric_id: ${FABRIC_ID}"
log "  vendor_id: ${VENDOR_ID}"
log "  primary_interface: ${PRIMARY_IF:-<auto>}"

mkdir -p /data

# Probe BlueZ DBus access — chip-native BLE depends on this
if [ -S /var/run/dbus/system_bus_socket ]; then
  log "BlueZ DBus socket present at /var/run/dbus/system_bus_socket"
elif [ -S /run/dbus/system_bus_socket ]; then
  log "BlueZ DBus socket present at /run/dbus/system_bus_socket"
else
  log "WARN: BlueZ DBus socket NOT present — BLE pair will fail"
fi

# noble BLE backend selects the adapter via the NOBLE_HCI_DEVICE_ID env
# var. No matter-server CLI flag controls this. Without this env, noble
# defaults to hci0 which on Mike's HAOS-Pi is the weak built-in BT chip,
# while hci1 = TP-Link UB500 is the one that actually sees Eve devices.
export NOBLE_HCI_DEVICE_ID="${BT_ADAPTER}"
log "noble HCI adapter: hci${BT_ADAPTER} (via NOBLE_HCI_DEVICE_ID env)"

# Best-effort power-up of the BLE adapter. HA's bluetooth integration sets
# Powered=false on adapter release; noble can't resurrect a Powered=false
# adapter. `bluetoothctl list` shows Controller<MAC><alias>, no hciN.
# So we power on EVERY known controller and let noble pick the right one
# via NOBLE_HCI_DEVICE_ID.
if [ "${BT_ADAPTER}" != "-1" ]; then
  log "  --- BlueZ adapter list ---"
  timeout 5 bluetoothctl list 2>&1 | while read -r line; do log "    ${line}"; done
  # Extract every MAC from 'Controller XX:XX:XX:XX:XX:XX ...' lines
  for mac in $(timeout 5 bluetoothctl list 2>/dev/null | awk '/^Controller / {print $2}'); do
    log "  power on ${mac}"
    timeout 5 bluetoothctl <<EOF >/dev/null 2>&1
select ${mac}
power on
EOF
  done
  log "  bluetoothctl power-on done"
fi

ARGS=( "--storage-path" "/data"
       "--port" "5580"
       "--log-level" "${LOG_LEVEL}"
       "--fabricid" "${FABRIC_ID}"
       "--vendorid" "${VENDOR_ID}"
       "--bluetooth-adapter" "${BT_ADAPTER}" )

if [ -n "${PRIMARY_IF}" ]; then
  ARGS+=( "--primary-interface" "${PRIMARY_IF}" )
fi

log "Exec: node --enable-source-maps /app/node_modules/matter-server/dist/esm/MatterServer.js ${ARGS[*]}"
exec node --enable-source-maps /app/node_modules/matter-server/dist/esm/MatterServer.js "${ARGS[@]}"
