#!/usr/bin/env python3
"""Thread Mesh Diagnostics for Mike's HAOS (matter.js-based).

Polls matter.js Server (cluster 0x35 ThreadNetworkDiagnostics) for per-Eve
RSSI/LQI and publishes Home Assistant sensors via Supervisor proxy.

Architecture:
  matter.js WS (5580) -> read 0/53/7 (NeighborTable) per node
                      -> extract avg/last RSSI + LQI
                      -> compute aggregates
  Supervisor proxy   -> POST /core/api/states/sensor.<prefix>_<name>

No OTBR access required. No docker exec required. Pure HAOS-friendly.
"""
import asyncio
import json
import logging
import os
import sys
import time
from typing import Any

import requests
import websockets


# ---------------------------------------------------------------------------
# Config from env (set by run.sh from bashio::config)
# ---------------------------------------------------------------------------
MJS_HOST = os.environ.get("MJS_HOST", "a35e7931-matterjs")
MJS_PORT = int(os.environ.get("MJS_PORT", "5580"))
INTERVAL = int(os.environ.get("INTERVAL", "300"))
SENSOR_PREFIX = os.environ.get("SENSOR_PREFIX", "thread_rssi")
NAME_OVERRIDES = json.loads(os.environ.get("NAME_OVERRIDES_JSON", "{}"))

# Supervisor proxy — adds Bearer auth automatically based on add-on token
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
HA_API = "http://supervisor/core/api"

