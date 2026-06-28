#!/usr/bin/env python3
"""UDM Health Monitor — polls UniFi UDM hardware sensors, publishes to MQTT.

Designed to run as a Home Assistant Add-on. Reads /data/options.json,
authenticates against the UDM local API, polls system stats every N seconds,
and publishes them to MQTT with HA Auto-Discovery payloads.

Sensors exposed:
- CPU %, Mem %, Mem used MB
- Temp CPU °C, Temp Board °C, Temp PHY °C
- Load 1/5/15
- Uptime (timestamp)
- Power total (W)
- Reachable (binary)
- Firmware version, model
- LAN clients count
"""
from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LOG = logging.getLogger("udm_monitor")


# ---------------------------------------------------------------------------
# UDM API client
# ---------------------------------------------------------------------------
class UDM:
    def __init__(self, host: str, username: str, password: str, verify_ssl: bool = False):
        self.base = f"https://{host}"
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self._logged_in = False

    def login(self) -> bool:
        try:
            r = self.session.post(
                f"{self.base}/api/auth/login",
                json={"username": self.username, "password": self.password, "remember": True},
                timeout=10,
            )
            self._logged_in = r.status_code == 200
            if not self._logged_in:
                LOG.warning("UDM login failed: HTTP %s body=%s", r.status_code, r.text[:200])
            return self._logged_in
        except Exception as e:
            LOG.warning("UDM login error: %s", e)
            return False

    def device(self) -> dict | None:
        if not self._logged_in and not self.login():
            return None
        try:
            r = self.session.get(
                f"{self.base}/proxy/network/api/s/default/stat/device",
                timeout=10,
            )
            if r.status_code == 401:
                # session expired
                self._logged_in = False
                if self.login():
                    r = self.session.get(
                        f"{self.base}/proxy/network/api/s/default/stat/device",
                        timeout=10,
                    )
            if r.status_code != 200:
                LOG.warning("UDM device API failed: HTTP %s", r.status_code)
                return None
            data = r.json().get("data", [])
            # find UDM
            for dev in data:
                if dev.get("type") == "udm" or "UDM" in dev.get("model", "").upper():
                    return dev
            LOG.warning("No UDM device found in /stat/device response")
            return None
        except Exception as e:
            LOG.warning("UDM device error: %s", e)
            self._logged_in = False
            return None


