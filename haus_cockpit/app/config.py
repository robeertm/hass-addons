"""haus-cockpit — configuration.

Read-only observer. Two deployment PROFILES, selected by env COCKPIT_PROFILE:

  • "robert" (default) — Robert's Pi. Shows BOTH houses. Radeberg feeds are
        native on the Pi's broker + the Pi's own HA (localhost). Klipphausen
        feeds arrive mirrored under `mike/…` via the Pi bridge, and Mike's HA
        is polled directly over the WireGuard tunnel (10.10.2.144).

  • "mike" — runs on Mike's HAOS (add-on). Shows ONLY Klipphausen, everything
        local: native MQTT topics (no `mike/` prefix) + local HA + local
        flow-collector. Mike sees just his part.

The cockpit never actuates anything (read-only on both houses).
"""
import os

PROFILE = os.environ.get("COCKPIT_PROFILE", "robert").strip().lower()
_IS_MIKE = PROFILE == "mike"

# ── MQTT (this host's broker) ───────────────────────────────────────────────
MQTT_HOST = os.environ.get("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER", "cockpit")
MQTT_PASS = os.environ.get("MQTT_PASS", "")
MQTT_CLIENT_ID = os.environ.get("MQTT_CLIENT_ID", f"haus-cockpit-{PROFILE}")

# On Mike's own instance the feeds are native (no bridge prefix). On Robert's
# instance Klipphausen feeds live under `mike/`.
KLIPP_PREFIX = os.environ.get("KLIPP_PREFIX", "" if _IS_MIKE else "mike/")

# ── Web ─────────────────────────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", "8099"))
REFRESH_SEC = int(os.environ.get("REFRESH_SEC", "4"))

# ── Docker (read-only socket) ───────────────────────────────────────────────
DOCKER_SOCK = os.environ.get("DOCKER_SOCK", "/var/run/docker.sock")

# ── Freshness thresholds (seconds) ──────────────────────────────────────────
FRESH_SEC = int(os.environ.get("FRESH_SEC", "90"))
STALE_SEC = int(os.environ.get("STALE_SEC", "300"))

# ── HA sources (read-only /api/states pollers) ──────────────────────────────
HA_POLL_SEC = int(os.environ.get("HA_POLL_SEC", "30"))
# Radeberg / Robert HA
HA_URL = os.environ.get("HA_URL", "http://127.0.0.1:8123")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
# Klipphausen / Mike HA — on Robert's box this is the WG address; on Mike's own
# instance it's local (falls back to HA_URL/HA_TOKEN there).
MIKE_HA_URL = os.environ.get("MIKE_HA_URL", HA_URL if _IS_MIKE else "http://10.10.2.144:8123")
MIKE_HA_TOKEN = os.environ.get("MIKE_HA_TOKEN", HA_TOKEN if _IS_MIKE else "")

# ── flow-collector (IPFIX) + NextDNS ────────────────────────────────────────
RAD_FLOWCOL_URL = os.environ.get("FLOWCOL_URL", "http://127.0.0.1:3002")
# Mike's collector: local on his instance, over WG from Robert's box.
MIKE_FLOWCOL_URL = os.environ.get(
    "MIKE_FLOWCOL_URL",
    "http://127.0.0.1:3002" if _IS_MIKE else "http://10.10.2.144:3002")
NEXTDNS_API_KEY = os.environ.get("NEXTDNS_API_KEY", "")
NEXTDNS_PROFILE = os.environ.get("NEXTDNS_PROFILE", "")

# ── SNMP (read-only SNMPv3 authPriv per-port UDM interface counters) ────────
SNMP_USER = os.environ.get("SNMP_USER", "")
SNMP_AUTH_PASS = os.environ.get("SNMP_AUTH_PASS", "")
SNMP_PRIV_PASS = os.environ.get("SNMP_PRIV_PASS", "")
SNMP_POLL_SEC = int(os.environ.get("SNMP_POLL_SEC", "30"))
RAD_SNMP_HOST = os.environ.get("SNMP_HOST", "10.30.1.1")            # Robert UDM
MIKE_SNMP_HOST = os.environ.get("MIKE_SNMP_HOST", "10.10.2.1")      # Mike UDM (local on his box, WG from Robert's)