logging.basicConfig(
    level=os.environ.get("PYLOG", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("thread_mesh_diag")


# ---------------------------------------------------------------------------
# matter.js fetch
# ---------------------------------------------------------------------------
async def matterjs_snapshot() -> dict[str, Any]:
    """Connect to matter.js, fetch nodes + per-node NeighborTable."""
    url = f"ws://{MJS_HOST}:{MJS_PORT}/ws"
    log.info("Connecting matter.js %s", url)
    async with websockets.connect(url, max_size=20 * 1024 * 1024) as ws:
        hello = json.loads(await ws.recv())
        log.debug("hello: sdk=%s", hello.get("sdk_version"))
        await ws.send(json.dumps({"message_id": "1", "command": "start_listening"}))
        listening = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
        nodes = listening.get("result", [])

        snap: dict[str, Any] = {"nodes": {}, "fabric_id": hello.get("fabric_id")}
        for n in nodes:
            nid = n["node_id"]
            attrs = n.get("attributes", {})
            node_info = {
                "node_id": nid,
                "available": n.get("available"),
                "vendor": attrs.get("0/40/1"),
                "product": attrs.get("0/40/3"),
                "node_label": attrs.get("0/40/5"),
                "serial": attrs.get("0/40/15"),
                "neighbors": [],
                "is_sleepy": True,  # default; refined below
            }
            # Read ThreadNetworkDiagnostics NeighborTable (cluster 0x35 / 53 attr 0x07)
            try:
                await ws.send(json.dumps({
                    "message_id": f"th{nid}",
                    "command": "read_attribute",
                    "args": {"node_id": nid, "attribute_path": "0/53/7"},
                }))
                r = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
                ntable = r.get("result", {}).get("0/53/7") or []
                for ent in ntable:
                    # NeighborTableEntry struct fields (Matter spec):
                    # 0=ExtAddress, 1=Age, 2=Rloc16, 3=LinkFC, 4=MleFC, 5=LQI,
                    # 6=AverageRssi, 7=LastRssi, 8=FrameErrPct, 9=MsgErrPct,
                    # 10=RxOnWhenIdle, 11=FullThreadDevice, 12=FullNetworkData,
                    # 13=IsChild
                    node_info["neighbors"].append({
                        "extaddr": f"{ent.get('0', 0):016x}",
                        "rloc16": ent.get("2"),
                        "age_s": ent.get("1"),
                        "lqi": ent.get("5"),
                        "rssi_avg": ent.get("6"),
                        "rssi_last": ent.get("7"),
                        "err_frame_pct": ent.get("8"),
                        "err_msg_pct": ent.get("9"),
                        "rx_on_when_idle": ent.get("10"),
                        "is_child": ent.get("13"),
                    })
            except Exception as e:
                log.warning("node %s NeighborTable read failed: %s", nid, e)

            # Try RoutingRole attr 0/53/1: 0=unspecified 1=unassigned 2=sleepy-end
            # 3=end-device 4=reed 5=router 6=leader
            try:
                await ws.send(json.dumps({
                    "message_id": f"rr{nid}",
                    "command": "read_attribute",
                    "args": {"node_id": nid, "attribute_path": "0/53/1"},
                }))
                r = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
                rr = r.get("result", {}).get("0/53/1")
                node_info["routing_role"] = rr
                # Routers (5/6) and REEDs (4) are mains-powered; sleepy (2/3) are battery
                node_info["is_sleepy"] = rr in (2, 3, None)
            except Exception as e:
                log.debug("node %s RoutingRole failed: %s", nid, e)

            snap["nodes"][str(nid)] = node_info
        return snap


# ---------------------------------------------------------------------------
# HA REST API publish
# ---------------------------------------------------------------------------
def ha_post_state(entity_id: str, state: Any, attributes: dict[str, Any] | None = None) -> None:
    if SUPERVISOR_TOKEN is None:
        log.error("SUPERVISOR_TOKEN missing — cannot publish")
        return
    headers = {
        "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
        "Content-Type": "application/json",
    }
    body = {"state": state}
    if attributes:
        body["attributes"] = attributes
    url = f"{HA_API}/states/{entity_id}"
    try:
        r = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
        if r.status_code >= 300:
            log.warning("POST %s -> %d: %s", entity_id, r.status_code, r.text[:200])
        else:
            log.debug("POST %s -> %d", entity_id, r.status_code)
    except Exception as e:
        log.error("POST %s exc: %s", entity_id, e)


# ---------------------------------------------------------------------------
# Sensor builder
# ---------------------------------------------------------------------------
RSSI_ATTRS = {
    "unit_of_measurement": "dBm",
    "device_class": "signal_strength",
    "state_class": "measurement",
}


def node_slug(node_id: str, info: dict[str, Any]) -> str:
    """Pick a stable slug for sensor naming."""
    ov = NAME_OVERRIDES.get(str(node_id))
    if ov:
        return ov
    # Fall back to vendor+node_id
    base = (info.get("node_label") or info.get("product") or f"node{node_id}")
    base = base.lower()
    out = []
    for c in base:
        if c.isalnum():
            out.append(c)
        elif c in (" ", "-", "_"):
            out.append("_")
    s = "".join(out).strip("_")
    while "__" in s:
        s = s.replace("__", "_")
    return s or f"node{node_id}"


def publish_snapshot(snap: dict[str, Any]) -> int:
    nodes = snap.get("nodes", {})
    n_total = len(nodes)
    n_with_data = 0

    # Aggregate accumulators
    all_best: list[int] = []
    all_avgs: list[int] = []
    all_worsts: list[int] = []
    sleepy_best: list[int] = []
    sleepy_avgs: list[int] = []
    sleepy_worsts: list[int] = []

    # Per-node: publish best/avg-RSSI to a sensor
    for nid, info in nodes.items():
        neigh = info.get("neighbors") or []
        if not neigh:
            continue
        rssis = [n.get("rssi_avg") for n in neigh if n.get("rssi_avg") is not None]
        if not rssis:
            continue
        n_with_data += 1
        best = max(rssis)
        worst = min(rssis)
        avg = round(sum(rssis) / len(rssis), 1)
        all_best.append(best)
        all_avgs.append(avg)
        all_worsts.append(worst)
        if info.get("is_sleepy"):
            sleepy_best.append(best)
            sleepy_avgs.append(avg)
            sleepy_worsts.append(worst)

        slug = node_slug(nid, info)
        entity_id = f"sensor.{SENSOR_PREFIX}_{slug}"
        attrs = dict(RSSI_ATTRS)
        attrs["friendly_name"] = f"Thread RSSI {slug.replace('_', ' ').title()}"
        attrs["node_id"] = int(nid)
        attrs["n_neighbors"] = len(neigh)
        attrs["rssi_avg"] = avg
        attrs["rssi_worst"] = worst
        attrs["best_neighbor_rloc16"] = (
            f"0x{[x for x in neigh if x.get('rssi_avg') == best][0].get('rloc16', 0):04x}"
        )
        attrs["routing_role"] = info.get("routing_role")
        attrs["serial"] = info.get("serial")
        attrs["product"] = info.get("product")
        attrs["available"] = info.get("available")
        # Publish best-RSSI as the state (highest signal = primary metric)
        ha_post_state(entity_id, best, attrs)
        log.info(
            "  %-30s n_neigh=%d best=%d avg=%.1f worst=%d  %s",
            entity_id, len(neigh), best, avg, worst, info.get("product", "")[:25],
        )

    # Aggregates
    def _publish_agg(eid: str, value, friendly: str, extra: dict | None = None) -> None:
        attrs = dict(RSSI_ATTRS)
        attrs["friendly_name"] = friendly
        if extra:
            attrs.update(extra)
        ha_post_state(eid, value if value is not None else "unknown", attrs)

    if all_best:
        _publish_agg(f"sensor.{SENSOR_PREFIX}_best", max(all_best), "Thread RSSI Best (alle)")
        _publish_agg(f"sensor.{SENSOR_PREFIX}_worst", min(all_worsts), "Thread RSSI Worst (alle)")
        _publish_agg(
            f"sensor.{SENSOR_PREFIX}_avg",
            round(sum(all_avgs) / len(all_avgs), 1),
            "Thread RSSI Avg (alle)",
        )
    if sleepy_best:
        _publish_agg(
            f"sensor.{SENSOR_PREFIX.replace('thread_rssi', 'thread_sleepy_rssi')}_best",
            max(sleepy_best),
            "Thread Sleepy RSSI Best",
        )
        _publish_agg(
            f"sensor.{SENSOR_PREFIX.replace('thread_rssi', 'thread_sleepy_rssi')}_worst",
            min(sleepy_worsts),
            "Thread Sleepy RSSI Worst",
        )
        _publish_agg(
            f"sensor.{SENSOR_PREFIX.replace('thread_rssi', 'thread_sleepy_rssi')}_avg",
            round(sum(sleepy_avgs) / len(sleepy_avgs), 1),
            "Thread Sleepy RSSI Avg",
        )

    # Master summary sensor — count of nodes
    ha_post_state(
        f"sensor.{SENSOR_PREFIX.replace('_rssi', '_mesh_nodes')}",
        n_total,
        {
            "friendly_name": "Thread Mesh Nodes",
            "n_with_rssi": n_with_data,
            "fabric_id": snap.get("fabric_id"),
            "updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
    )

    return n_with_data


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
async def cycle() -> None:
    try:
        snap = await asyncio.wait_for(matterjs_snapshot(), timeout=60)
        n = publish_snapshot(snap)
        log.info("Cycle done: %d/%d nodes with RSSI", n, len(snap.get("nodes", {})))
    except Exception as e:
        log.error("Cycle failed: %s", e, exc_info=True)


async def main() -> None:
    log.info("Starting main loop (interval=%ds)", INTERVAL)
    while True:
        await cycle()
        await asyncio.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
