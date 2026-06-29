## 1.1.1 - 2026-06-29

Initial release. Drop-in alternative to `core_matter_server` for cases
where the HA-BleProxy → matter.js advertisement forwarding silently fails.

- Based on `ghcr.io/matter-js/matterjs-server:1.1.1`
- Chip-native BLE via `--bluetooth-adapter`
- `host_dbus: true`, `apparmor: false` for unblocked BlueZ DBus access
- bashio-based options wrapper, configurable via HAOS add-on UI
