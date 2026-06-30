#!/usr/bin/env python3
"""RPi Health Monitor — polls /proc + /sys + vcgencmd for host stats and
publishes to MQTT with HA Auto-Discovery.

Works on:
- HAOS RPi (as HA Add-on, requires host_pid+host_network+SYS_RAWIO)
- Plain Debian/Raspbian RPi (as systemd-service, reads /proc directly)
- Other Linux hosts (x86, falls back gracefully — only Pi-specific metrics absent)

Reads config from /data/options.json (HA Add-on) OR
${RPI_MONITOR_CFG} env var (systemd-service).
"""
from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone, date
from pathlib import Path

import paho.mqtt.client as mqtt

LOG = logging.getLogger("rpi_monitor")

PROC = Path("/proc")
SYS = Path("/sys")


# ---------------------------------------------------------------------------
# Sample collectors
# ---------------------------------------------------------------------------
def read_file(p: Path, default: str = "") -> str:
    try:
        return p.read_text().strip()
    except Exception:
        return default


def sample_cpu_times() -> dict | None:
    """Read /proc/stat first 'cpu ' line. Returns dict of jiffies."""
    try:
        line = read_file(PROC / "stat").splitlines()[0]
        parts = line.split()
        if parts[0] != "cpu":
            return None
        # cpu user nice system idle iowait irq softirq steal guest guest_nice
        names = ["user","nice","system","idle","iowait","irq","softirq","steal"]
        vals = [int(p) for p in parts[1:9]]
        d = dict(zip(names, vals))
        d["total"] = sum(vals)
        return d
    except Exception as e:
        LOG.warning("cpu_times read failed: %s", e)
        return None


def sample_meminfo() -> dict:
    """Read /proc/meminfo, return key->kB int."""
    res = {}
    try:
        for line in read_file(PROC / "meminfo").splitlines():
            k, _, v = line.partition(":")
            v = v.strip().split()
            if not v:
                continue
            try:
                res[k.strip()] = int(v[0])  # kB
            except ValueError:
                pass
    except Exception as e:
        LOG.warning("meminfo read failed: %s", e)
    return res


def sample_loadavg() -> tuple[float, float, float]:
    try:
        parts = read_file(PROC / "loadavg").split()
        return float(parts[0]), float(parts[1]), float(parts[2])
    except Exception:
        return 0.0, 0.0, 0.0


def sample_uptime_seconds() -> float:
    try:
        return float(read_file(PROC / "uptime").split()[0])
    except Exception:
        return 0.0


def sample_cpu_temp_celsius() -> float | None:
    """Read /sys/class/thermal/thermal_zone0/temp (millidegree C)."""
    for zone in sorted((SYS / "class/thermal").glob("thermal_zone*")):
        t = read_file(zone / "temp")
        if t.isdigit():
            v = int(t) / 1000.0
            if 10 < v < 130:
                return round(v, 1)
    return None


def sample_cpu_freq_mhz() -> float | None:
    """Current CPU frequency in MHz, from cpufreq."""
    for cpu in sorted((SYS / "devices/system/cpu").glob("cpu[0-9]*")):
        f = read_file(cpu / "cpufreq/scaling_cur_freq")
        if f.isdigit():
            return round(int(f) / 1000.0, 0)  # kHz -> MHz
    return None


def sample_diskstats(block_device: str = "mmcblk0") -> dict | None:
    """Read /proc/diskstats for given block device. Returns sectors r/w + IOPS.
    Sector is 512 bytes.
    Format per line: major minor name reads_completed reads_merged sectors_read time_reading writes_completed writes_merged sectors_written time_writing ios_in_progress time_io weighted_time_io ...
    """
    try:
        for line in read_file(PROC / "diskstats").splitlines():
            parts = line.split()
            if len(parts) < 14:
                continue
            if parts[2] == block_device:
                return {
                    "reads_completed": int(parts[3]),
                    "sectors_read": int(parts[5]),
                    "time_reading_ms": int(parts[6]),
                    "writes_completed": int(parts[7]),
                    "sectors_written": int(parts[9]),
                    "time_writing_ms": int(parts[10]),
                    "ios_in_progress": int(parts[11]),
                    "time_io_ms": int(parts[12]),
                }
    except Exception as e:
        LOG.warning("diskstats read failed: %s", e)
    return None