# ---------------------------------------------------------------------------
# MQTT helper
# ---------------------------------------------------------------------------
class MQTTPub:
    def __init__(self, host: str, port: int, user: str, pwd: str):
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"udm_health_{os.getpid()}",
        )
        if user:
            self.client.username_pw_set(user, pwd)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.host = host
        self.port = port
        self.connected = False

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            LOG.info("MQTT connected to %s:%s", self.host, self.port)
            self.connected = True
        else:
            LOG.warning("MQTT connect failed: %s", reason_code)
            self.connected = False

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
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
# HA Auto-Discovery sensor definitions
# ---------------------------------------------------------------------------
def discovery_configs(device_id: str, device_name: str,
                       state_topic: str, disc_prefix: str,
                       udm_host: str) -> list[tuple[str, dict]]:
    """Returns list of (topic, payload) for HA auto-discovery."""
    dev = {
        "identifiers": [f"udm_{device_id}"],
        "name": device_name,
        "manufacturer": "Ubiquiti",
        "model": "UniFi Dream Machine",
        "configuration_url": f"https://{udm_host}",
    }
    common = {
        "device": dev,
        "state_topic": state_topic,
        "availability_topic": f"{state_topic}/availability",
        "payload_available": "online",
        "payload_not_available": "offline",
    }

    def sensor(key: str, name: str, unit: str = None, ic: str = None,
                dc: str = None, sc: str = None, value_template: str = None,
                category: str = None):
        cfg = {
            **common,
            "name": name,
            "unique_id": f"udm_{device_id}_{key}",
            "object_id": f"udm_{device_id}_{key}",
            "value_template": value_template or f"{{{{ value_json.{key} }}}}",
        }
        if unit: cfg["unit_of_measurement"] = unit
        if ic: cfg["icon"] = ic
        if dc: cfg["device_class"] = dc
        if sc: cfg["state_class"] = sc
        if category: cfg["entity_category"] = category
        topic = f"{disc_prefix}/sensor/udm_{device_id}/{key}/config"
        return topic, cfg

    def binary(key: str, name: str, ic: str = None, dc: str = None, category: str = None):
        cfg = {
            **common,
            "name": name,
            "unique_id": f"udm_{device_id}_{key}",
            "object_id": f"udm_{device_id}_{key}",
            "value_template": f"{{{{ value_json.{key} }}}}",
            "payload_on": "on",
            "payload_off": "off",
        }
        if ic: cfg["icon"] = ic
        if dc: cfg["device_class"] = dc
        if category: cfg["entity_category"] = category
        topic = f"{disc_prefix}/binary_sensor/udm_{device_id}/{key}/config"
        return topic, cfg

    return [
        sensor("cpu_pct", "CPU", "%", "mdi:cpu-32-bit", sc="measurement"),
        sensor("mem_pct", "Speicher", "%", "mdi:memory", sc="measurement"),
        sensor("mem_used_mb", "Speicher belegt", "MB", "mdi:memory", sc="measurement"),
        sensor("mem_total_mb", "Speicher gesamt", "MB", "mdi:memory", category="diagnostic"),
        sensor("temp_cpu", "CPU-Temperatur", "°C", "mdi:thermometer", dc="temperature", sc="measurement"),
        sensor("temp_board", "Board-Temperatur", "°C", "mdi:thermometer", dc="temperature", sc="measurement"),
        sensor("temp_phy", "PHY-Temperatur", "°C", "mdi:thermometer", dc="temperature", sc="measurement"),
        sensor("temp_max", "Max-Temperatur", "°C", "mdi:thermometer-alert", dc="temperature", sc="measurement"),
        sensor("load_1", "Last 1m", None, "mdi:gauge", sc="measurement"),
        sensor("load_5", "Last 5m", None, "mdi:gauge", sc="measurement"),
        sensor("load_15", "Last 15m", None, "mdi:gauge", sc="measurement"),
        sensor("uptime", "Uptime", None, "mdi:clock-outline", dc="timestamp", category="diagnostic"),
        sensor("uptime_sec", "Uptime (s)", "s", "mdi:timer-outline", sc="total_increasing", category="diagnostic"),
        sensor("power_w", "PoE-Leistung", "W", "mdi:flash", dc="power", sc="measurement"),
        sensor("clients", "LAN-Clients", None, "mdi:account-network", sc="measurement"),
        sensor("version", "Firmware", None, "mdi:chip", category="diagnostic"),
        sensor("model", "Modell", None, "mdi:router", category="diagnostic"),
        sensor("wan_ip", "WAN-IPv4", None, "mdi:wan", category="diagnostic"),
        sensor("temp_status", "Temperatur-Status", None, "mdi:shield-check"),
        binary("reachable", "UDM erreichbar", dc="connectivity", category="diagnostic"),
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def build_state(dev: dict, alerts: dict) -> dict:
    sysstats = dev.get("system-stats", {}) or {}
    syss = dev.get("sys_stats", {}) or {}
    temps = {t.get("name", "").lower(): t.get("value", 0)
             for t in dev.get("temperatures", []) or []}
    mem_used = (syss.get("mem_used") or 0) / 1048576
    mem_total = (syss.get("mem_total") or 0) / 1048576
    uptime_sec = int(dev.get("uptime", 0))
    startup_ts = dev.get("startup_timestamp", 0)
    if startup_ts:
        uptime_iso = datetime.fromtimestamp(startup_ts, tz=timezone.utc).isoformat()
    else:
        uptime_iso = datetime.fromtimestamp(time.time() - uptime_sec, tz=timezone.utc).isoformat()

    t_cpu = temps.get("cpu", 0)
    t_max = max([temps.get("cpu", 0), temps.get("local", 0), temps.get("phy", 0)])

    warn = float(alerts.get("cpu_temp_warn_c", 70))
    alert = float(alerts.get("cpu_temp_alert_c", 80))
    if t_max >= alert:    status = "alert"
    elif t_max >= warn:   status = "warn"
    else:                 status = "ok"

    return {
        "cpu_pct": float(sysstats.get("cpu", 0)),
        "mem_pct": float(sysstats.get("mem", 0)),
        "mem_used_mb": round(mem_used, 0),
        "mem_total_mb": round(mem_total, 0),
        "temp_cpu": temps.get("cpu", 0),
        "temp_board": temps.get("local", 0),
        "temp_phy": temps.get("phy", 0),
        "temp_max": t_max,
        "temp_status": status,
        "load_1": float(syss.get("loadavg_1") or 0),
        "load_5": float(syss.get("loadavg_5") or 0),
        "load_15": float(syss.get("loadavg_15") or 0),
        "uptime": uptime_iso,
        "uptime_sec": uptime_sec,
        "power_w": float(dev.get("total_used_power") or 0),
        "clients": int(dev.get("num_sta") or 0),
        "version": dev.get("version", "?"),
        "model": dev.get("model", "?"),
        "wan_ip": dev.get("ip", ""),
    }


def main(cfg_path: str):
    with open(cfg_path) as f:
        cfg = json.load(f)

    logging.basicConfig(
        level=cfg.get("log_level", "info").upper(),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    udm_cfg = cfg["udm"]
    udm = UDM(udm_cfg["host"], udm_cfg["username"], udm_cfg["password"],
              verify_ssl=udm_cfg.get("verify_ssl", False))

    device_cfg = cfg["device"]
    device_id = device_cfg["id_suffix"]
    device_name = device_cfg["name"]

    mqtt_cfg = cfg["mqtt"]
    mqtt_host = os.environ.get("UDM_MQTT_BROKER") or mqtt_cfg["broker"]
    mqtt_port = int(os.environ.get("UDM_MQTT_PORT") or mqtt_cfg["port"])
    mqtt_user = os.environ.get("UDM_MQTT_USER") or mqtt_cfg.get("username", "")
    mqtt_pass = os.environ.get("UDM_MQTT_PASS") or mqtt_cfg.get("password", "")

    state_topic = f"{mqtt_cfg.get('state_topic_prefix','udm_health')}/{device_id}/state"
    avail_topic = f"{state_topic}/availability"
    disc_prefix = mqtt_cfg.get("discovery_prefix", "homeassistant")

    pub = MQTTPub(mqtt_host, mqtt_port, mqtt_user, mqtt_pass)
    pub.connect()

    # wait for MQTT to settle
    for _ in range(50):
        if pub.connected:
            break
        time.sleep(0.1)

    LOG.info("UDM: https://%s — device id=%s, name=%s",
             udm_cfg["host"], device_id, device_name)
    LOG.info("MQTT: %s:%s state_topic=%s discovery=%s",
             mqtt_host, mqtt_port, state_topic, disc_prefix)

    # publish discovery
    for topic, payload in discovery_configs(device_id, device_name,
                                              state_topic, disc_prefix, udm_cfg["host"]):
        pub.publish(topic, json.dumps(payload), retain=True)
    LOG.info("Published %d discovery configs", len(discovery_configs(device_id, device_name, state_topic, disc_prefix, udm_cfg["host"])))

    interval = int(cfg["poll"]["interval_seconds"])
    alerts = cfg.get("alerts", {})

    stop = False
    def shutdown(*_):
        nonlocal stop
        stop = True
        LOG.info("Shutting down")
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    failures = 0
    while not stop:
        dev = udm.device()
        if dev is None:
            failures += 1
            pub.publish(avail_topic, "offline", retain=True)
            payload = {"reachable": "off", "_error": "udm_unreachable", "_failures": failures}
            pub.publish(state_topic, json.dumps(payload), retain=False)
            LOG.warning("UDM poll failed (#%d), sleeping %ds", failures, interval)
        else:
            failures = 0
            state = build_state(dev, alerts)
            state["reachable"] = "on"
            pub.publish(avail_topic, "online", retain=True)
            pub.publish(state_topic, json.dumps(state), retain=False)
            LOG.info(
                "poll ok · CPU=%.1f%% MEM=%.1f%% Temps CPU/Board/PHY=%.1f/%.1f/%.1f °C [%s] up=%dd %dh",
                state["cpu_pct"], state["mem_pct"],
                state["temp_cpu"], state["temp_board"], state["temp_phy"],
                state["temp_status"],
                state["uptime_sec"] // 86400, (state["uptime_sec"] % 86400) // 3600,
            )
        for _ in range(interval):
            if stop:
                break
            time.sleep(1)

    pub.publish(avail_topic, "offline", retain=True)
    pub.client.loop_stop()
    pub.client.disconnect()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/data/options.json")
