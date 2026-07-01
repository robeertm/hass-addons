#!/usr/bin/env python3
"""BLE Source Profiler — MQTT add-on.

Subscribes to HA's `bluetooth/subscribe_advertisements` event stream over
the WebSocket API for `sweep_seconds` at a time, aggregates per-source
statistics (advert count, unique addresses, RSSI min/avg/max) plus a
per-named-device best-source picker, and publishes:

- Per configured source: `<prefix>_<key>_adverts`, `_unique_devices`,
  `_rssi_avg`, `_rssi_best`, `_rssi_worst` sensors (MQTT Discovery)
- Aggregate: `<prefix>_snapshot` sensor whose state is the last-update
  epoch and whose attributes carry the full `named_devices` array (used
  by Lovelace markdown for per-device comparison tables).

Design port of Robert's `dump_ble_sources.py` cron-script into a HAOS
add-on: instead of writing `/www/ble_sources.json`, the aggregated state
is emitted via MQTT so it survives HAOS restrictions.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import time
from collections import defaultdict
from pathlib import Path

import paho.mqtt.client as mqtt
import websockets

LOG = logging.getLogger("ble_source_profiler")


# ---------------------------------------------------------------------------
# MQTT
# ---------------------------------------------------------------------------
class MQTTPub:
    def __init__(self, host: str, port: int, user: str, pwd: str):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=f"ble_source_profiler_{os.getpid()}")
        if user:
            self.client.username_pw_set(user, pwd)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.host = host
        self.port = port
        self.connected = False

    def _on_connect(self, c, userdata, flags, reason_code, properties):
        if reason_code == 0:
            LOG.info("MQTT connected %s:%s", self.host, self.port)
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
SOURCE_SENSORS = [
    # (suffix, name, icon, unit, device_class, state_class)
    ("adverts",         "Adverts /Sweep",        "mdi:bluetooth-transfer",  None,   None,          "measurement"),
    ("unique_devices",  "Unique Devices /Sweep", "mdi:bluetooth-connect",   None,   None,          "measurement"),
    ("rssi_avg",        "RSSI Avg",              "mdi:signal",              "dBm",  "signal_strength", "measurement"),
    ("rssi_best",       "RSSI Best",             "mdi:signal-cellular-3",   "dBm",  "signal_strength", "measurement"),
    ("rssi_worst",      "RSSI Worst",            "mdi:signal-cellular-outline", "dBm", "signal_strength", "measurement"),
]


def publish_discovery(mq: MQTTPub, disc_prefix: str, device_prefix: str,
                      device_name: str, sources: list[dict]) -> None:
    """One-shot MQTT Discovery publish for all configured sources + snapshot."""
    dev = {
        "identifiers": [f"ble_source_profiler_{device_prefix}"],
        "name": device_name,
        "manufacturer": "Custom",
        "model": "BLE Source Profiler",
    }

    for src in sources:
        key = src["key"]
        friendly = src["name"]
        state_topic = f"{device_prefix}/{key}/state"
        avail_topic = f"{device_prefix}/{key}/availability"
        for suffix, name, icon, unit, dc, sc in SOURCE_SENSORS:
            uid = f"{device_prefix}_{key}_{suffix}"
            payload = {
                "name": f"{friendly} {name}",
                "uniq_id": uid,
                "stat_t": state_topic,
                "val_tpl": f"{{{{ value_json.{suffix} }}}}",
                "device": dev,
                "icon": icon,
                "avty_t": avail_topic,
                "pl_avail": "online",
                "pl_not_avail": "offline",
            }
            if unit:
                payload["unit_of_meas"] = unit
            if dc:
                payload["dev_cla"] = dc
            if sc:
                payload["stat_cla"] = sc
            topic = f"{disc_prefix}/sensor/{uid}/config"
            mq.publish(topic, json.dumps(payload), retain=True)

    # Snapshot sensor (aggregate — state=timestamp, attributes=named_devices etc.)
    snap_uid = f"{device_prefix}_snapshot"
    snap_state = f"{device_prefix}/snapshot/state"
    snap_avail = f"{device_prefix}/snapshot/availability"
    snap_attr = f"{device_prefix}/snapshot/attributes"
    payload = {
        "name": "BLE Sources Snapshot",
        "uniq_id": snap_uid,
        "stat_t": snap_state,
        "json_attr_t": snap_attr,
        "device": dev,
        "icon": "mdi:radar",
        "device_class": "timestamp",
        "avty_t": snap_avail,
        "pl_avail": "online",
        "pl_not_avail": "offline",
    }
    mq.publish(f"{disc_prefix}/sensor/{snap_uid}/config", json.dumps(payload), retain=True)


# ---------------------------------------------------------------------------
# Sweep collector
# ---------------------------------------------------------------------------
def is_named(name: str, addr: str) -> bool:
    return bool(name) and name.upper() != addr.upper()


async def one_sweep(ha_url: str, ha_token: str, sample_seconds: int,
                    source_map: dict[str, dict]) -> dict:
    """Perform a single sweep and return aggregate stats.
    source_map: {upper_mac: {"name": ..., "key": ...}}
    """
    src_stats: dict = defaultdict(lambda: {"count": 0, "addrs": set(), "rssis": []})
    per_addr_src: dict = {}
    names: dict = {}

    async with websockets.connect(ha_url, max_size=20 * 1024 * 1024) as ws:
        # HA WS auth handshake
        await ws.recv()  # auth_required
        await ws.send(json.dumps({"type": "auth", "access_token": ha_token}))
        auth_resp = json.loads(await ws.recv())
        if auth_resp.get("type") != "auth_ok":
            raise RuntimeError(f"HA WS auth failed: {auth_resp}")
        await ws.send(json.dumps({"id": 1, "type": "bluetooth/subscribe_advertisements"}))

        end = time.time() + sample_seconds
        while time.time() < end:
            try:
                remaining = max(0.5, end - time.time())
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=remaining))
            except asyncio.TimeoutError:
                break
            if msg.get("type") != "event":
                continue
            for adv in msg.get("event", {}).get("add", []):
                addr = (adv.get("address") or "").upper()
                src = (adv.get("source") or "").upper()
                rssi = adv.get("rssi")
                name = adv.get("name") or ""
                if not addr or rssi is None:
                    continue
                src_stats[src]["count"] += 1
                src_stats[src]["addrs"].add(addr)
                src_stats[src]["rssis"].append(rssi)
                per_addr_src[(addr, src)] = rssi
                if is_named(name, addr):
                    names[addr] = name

    # Build per-source summary
    sources_out = []
    for src, stats in src_stats.items():
        rssis = stats["rssis"]
        info = source_map.get(src, {})
        sources_out.append({
            "source": src,
            "name": info.get("name") or f"Unknown ({src[-8:]})",
            "key": info.get("key"),
            "count": stats["count"],
            "uniq_devices": len(stats["addrs"]),
            "rssi_best": max(rssis) if rssis else None,
            "rssi_worst": min(rssis) if rssis else None,
            "rssi_avg": round(sum(rssis) / len(rssis), 1) if rssis else None,
        })
    sources_out.sort(key=lambda s: -s["count"])

    # Per-named-device
    named_devices = []
    for addr in names:
        rssis_by_src = {}
        for (a, src), rssi in per_addr_src.items():
            if a == addr:
                rssis_by_src[src] = rssi
        if not rssis_by_src:
            continue
        best_src = max(rssis_by_src, key=lambda s: rssis_by_src[s])
        named_devices.append({
            "address": addr,
            "name": names[addr],
            "best_source": best_src,
            "best_source_name": (source_map.get(best_src) or {}).get("name",
                                f"({best_src[-8:]})"),
            "best_rssi": rssis_by_src[best_src],
            "rssis_per_source": rssis_by_src,
        })
    def sort_key(d):
        is_eve = d["name"].lower().startswith("eve")
        return (0 if is_eve else 1, -d["best_rssi"])
    named_devices.sort(key=sort_key)

    return {
        "updated": int(time.time()),
        "sample_seconds": sample_seconds,
        "sources": sources_out,
        "named_devices": named_devices,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def run_loop():
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else "/data/options.json"
    cfg = json.loads(Path(cfg_path).read_text())

    logging.basicConfig(
        level=getattr(logging, cfg.get("log_level", "info").upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    ha_url = cfg["ha"]["url"]
    ha_token = os.environ.get("BLE_HA_TOKEN") or cfg["ha"].get("token") or ""
    if not ha_token:
        LOG.error("No HA WS token — provide ha.token or ensure SUPERVISOR_TOKEN is set")
        sys.exit(1)

    sample_seconds = int(cfg["sample"]["sweep_seconds"])
    poll_interval = int(cfg["sample"]["poll_interval_seconds"])
    sources = cfg.get("sources") or []
    source_map = {s["mac"].upper(): {"name": s["name"], "key": s["key"]}
                  for s in sources if s.get("mac")}

    mq_cfg = cfg["mqtt"]
    mqtt_host = os.environ.get("BLE_MQTT_BROKER") or mq_cfg["broker"]
    mqtt_port = int(os.environ.get("BLE_MQTT_PORT") or mq_cfg["port"])
    mqtt_user = os.environ.get("BLE_MQTT_USER") or mq_cfg.get("username") or ""
    mqtt_pass = os.environ.get("BLE_MQTT_PASS") or mq_cfg.get("password") or ""

    disc_prefix = mq_cfg["discovery_prefix"]
    device_prefix = mq_cfg["device_prefix"]
    device_name = mq_cfg.get("device_name", "BLE Source Profiler")

    LOG.info("HA WS: %s | MQTT: %s:%s | sources: %d | sweep %ds every %ds",
             ha_url, mqtt_host, mqtt_port, len(sources), sample_seconds, poll_interval)

    mq = MQTTPub(mqtt_host, mqtt_port, mqtt_user, mqtt_pass)
    mq.connect()
    for _ in range(20):
        if mq.connected: break
        await asyncio.sleep(0.5)
    if not mq.connected:
        LOG.warning("MQTT not connected after 10s — continuing anyway")

    publish_discovery(mq, disc_prefix, device_prefix, device_name, sources)
    LOG.info("Published discovery for %d sources + snapshot", len(sources))

    # availability
    for s in sources:
        mq.publish(f"{device_prefix}/{s['key']}/availability", "online", retain=True)
    mq.publish(f"{device_prefix}/snapshot/availability", "online", retain=True)

    stop = asyncio.Event()
    def _sig(*a):
        stop.set()
        LOG.info("Signal — stopping")
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, _sig)

    # ---- Main loop -----------------------------------------------------
    while not stop.is_set():
        loop_start = time.time()
        try:
            data = await one_sweep(ha_url, ha_token, sample_seconds, source_map)
        except Exception as e:
            LOG.warning("Sweep error: %s", e)
            data = None

        if data:
            # publish per-source states
            for src in data["sources"]:
                key = src.get("key")
                if not key:
                    continue
                state_payload = {
                    "adverts": src["count"],
                    "unique_devices": src["uniq_devices"],
                    "rssi_avg": src["rssi_avg"],
                    "rssi_best": src["rssi_best"],
                    "rssi_worst": src["rssi_worst"],
                    "source_mac": src["source"],
                    "updated": data["updated"],
                }
                mq.publish(f"{device_prefix}/{key}/state",
                           json.dumps(state_payload), retain=True)

            # aggregate snapshot
            from datetime import datetime, timezone
            ts_iso = datetime.fromtimestamp(data["updated"], timezone.utc).isoformat()
            mq.publish(f"{device_prefix}/snapshot/state", ts_iso, retain=True)
            mq.publish(f"{device_prefix}/snapshot/attributes",
                       json.dumps({
                           "sample_seconds": data["sample_seconds"],
                           "n_sources": len(data["sources"]),
                           "n_named_devices": len(data["named_devices"]),
                           "sources": data["sources"],
                           "named_devices": data["named_devices"],
                       }, ensure_ascii=False), retain=True)
            LOG.info("Sweep: %d sources, %d named devices",
                     len(data["sources"]), len(data["named_devices"]))

        # sleep until next poll
        elapsed = time.time() - loop_start
        sleep_for = max(1, poll_interval - int(elapsed))
        try:
            await asyncio.wait_for(stop.wait(), timeout=sleep_for)
        except asyncio.TimeoutError:
            pass

    # offline announcements
    for s in sources:
        mq.publish(f"{device_prefix}/{s['key']}/availability", "offline", retain=True)
    mq.publish(f"{device_prefix}/snapshot/availability", "offline", retain=True)
    LOG.info("Bye")


if __name__ == "__main__":
    asyncio.run(run_loop())