def sample_disk_usage(path: str = "/") -> dict:
    """Disk usage of root filesystem via statvfs."""
    try:
        s = os.statvfs(path)
        total = s.f_blocks * s.f_frsize
        free = s.f_bavail * s.f_frsize
        used = total - free
        return {
            "total_b": total,
            "used_b": used,
            "free_b": free,
            "pct": (used / total * 100) if total else 0,
        }
    except Exception as e:
        LOG.warning("statvfs read failed: %s", e)
        return {"total_b": 0, "used_b": 0, "free_b": 0, "pct": 0}


def sample_netdev() -> dict:
    """Sum RX/TX bytes per interface from /proc/net/dev (skip lo, docker, veth, br-)."""
    res = {}
    try:
        for line in read_file(PROC / "net/dev").splitlines()[2:]:
            iface, _, data = line.partition(":")
            iface = iface.strip()
            if iface in ("lo",) or iface.startswith(("docker", "veth", "br-", "hassio")):
                continue
            parts = data.split()
            if len(parts) < 16:
                continue
            res[iface] = {
                "rx_bytes": int(parts[0]),
                "rx_packets": int(parts[1]),
                "rx_errors": int(parts[2]),
                "tx_bytes": int(parts[8]),
                "tx_packets": int(parts[9]),
                "tx_errors": int(parts[10]),
            }
    except Exception as e:
        LOG.warning("net/dev read failed: %s", e)
    return res


def _decode_throttled(v: int, raw_hex: str) -> dict:
    return {
        "raw_hex": raw_hex,
        "undervoltage_now":      bool(v & (1 << 0)),
        "freq_capped_now":       bool(v & (1 << 1)),
        "throttled_now":         bool(v & (1 << 2)),
        "soft_temp_limit_now":   bool(v & (1 << 3)),
        "undervoltage_ever":     bool(v & (1 << 16)),
        "freq_capped_ever":      bool(v & (1 << 17)),
        "throttled_ever":        bool(v & (1 << 18)),
        "soft_temp_limit_ever":  bool(v & (1 << 19)),
        "any_now":  any(bool(v & (1 << b)) for b in (0,1,2,3)),
        "any_ever": any(bool(v & (1 << b)) for b in (16,17,18,19)),
    }


def sample_throttled() -> dict:
    """Read RPi throttled status. Tries (1) /sys hwmon node (modern kernels),
    (2) vcgencmd CLI tool. Returns decoded flags or {}.
    Bits per Pi spec:
      0: under-voltage now
      1: arm frequency capped now
      2: throttled now
      3: soft temp limit reached now
      16+: same since boot
    """
    # 1) /sys: hwmon throttle counters from cpufreq driver (rpi5/cm5)
    for hw in sorted(SYS.glob("class/hwmon/hwmon*")):
        name = read_file(hw / "name")
        if "rpi" in name.lower():
            tmp = read_file(hw / "in0_lcrit_alarm")
            if tmp.isdigit():
                # in0_lcrit_alarm: 1 = undervoltage now
                v = 0
                if int(tmp) == 1:
                    v |= (1 << 0)
                return _decode_throttled(v, hex(v))
    # 2) /sys: legacy firmware sysfs (some BSPs expose direct throttled bitmap)
    for path_candidate in [
        "/sys/devices/platform/soc/soc:firmware/get_throttled",
        "/sys/class/leds/PWR/trigger",
    ]:
        v_str = read_file(Path(path_candidate))
        if v_str.startswith("0x"):
            try:
                v = int(v_str, 16)
                return _decode_throttled(v, v_str)
            except ValueError:
                pass
    # 3) vcgencmd
    try:
        out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True,
                             text=True, timeout=5)
        s = out.stdout.strip()
        if "=" in s:
            hex_val = s.split("=")[1].strip()
            v = int(hex_val, 16)
            return _decode_throttled(v, hex_val)
    except Exception:
        pass
    return {}


def sample_volts() -> dict:
    """vcgencmd measure_volts core/sdram_c/sdram_i/sdram_p"""
    res = {}
    for src in ("core", "sdram_c", "sdram_i", "sdram_p"):
        try:
            out = subprocess.run(["vcgencmd", "measure_volts", src],
                                 capture_output=True, text=True, timeout=5)
            s = out.stdout.strip()
            if "=" in s and "V" in s:
                res[src] = float(s.split("=")[1].rstrip("V"))
        except Exception:
            pass
    return res