# ── Service registry ────────────────────────────────────────────────────────
_RAD_SERVICES = [
    {"key": "flow-collector", "label": "flow-collector", "icon": "network",
     "blurb": "IPFIX → per-device Traffic", "house": "radeberg",
     "avail_topic": "flowcol/status", "fresh_topic": "flowcol/heartbeat",
     "fresh_kind": "iso", "ts_field": "ts"},
    {"key": "rpi-health", "label": "rpi-health-monitor", "icon": "cpu",
     "blurb": "Pi 5 Vitals · NVMe SMART", "house": "radeberg",
     "avail_topic": "rpi_health/robert_pi/availability", "fresh_topic": "rpi_health/robert_pi/state",
     "fresh_kind": "iso", "ts_field": "ts"},
    {"key": "udm-monitor", "label": "udm-monitor", "icon": "shield",
     "blurb": "UDM Pro SE · WAN · Clients", "house": "radeberg",
     "avail_topic": "udm_health/radeberg/state/availability", "fresh_topic": "udm_health/radeberg/state",
     "fresh_kind": "iso", "ts_field": "ts"},
    {"key": "shelly-analyzer", "label": "shelly-energy-analyzer", "icon": "bolt",
     "blurb": "Live-Leistung · Kosten · CO₂", "house": "radeberg",
     "avail_topic": None, "fresh_topic": "shelly_analyzer/shelly1/state",
     "fresh_kind": "unix", "ts_field": "timestamp"},
]


def _kp(topic):
    return f"{KLIPP_PREFIX}{topic}"


# Klipphausen services — topic prefix depends on profile. The Mac/Pi bridge
# itself is only a "service" on Robert's instance (Mike reads natively).
_KLIPP_SERVICES = []
if not _IS_MIKE:
    _KLIPP_SERVICES.append(
        {"key": "mike-bridge", "label": "MQTT-Bridge (Pi)", "icon": "bridge",
         "blurb": "Mike → Robert Spiegel", "house": "klipphausen",
         "avail_topic": "mike/bridge/status", "fresh_topic": "mike/bridge/heartbeat",
         "fresh_kind": "iso", "ts_field": "ts"})
_KLIPP_SERVICES += [
    {"key": "mike-rpi", "label": "rpi-health-monitor", "icon": "cpu",
     "blurb": "Mike-Pi Vitals (SD)", "house": "klipphausen",
     "avail_topic": _kp("rpi_health/mike_pi/availability"), "fresh_topic": _kp("rpi_health/mike_pi/state"),
     "fresh_kind": "iso", "ts_field": "ts"},
    {"key": "mike-udm", "label": "udm-monitor", "icon": "shield",
     "blurb": "UDM Pro SE · Sonnenrain", "house": "klipphausen",
     "avail_topic": _kp("udm_health/sonnenrain/state/availability"), "fresh_topic": _kp("udm_health/sonnenrain/state"),
     "fresh_kind": "iso", "ts_field": "ts"},
    {"key": "mike-ble", "label": "ble-source-profiler", "icon": "network",
     "blurb": "3 BLE-Proxy-Quellen", "house": "klipphausen",
     "avail_topic": _kp("mike_ble_source/snapshot/availability"), "fresh_topic": _kp("mike_ble_source/snapshot/state"),
     "fresh_kind": "iso", "ts_field": None},
]

# ── Houses ──────────────────────────────────────────────────────────────────
_RADEBERG = {
    "key": "radeberg", "name": "Radeberg", "who": "Robert & Steffi",
    "accent": "mauve", "live": True,
    "panels": ["services", "security", "energy", "climate",
               "sensors", "pi", "udm", "snmp", "network", "docker"],
    "pi_topic": "rpi_health/robert_pi/state",
    "udm_topic": "udm_health/radeberg/state",
    "shelly_prefix": "shelly_analyzer", "flow_prefix": "flowcol",
    "ha_url": HA_URL, "ha_token": HA_TOKEN,
    "flowcol_url": RAD_FLOWCOL_URL, "snmp_host": RAD_SNMP_HOST,
    "nextdns_key": NEXTDNS_API_KEY, "nextdns_profile": NEXTDNS_PROFILE,
    "docker": True,
}
_KLIPPHAUSEN = {
    "key": "klipphausen", "name": "Klipphausen", "who": "Mike",
    "accent": "teal", "live": True,
    "panels": ["services", "solar", "security", "climate",
               "sensors", "pi", "udm", "snmp", "ble"],
    "pi_topic": _kp("rpi_health/mike_pi/state"),
    "udm_topic": _kp("udm_health/sonnenrain/state"),
    "ble_prefix": _kp("mike_ble_source").rstrip("/") if KLIPP_PREFIX else "mike_ble_source",
    "bridge_status_topic": _kp("bridge/status") if not _IS_MIKE else None,
    "ha_url": MIKE_HA_URL, "ha_token": MIKE_HA_TOKEN,
    "flowcol_url": MIKE_FLOWCOL_URL, "snmp_host": MIKE_SNMP_HOST,
    "nextdns_key": "", "nextdns_profile": "",     # Mike has no NextDNS
    "docker": False,                               # HAOS add-on has no docker socket
}

