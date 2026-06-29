## 1.1.6 - 2026-06-29

- **HOTFIX**: removed `--ble-hci-id` CLI arg — matter-server v1.1.1 errors
  out with "unknown option '--ble-hci-id'" on startup. The `NOBLE_HCI_DEVICE_ID`
  env var (added in 1.1.5) is sufficient on its own to direct noble to the
  right adapter. No matter-server CLI flag exposes adapter selection.

## 1.1.5 - 2026-06-29

- **FIX**: noble BLE backend was defaulting to hci0 regardless of the
  `bluetooth_adapter` option. Now sets `NOBLE_HCI_DEVICE_ID` env var so the
  noble library actually targets the configured adapter (essential when
  hci0 is the weak built-in chip and hci1 is the working USB dongle).
- Switched CLI arg from `--bluetooth-adapter` (silently ignored by
  matter-server v1.1.1) to `--ble-hci-id`. The previous arg passed without
  effect, but the noble env var is what actually controls which adapter
  noble scans on.

## 1.1.1 - 2026-06-29

Initial release. Drop-in alternative to `core_matter_server` for cases
where the HA-BleProxy → matter.js advertisement forwarding silently fails.

- Based on `ghcr.io/matter-js/matterjs-server:1.1.1`
- Chip-native BLE via `--bluetooth-adapter`
- `host_dbus: true`, `apparmor: false` for unblocked BlueZ DBus access
- bashio-based options wrapper, configurable via HAOS add-on UI
