# UDM Health Monitor

Polls a UniFi UDM (Pro / Pro SE / Dream Router) over its local API
and publishes hardware sensors to MQTT with Home Assistant Auto-Discovery.

## Why

The UniFi-Network HA integration only exposes a fraction of the UDM's
hardware telemetry (CPU%, Mem%, PoE-Power, Uptime). The local UDM API
returns much more: **CPU/Board/PHY temperatures, load averages,
memory in MB, firmware version, WAN IP, client count.**

This add-on bridges that gap. Multiple instances can run side by side
(`udm.host` + `device.id_suffix`) to monitor several UDMs from one HA.

## Setup

1. Add `https://github.com/robeertm/hass-addons` to your add-on store repos
2. Install **UDM Health Monitor**
3. Configure:

```yaml
udm:
  host: 192.168.1.1          # local UDM IP
  username: claude           # UniFi local-account name (NOT cloud)
  password: "your-pwd-here"
  verify_ssl: false
device:
  name: "UDM Pro SE Radeberg"
  id_suffix: "radeberg"      # used in entity IDs: sensor.udm_radeberg_cpu_pct
poll:
  interval_seconds: 30
mqtt:
  broker: core-mosquitto     # auto-detected from HA Supervisor if blank
  port: 1883
  username: ""               # auto-detected
  password: ""
  discovery_prefix: homeassistant
  state_topic_prefix: udm_health
alerts:
  cpu_temp_warn_c: 70
  cpu_temp_alert_c: 80
  mem_pct_warn: 85
```

4. Start the add-on. After ~1 min HA exposes entities under
   `sensor.udm_<id_suffix>_*` and `binary_sensor.udm_<id_suffix>_reachable`.

## Sensors exposed

| Sensor | Unit | Notes |
|---|---|---|
| `cpu_pct` | % | system-stats.cpu |
| `mem_pct` | % | system-stats.mem |
| `mem_used_mb` / `mem_total_mb` | MB | from sys_stats |
| `temp_cpu` / `temp_board` / `temp_phy` | °C | hardware sensors |
| `temp_max` | °C | max of the 3 |
| `temp_status` | string | `ok` / `warn` / `alert` based on thresholds |
| `load_1` / `load_5` / `load_15` | — | unix load avg |
| `uptime` | timestamp | `device_class: timestamp` for nice "X days ago" rendering |
| `uptime_sec` | s | for counters/graphs |
| `power_w` | W | total PoE-Out |
| `clients` | — | LAN station count |
| `version` / `model` / `wan_ip` | string | metadata |
| `reachable` | binary | UDM API responding? |

## Prerequisites

- A **dedicated UniFi local-account** with read access (Settings → Admins).
  NOT the Ubiquiti cloud-SSO login.
- ⚠️ **Use a separate account from your HA UniFi-Network integration**.
  UDM-OS allows only one active session per user; sharing a login causes
  this add-on and HA's UniFi-Network integration to kick each other out
  every poll cycle. Suggestion: create `claude_monitor` (or similar) with
  read-only role, dedicated to this add-on.
- MQTT broker reachable from the add-on (typically Mosquitto add-on).
- A **dedicated MQTT user** for the add-on (the add-on auto-detects HA
  Supervisor-managed MQTT credentials if `mqtt.username`/`password` are
  blank; for stand-alone Mosquitto, create a user and put the credentials
  in the config).

## Multi-Instance

To monitor more than one UDM (e.g. yours + family), install the add-on
twice and give each instance a distinct `device.id_suffix`. Entity IDs
will not collide.