if _IS_MIKE:
    SERVICES = _KLIPP_SERVICES
    HOUSES = [_KLIPPHAUSEN]
else:
    SERVICES = _RAD_SERVICES + _KLIPP_SERVICES
    HOUSES = [_RADEBERG, _KLIPPHAUSEN]

SHELLY_DEVICES = ["shelly1", "shelly2", "shelly3", "shelly4"]

# ── History / charts ────────────────────────────────────────────────────────
HIST_SAMPLE_SEC = int(os.environ.get("HIST_SAMPLE_SEC", "20"))     # live sample cadence
HIST_MAXLEN = int(os.environ.get("HIST_MAXLEN", "1200"))          # ~6.6h at 20s
HIST_BACKFILL_HOURS = int(os.environ.get("HIST_BACKFILL_HOURS", "6"))
HIST_TRANSPORT_CAP = int(os.environ.get("HIST_TRANSPORT_CAP", "360"))

# Robert-side chart metric → HA recorder entity_id (instant-full charts)
CHART_HA_ENTITIES = {
    "pi.cpu_pct":              "sensor.robert_rpi_docker_cpu_auslastung",
    "pi.cpu_temp_c":           "sensor.robert_rpi_docker_cpu_temperatur",
    "pi.mem_pct":              "sensor.robert_rpi_docker_speicher_auslastung",
    "pi.disk_pct":             "sensor.robert_rpi_docker_disk_auslastung",
    "pi.load_1m":              "sensor.robert_rpi_docker_load_1_min",
    "pi.swap_pct":             "sensor.robert_rpi_docker_swap_auslastung",
    "pi.net_rx_mbs":           "sensor.robert_rpi_docker_netzwerk_rx",
    "pi.net_tx_mbs":           "sensor.robert_rpi_docker_netzwerk_tx",
    "pi.nvme_composite_temp_c":"sensor.robert_rpi_docker_nvme_temperatur",
    "pi.health_score":         "sensor.robert_rpi_docker_gesundheits_score",
    "udm.mem_pct":             "sensor.udm_pro_se_radeberg_speicher",
    "udm.temp_max":            "sensor.udm_pro_se_radeberg_max_temperatur",
    "udm.clients":             "sensor.udm_pro_se_radeberg_lan_clients",
    "udm.power_w":             "sensor.udm_pro_se_radeberg_poe_leistung",
    "energy.total_power_w":    "sensor.gesamtverbrauch_leistung",
    "energy.dev.shelly1":      "sensor.shelly_analyzer_haus_haus_power",
}

# Klipphausen solar/energy metric → Mike HA recorder entity_id (backfill via WG)
CHART_HA_ENTITIES_MIKE = {
    "solar.pv_w":            "sensor.emma_pv_ausgangsleistung",
    "solar.house_w":         "sensor.hausverbrauch_live",
    "solar.battery_soc":     "sensor.batterien_batterieladung",
    "solar.battery_power_w": "sensor.batterien_lade_entladeleistung",
    "solar.grid_feed_w":     "sensor.emma_einspeiseleistung",
    "solar.inverter_ac_w":   "sensor.wechselrichter_wirkleistung",
    "solar.daily_pv_kwh":    "sensor.emma_pv_ertrag_heute",
    "solar.daily_consume_kwh":"sensor.emma_verbrauch_heute",
}