def sample_pi_model() -> str:
    return read_file(PROC / "device-tree/model").rstrip("\x00") or "Unknown"


# ---------------------------------------------------------------------------
# MQTT helper
# ---------------------------------------------------------------------------
class MQTTPub:
    def __init__(self, host: str, port: int, user: str, pwd: str):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=f"rpi_health_{os.getpid()}")
        if user:
            self.client.username_pw_set(user, pwd)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.host = host
        self.port = port
        self.connected = False

    def _on_connect(self, c, userdata, flags, reason_code, properties):
        if reason_code == 0:
            LOG.info("MQTT connected to %s:%s", self.host, self.port)
            self.connected = True
        else:
            LOG.warning("MQTT connect failed: %s", reason_code)

    def _on_disconnect(self, c, userdata, flags, reason_code, properties):
        LOG.warning("MQTT disconnected: %s", reason_code)
        self.connected = False

    def connect(self):
        try:
            self.client.connect(self.host, self.port, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            LOG.warning("MQTT connect error: %s", e)

    def publish(self, topic: str, payload: str, retain: bool = False):
        if not self.connected:
            return
        self.client.publish(topic, payload, qos=0, retain=retain)


# ---------------------------------------------------------------------------
# HA Auto-Discovery
# ---------------------------------------------------------------------------
SENSORS = [
    # (key, name, icon, unit, device_class, state_class, options)
    ("cpu_pct",         "CPU Auslastung",        "mdi:chip",                 "%",     None,            "measurement", {}),
    ("cpu_user_pct",    "CPU User",              "mdi:account",              "%",     None,            "measurement", {}),
    ("cpu_system_pct",  "CPU System",            "mdi:cog",                  "%",     None,            "measurement", {}),
    ("cpu_iowait_pct",  "CPU I/O Wait",          "mdi:clock-alert",          "%",     None,            "measurement", {}),
    ("cpu_temp_c",      "CPU Temperatur",        "mdi:thermometer",          "°C",    "temperature",   "measurement", {}),
    ("cpu_freq_mhz",    "CPU Frequenz",          "mdi:speedometer",          "MHz",   "frequency",     "measurement", {}),
    ("load_1m",         "Load 1 min",            "mdi:gauge",                "load",  None,            "measurement", {}),
    ("load_5m",         "Load 5 min",            "mdi:gauge",                "load",  None,            "measurement", {}),
    ("load_15m",        "Load 15 min",           "mdi:gauge",                "load",  None,            "measurement", {}),
    ("uptime_days",     "Uptime",                "mdi:timer-outline",        "d",     None,            "measurement", {}),
    ("mem_total_mb",    "Speicher Total",        "mdi:memory",               "MB",    None,            "measurement", {}),
    ("mem_used_mb",     "Speicher belegt",       "mdi:memory",               "MB",    None,            "measurement", {}),
    ("mem_free_mb",     "Speicher frei",         "mdi:memory",               "MB",    None,            "measurement", {}),
    ("mem_pct",         "Speicher Auslastung",   "mdi:memory",               "%",     None,            "measurement", {}),
    ("mem_cache_mb",    "Cache+Buffer",          "mdi:cached",               "MB",    None,            "measurement", {}),
    ("swap_used_mb",    "Swap belegt",           "mdi:swap-vertical",        "MB",    None,            "measurement", {}),
    ("swap_pct",        "Swap Auslastung",       "mdi:swap-vertical",        "%",     None,            "measurement", {}),
    ("disk_total_gb",   "Disk Total",            "mdi:harddisk",             "GB",    None,            "measurement", {}),
    ("disk_used_gb",    "Disk belegt",           "mdi:harddisk",             "GB",    None,            "measurement", {}),
    ("disk_free_gb",    "Disk frei",             "mdi:harddisk",             "GB",    None,            "measurement", {}),
    ("disk_pct",        "Disk Auslastung",       "mdi:harddisk",             "%",     None,            "measurement", {}),
    ("sd_read_mbs",     "SD Read jetzt",         "mdi:download-network",     "MB/s",  "data_rate",     "measurement", {}),
    ("sd_write_mbs",    "SD Write jetzt",        "mdi:upload-network",       "MB/s",  "data_rate",     "measurement", {}),
    ("sd_read_iops",    "SD Read IOPS",          "mdi:database-arrow-down",  "IOPS",  None,            "measurement", {}),
    ("sd_write_iops",   "SD Write IOPS",         "mdi:database-arrow-up",    "IOPS",  None,            "measurement", {}),
    ("sd_read_today_gb",   "SD Read heute",      "mdi:download",             "GB",    None,            "measurement", {}),
    ("sd_write_today_gb",  "SD Write heute",     "mdi:upload",               "GB",    None,            "measurement", {}),
    ("sd_read_total_gb",   "SD Read total",      "mdi:download-network",     "GB",    None,            "total_increasing", {}),
    ("sd_write_total_gb",  "SD Write total",     "mdi:upload-network",       "GB",    None,            "total_increasing", {}),
    ("sd_wear_pct",     "SD Wear-Schätzung",     "mdi:battery-heart-variant","%",     None,            "measurement", {}),
    ("sd_years_left",   "SD Restjahre (geschätzt)", "mdi:calendar-clock",    "a",     None,            "measurement", {}),
    ("net_rx_mbs",      "Netzwerk RX",           "mdi:download",             "MB/s",  "data_rate",     "measurement", {}),
    ("net_tx_mbs",      "Netzwerk TX",           "mdi:upload",               "MB/s",  "data_rate",     "measurement", {}),
    ("net_rx_total_gb", "Netzwerk RX Total",     "mdi:download-network",     "GB",    None,            "total_increasing", {}),
    ("net_tx_total_gb", "Netzwerk TX Total",     "mdi:upload-network",       "GB",    None,            "total_increasing", {}),
    ("core_voltage_v",  "Core Spannung",         "mdi:flash",                "V",     "voltage",       "measurement", {}),
    ("health_score",    "Gesundheits-Score",     "mdi:heart-pulse",          "%",     None,            "measurement", {}),
    ("pi_model",        "Pi Modell",             "mdi:raspberry-pi",         None,    None,            None,          {}),
    ("os_kernel",       "Kernel",                "mdi:linux",                None,    None,            None,          {}),
]

BINARY_SENSORS = [
    # (key, name, icon, device_class)
    ("undervoltage_now",     "Untervoltage jetzt",      "mdi:flash-alert",     "problem"),
    ("freq_capped_now",      "Frequenz gedrosselt",     "mdi:speedometer-slow","problem"),
    ("throttled_now",        "Throttled jetzt",         "mdi:fire",            "problem"),
    ("soft_temp_limit_now",  "Soft-Temp-Limit",         "mdi:thermometer-high","problem"),
    ("undervoltage_ever",    "Untervoltage seit Boot",  "mdi:flash-alert",     "problem"),
    ("throttled_ever",       "Throttled seit Boot",     "mdi:fire",            "problem"),
]


def disc_topic(disc_prefix: str, dom: str, dev_id: str, key: str) -> str:
    return f"{disc_prefix}/{dom}/{dev_id}_{key}/config"


def discovery_payloads(device_id: str, device_name: str, pi_model: str,
                       state_topic: str, disc_prefix: str) -> list[tuple[str, dict]]:
    dev = {
        "identifiers": [f"rpi_{device_id}"],
        "name": device_name,
        "manufacturer": "Raspberry Pi Foundation",
        "model": pi_model,
    }
    out = []
    for key, name, icon, unit, dc, sc, opts in SENSORS:
        p = {
            "name": name,
            "uniq_id": f"{device_id}_{key}",
            "stat_t": state_topic,
            "val_tpl": f"{{{{ value_json.{key} }}}}",
            "device": dev,
            "icon": icon,
        }
        if unit:
            p["unit_of_meas"] = unit
        if dc:
            p["dev_cla"] = dc
        if sc:
            p["stat_cla"] = sc
        # availability
        p["avty_t"] = f"{state_topic.rsplit('/', 1)[0]}/availability"
        p["pl_avail"] = "online"
        p["pl_not_avail"] = "offline"
        out.append((disc_topic(disc_prefix, "sensor", device_id, key), p))
    for key, name, icon, dc in BINARY_SENSORS:
        p = {
            "name": name,
            "uniq_id": f"{device_id}_{key}",
            "stat_t": state_topic,
            "val_tpl": f"{{{{ 'ON' if value_json.{key} else 'OFF' }}}}",
            "pl_on": "ON", "pl_off": "OFF",
            "dev_cla": dc,
            "device": dev,
            "icon": icon,
            "avty_t": f"{state_topic.rsplit('/', 1)[0]}/availability",
            "pl_avail": "online",
            "pl_not_avail": "offline",
        }
        out.append((disc_topic(disc_prefix, "binary_sensor", device_id, key), p))
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def compute_health_score(state: dict, alerts: dict) -> int:
    """Composite health score 0-100. Higher = better."""
    score = 100
    # CPU temp
    t = state.get("cpu_temp_c")
    if t:
        if t > alerts.get("cpu_temp_alert_c", 80):  score -= 25
        elif t > alerts.get("cpu_temp_warn_c", 70): score -= 10
    # Memory
    m = state.get("mem_pct", 0)
    if m > 95:  score -= 20
    elif m > alerts.get("mem_pct_warn", 85): score -= 10
    # Disk
    d = state.get("disk_pct", 0)
    if d > 95:  score -= 20
    elif d > alerts.get("disk_pct_warn", 85): score -= 10
    # Throttling
    if state.get("throttled_now"):           score -= 15
    if state.get("undervoltage_now"):        score -= 15
    if state.get("throttled_ever"):          score -= 5
    if state.get("undervoltage_ever"):       score -= 5
    # CPU load (1m)
    cpu = state.get("cpu_pct", 0)
    if cpu > 95:  score -= 10
    return max(0, min(100, score))


def collect_state(prev_cpu: dict | None, prev_disk: dict | None,
                  prev_net: dict | None, prev_ts: float | None,
                  block_device: str, sd_tbw_lifetime_gb: int,
                  daily_baseline: dict, kernel: str, pi_model: str) -> tuple[dict, dict, dict, dict, float]:
    """Sample current values, calc deltas, return state + new prev refs."""
    now_ts = time.time()
    dt = (now_ts - prev_ts) if prev_ts else 1.0

    state: dict = {}

    # CPU times delta
    cpu_now = sample_cpu_times()
    if cpu_now and prev_cpu and cpu_now["total"] > prev_cpu["total"]:
        d_total = cpu_now["total"] - prev_cpu["total"]
        d_idle  = (cpu_now["idle"] - prev_cpu["idle"]) + (cpu_now["iowait"] - prev_cpu["iowait"])
        d_user  = cpu_now["user"]  - prev_cpu["user"]
        d_sys   = cpu_now["system"]- prev_cpu["system"]
        d_iow   = cpu_now["iowait"]- prev_cpu["iowait"]
        state["cpu_pct"]        = round((d_total - d_idle) / d_total * 100, 1)
        state["cpu_user_pct"]   = round(d_user / d_total * 100, 1)
        state["cpu_system_pct"] = round(d_sys  / d_total * 100, 1)
        state["cpu_iowait_pct"] = round(d_iow  / d_total * 100, 1)

    # Memory
    m = sample_meminfo()
    if m:
        mt = m.get("MemTotal", 0) / 1024.0       # kB -> MB
        ma = m.get("MemAvailable", m.get("MemFree", 0)) / 1024.0
        mc = (m.get("Cached", 0) + m.get("Buffers", 0)) / 1024.0
        mu = mt - ma
        state["mem_total_mb"] = round(mt, 0)
        state["mem_used_mb"]  = round(mu, 0)
        state["mem_free_mb"]  = round(ma, 0)
        state["mem_cache_mb"] = round(mc, 0)
        state["mem_pct"]      = round(mu / mt * 100, 1) if mt else 0
        st = m.get("SwapTotal", 0) / 1024.0
        sf = m.get("SwapFree", 0) / 1024.0
        state["swap_used_mb"] = round(st - sf, 0)
        state["swap_pct"]     = round((st - sf) / st * 100, 1) if st else 0

    # Load + Uptime
    l1, l5, l15 = sample_loadavg()
    state["load_1m"], state["load_5m"], state["load_15m"] = l1, l5, l15
    state["uptime_days"] = round(sample_uptime_seconds() / 86400.0, 2)

    # Temp + Freq
    t = sample_cpu_temp_celsius()
    if t is not None: state["cpu_temp_c"] = t
    f = sample_cpu_freq_mhz()
    if f is not None: state["cpu_freq_mhz"] = f

    # Disk
    du = sample_disk_usage("/")
    state["disk_total_gb"] = round(du["total_b"] / 1e9, 2)
    state["disk_used_gb"]  = round(du["used_b"] / 1e9, 2)
    state["disk_free_gb"]  = round(du["free_b"] / 1e9, 2)
    state["disk_pct"]      = round(du["pct"], 1)

    # SD diskstats delta
    disk_now = sample_diskstats(block_device)
    if disk_now and prev_disk:
        d_r = max(0, disk_now["sectors_read"]    - prev_disk["sectors_read"]) * 512
        d_w = max(0, disk_now["sectors_written"] - prev_disk["sectors_written"]) * 512
        d_rc = max(0, disk_now["reads_completed"]  - prev_disk["reads_completed"])
        d_wc = max(0, disk_now["writes_completed"] - prev_disk["writes_completed"])
        if dt > 0:
            state["sd_read_mbs"]   = round(d_r / dt / 1e6, 2)
            state["sd_write_mbs"]  = round(d_w / dt / 1e6, 2)
            state["sd_read_iops"]  = round(d_rc / dt, 1)
            state["sd_write_iops"] = round(d_wc / dt, 1)
    if disk_now:
        # Lifetime cumulative
        state["sd_read_total_gb"]  = round(disk_now["sectors_read"]    * 512 / 1e9, 3)
        state["sd_write_total_gb"] = round(disk_now["sectors_written"] * 512 / 1e9, 3)
        # Today delta — relative to baseline at midnight
        today_str = date.today().isoformat()
        if daily_baseline.get("date") != today_str:
            daily_baseline["date"] = today_str
            daily_baseline["read_sectors"]  = disk_now["sectors_read"]
            daily_baseline["write_sectors"] = disk_now["sectors_written"]
        state["sd_read_today_gb"]  = round(max(0, disk_now["sectors_read"]    - daily_baseline["read_sectors"])  * 512 / 1e9, 3)
        state["sd_write_today_gb"] = round(max(0, disk_now["sectors_written"] - daily_baseline["write_sectors"]) * 512 / 1e9, 3)
        # Wear estimate: % of SD-TBW used so far cumulatively
        if sd_tbw_lifetime_gb > 0:
            state["sd_wear_pct"] = round(state["sd_write_total_gb"] / sd_tbw_lifetime_gb * 100, 2)
            # Years left based on writes per day estimate via uptime
            ups = sample_uptime_seconds()
            if ups > 3600:
                writes_per_day = state["sd_write_total_gb"] * 86400 / ups
                if writes_per_day > 0.01:
                    remaining = max(0, sd_tbw_lifetime_gb - state["sd_write_total_gb"])
                    state["sd_years_left"] = round(remaining / writes_per_day / 365, 1)

    # Network
    nets = sample_netdev()
    if nets and prev_net:
        d_rx, d_tx = 0, 0
        for iface, cur in nets.items():
            prev = prev_net.get(iface)
            if not prev: continue
            d_rx += max(0, cur["rx_bytes"] - prev["rx_bytes"])
            d_tx += max(0, cur["tx_bytes"] - prev["tx_bytes"])
        if dt > 0:
            state["net_rx_mbs"] = round(d_rx / dt / 1e6, 2)
            state["net_tx_mbs"] = round(d_tx / dt / 1e6, 2)
    if nets:
        total_rx = sum(n["rx_bytes"] for n in nets.values())
        total_tx = sum(n["tx_bytes"] for n in nets.values())
        state["net_rx_total_gb"] = round(total_rx / 1e9, 3)
        state["net_tx_total_gb"] = round(total_tx / 1e9, 3)

    # Throttling (vcgencmd, RPi only)
    th = sample_throttled()
    for k in ("undervoltage_now","freq_capped_now","throttled_now","soft_temp_limit_now",
              "undervoltage_ever","freq_capped_ever","throttled_ever","soft_temp_limit_ever"):
        state[k] = th.get(k, False)
    if th.get("raw_hex"):
        state["throttled_raw"] = th["raw_hex"]

    # Voltage
    volts = sample_volts()
    if "core" in volts: state["core_voltage_v"] = round(volts["core"], 3)

    # Identifiers
    state["pi_model"] = pi_model
    state["os_kernel"] = kernel

    return state, cpu_now or prev_cpu, disk_now or prev_disk, nets or prev_net, now_ts


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    # ---- Load config -----------------------------------------------------
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("RPI_MONITOR_CFG", "/data/options.json")
    try:
        cfg = json.loads(Path(cfg_path).read_text())
    except Exception as e:
        LOG.error("Cannot read config %s: %s", cfg_path, e)
        sys.exit(1)

    log_level = cfg.get("log_level", "info").upper()
    logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))

    dev_name   = cfg["device"]["name"]
    dev_id     = cfg["device"]["id_suffix"]
    interval   = max(10, int(cfg["poll"]["interval_seconds"]))
    block_dev  = cfg["disk"]["block_device"]
    sd_tbw     = int(cfg["disk"].get("sd_tbw_lifetime_gb", 300))
    disc_prefix = cfg["mqtt"]["discovery_prefix"]
    state_topic_prefix = cfg["mqtt"]["state_topic_prefix"]
    alerts     = cfg.get("alerts", {})

    mqtt_host = os.environ.get("RPI_MQTT_BROKER") or cfg["mqtt"]["broker"]
    mqtt_port = int(os.environ.get("RPI_MQTT_PORT") or cfg["mqtt"]["port"])
    mqtt_user = os.environ.get("RPI_MQTT_USER") or cfg["mqtt"].get("username") or ""
    mqtt_pass = os.environ.get("RPI_MQTT_PASS") or cfg["mqtt"].get("password") or ""

    LOG.info("Monitoring %s (id=%s) → MQTT %s:%s every %ds", dev_name, dev_id, mqtt_host, mqtt_port, interval)

    state_topic   = f"{state_topic_prefix}/{dev_id}/state"
    avail_topic   = f"{state_topic_prefix}/{dev_id}/availability"

    pi_model = sample_pi_model()
    kernel = read_file(Path("/proc/sys/kernel/osrelease")) or "?"
    LOG.info("Pi model: %s | Kernel: %s", pi_model, kernel)

    # ---- MQTT -----------------------------------------------------------
    mq = MQTTPub(mqtt_host, mqtt_port, mqtt_user, mqtt_pass)
    mq.connect()

    # wait for connection up to 10s
    for _ in range(20):
        if mq.connected: break
        time.sleep(0.5)

    # publish discovery once
    for topic, payload in discovery_payloads(dev_id, dev_name, pi_model,
                                              state_topic, disc_prefix):
        mq.publish(topic, json.dumps(payload), retain=True)
    LOG.info("Published %d discovery configs", len(SENSORS)+len(BINARY_SENSORS))

    # availability online
    mq.publish(avail_topic, "online", retain=True)

    # ---- Sample loop ----------------------------------------------------
    stop = False
    def _sig(signum, frame):
        nonlocal stop
        stop = True
        LOG.info("Signal %s → stopping", signum)
    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)

    prev_cpu = None
    prev_disk = None
    prev_net = None
    prev_ts = None
    daily_baseline = {"date": None, "read_sectors": 0, "write_sectors": 0}

    # Warm-up sample (for first delta)
    prev_cpu = sample_cpu_times()
    prev_disk = sample_diskstats(block_dev)
    prev_net = sample_netdev()
    prev_ts = time.time()
    time.sleep(min(5, interval))

    while not stop:
        try:
            state, prev_cpu, prev_disk, prev_net, prev_ts = collect_state(
                prev_cpu, prev_disk, prev_net, prev_ts,
                block_dev, sd_tbw, daily_baseline, kernel, pi_model
            )
            state["health_score"] = compute_health_score(state, alerts)
            state["ts"] = datetime.now(timezone.utc).isoformat()
            mq.publish(state_topic, json.dumps(state), retain=True)
            mq.publish(avail_topic, "online", retain=True)
            LOG.debug("Published %d keys", len(state))
        except Exception as e:
            LOG.exception("Sample loop error: %s", e)

        # Sleep with stop-check
        for _ in range(interval):
            if stop: break
            time.sleep(1)

    mq.publish(avail_topic, "offline", retain=True)
    LOG.info("Bye")


if __name__ == "__main__":
    main()
