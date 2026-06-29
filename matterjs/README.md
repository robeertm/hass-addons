# matter.js Server (BLE-native)

Drop-in alternative to Home Assistant's `core_matter_server` add-on when
its BLE-Proxy fails to forward Matter advertisements (`FFF6` service-data)
from HA's Bluetooth integration to matter.js's `ProxyBleClient`.

Uses the upstream `ghcr.io/matter-js/matterjs-server:1.1.1` image with:
- `host_network: true`  (matter operational mDNS discovery)
- `host_dbus: true`     (BlueZ system bus access)
- `apparmor: false`     (BlueZ DBus profile not blocked)
- direct `--bluetooth-adapter <hciN>` flag (chip-native BLE, not proxy)

## Configuration

```yaml
log_level: info               # debug for BLE-pair troubleshooting
bluetooth_adapter: 0          # hci0 default; -1 to disable BLE
fabric_id: 2                  # Matter fabric ID (1 = Robert, 2 = Mike)
vendor_id: 65521              # 0xfff1, default for matter.js
primary_interface: ""         # leave empty to auto-detect, else "eth0"/"end0"
```

## Setup

1. **Stop `Matter Server` (`core_matter_server`)** in HAOS Add-on Store first
   to free port 5580 and avoid fabric conflicts.
2. **Install this add-on** from the `robeertm/hass-addons` repository.
3. **Start it.** Logs will report BlueZ DBus socket status and matter-server
   listening on port 5580.
4. **Re-configure HA's Matter integration** to point at this server:
   - Settings → Devices & Services → Matter → Configure
   - Or via WebSocket: update `config_entries.data.url` to
     `ws://core-matterjs:5580/ws` (Docker hostname of this add-on)

## Pair flow

After start, matter.js will accept `commission_with_code` calls. BLE
discovery uses the HCI adapter directly via BlueZ DBus — no advertisement
hand-off from HA's Bluetooth integration required.

## Storage

Fabric / nodes persisted under `/data/` inside the add-on container.
HAOS exposes this as `/addon_configs/<repo-id>_matterjs/` on the host.

## Conflict with HA's Bluetooth integration

BlueZ supports multiple DBus clients on the same HCI adapter. matter.js's
chip-native scan and HA's Bluetooth-Integration passive scans can run in
parallel without arbitration — neither holds exclusive control over the
adapter.
