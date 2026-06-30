# RPi Health Monitor (HA Add-on)

Monitor your Raspberry Pi / HAOS host with deep stats: CPU/Memory/Disk/SD-IO/Network/Voltage/Throttling, plus a daily SD-write tracker and SD-card endurance estimate.

Designed for HAOS but also runs as a plain systemd service on Debian/Raspbian (same script, different runtime).

## Sensors (38 numeric + 6 binary)

| Group | Sensors |
|---|---|
| CPU | Auslastung %, User %, System %, IO Wait %, Temperatur °C, Frequenz MHz |
| Load | 1m / 5m / 15m, Uptime (Tage) |
| Memory | Total/Used/Free/Cache MB, Used %, Swap Used/% |
| Disk (root) | Total/Used/Free GB, Used % |
| SD-Karte | Read+Write **MB/s jetzt**, IOPS, **GB heute**, GB total, Wear %, Restjahre |
| Netzwerk | RX/TX MB/s, Total GB |
| Pi-spezifisch | Core Voltage V, Throttled (now+ever), Untervoltage, Soft-Temp-Limit |
| Composite | Gesundheits-Score (0-100) |

## Konfiguration

```yaml
device:
  name: "Mike RPi (HAOS)"
  id_suffix: "mike_pi"      # eindeutiger MQTT-Topic-Suffix
poll:
  interval_seconds: 30
disk:
  block_device: "mmcblk0"   # /proc/diskstats device name
  sd_tbw_lifetime_gb: 300   # nominale SD-TBW (Consumer ~100-500 GB, Endurance ~50000 GB)
alerts:
  cpu_temp_warn_c: 70
  cpu_temp_alert_c: 80
  mem_pct_warn: 85
  disk_pct_warn: 85
```

MQTT-Credentials werden automatisch vom Mosquitto-Add-on geholt wenn leer.

## Sample-Loop

Alle 30s (konfigurierbar) wird ein State-Payload via MQTT publish:

```json
{
  "cpu_pct": 23.5,
  "cpu_temp_c": 56.8,
  "mem_pct": 41.2,
  "sd_write_mbs": 0.42,
  "sd_write_today_gb": 0.18,
  "health_score": 95,
  "throttled_ever": false,
  ...
}
```

HA Auto-Discovery erstellt für jeden Key einen Sensor unter dem Pi-Device.

## Standalone (systemd auf Debian-Pi)

Für Robert's Setup (HA als Docker auf Debian-Pi):

```bash
sudo apt install python3-paho-mqtt libraspberrypi-bin
sudo install -m 755 rpi_monitor.py /opt/rpi_monitor/rpi_monitor.py
# /etc/rpi_monitor/options.json mit obiger Konfig
sudo systemctl enable --now rpi-monitor
```

`rpi-monitor.service` siehe `examples/`.

## SD-Endurance Faustregel

- Consumer SD (SanDisk Ultra, Kingston Canvas Select): **100-500 GB TBW** → 1-3 Jahre HA
- High Endurance (Samsung Pro Endurance, SanDisk Max Endurance): **30-100 TB TBW** → 10-50 Jahre HA
- Industrial SD: **100+ TB TBW**

Setze `sd_tbw_lifetime_gb` auf den Wert deiner Karte → `sd_years_left` zeigt dann die geschätzte Restlebensdauer basierend auf der aktuellen täglichen Schreiblast.
