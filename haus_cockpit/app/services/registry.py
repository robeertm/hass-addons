"""Registry / transformer — turns the raw MQTT snapshot + docker list into the
structured per-house state the cockpit renders. Freshness (up/stale/down) is
judged here — the whole point of the resilience work, made visible.
"""
import time
from datetime import datetime, timezone

import config
from services import docker_probe
from services import curate


# ── HA snapshot helpers ─────────────────────────────────────────────────────
def _ha_snap(ha_sources, key):
    src = (ha_sources or {}).get(key)
    return (src.snapshot() if src else {}), (src.info() if src else None)


def _num(snap, eid):
    e = snap.get(eid)
    return e.get("num") if e else None


def _security_summary(sec_snap):
    """Compact security block for the main /api/state."""
    if not sec_snap:
        return None
    flow = sec_snap.get("flow")
    unifi = sec_snap.get("unifi")
    nd = sec_snap.get("nextdns")
    out = {"flow_enabled": sec_snap.get("flow_enabled"),
           "nextdns_enabled": sec_snap.get("nextdns_enabled"),
           "flow_age_sec": sec_snap.get("flow_age_sec")}
    if flow:
        top_c = (flow.get("countries") or [{}])[0]
        top_s = (flow.get("services") or [{}])[0]
        out.update({"live_mbits": flow["live"].get("mbits"),
                    "total_gb": flow["totals"].get("gb"),
                    "v6_share": flow["totals"].get("v6_share"),
                    "host_count": flow.get("host_count"),
                    "top_country": top_c.get("cc"), "top_country_flag": top_c.get("flag"),
                    "top_service": top_s.get("name")})
    if unifi:
        out["unifi"] = unifi
    if nd:
        out.update({"nd_queries": nd.get("queries"), "nd_blocked": nd.get("blocked"),
                    "nd_block_pct": nd.get("block_pct")})
    return out


# ── timestamp helpers ───────────────────────────────────────────────────────
def _iso_to_epoch(s):
    try:
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return None


def _feed_epoch(entry, kind, ts_field):
    if not entry:
        return None
    j = entry.get("json")
    val = j.get(ts_field) if (j is not None and ts_field) else None
    if kind == "iso":
        if isinstance(val, str):
            e = _iso_to_epoch(val)
            if e:
                return e
        if entry.get("payload") and not j:          # payload itself is the iso ts
            e = _iso_to_epoch(entry["payload"].strip())
            if e:
                return e
    elif kind == "unix":
        try:
            return float(val)
        except (TypeError, ValueError):
            pass
    return entry.get("rx")


def _status_from_age(age, avail_offline):
    if avail_offline or age is None:
        return "down"
    if age <= config.FRESH_SEC:
        return "up"
    if age <= config.STALE_SEC:
        return "stale"
    return "down"


# ── per-service registry ────────────────────────────────────────────────────
def service_status(svc, ingest, now):
    fresh = ingest.get(svc["fresh_topic"])
    avail = ingest.get(svc["avail_topic"]) if svc.get("avail_topic") else None
    avail_val = (avail["payload"].strip().lower() if avail else None)
    avail_offline = avail_val == "offline"
    feed_ts = _feed_epoch(fresh, svc["fresh_kind"], svc.get("ts_field"))
    age = (now - feed_ts) if feed_ts else None
    return {
        "key": svc["key"], "label": svc["label"], "icon": svc["icon"],
        "blurb": svc["blurb"], "house": svc["house"],
        "status": _status_from_age(age, avail_offline),
        "avail": avail_val,
        "age_sec": round(age, 1) if age is not None else None,
        "last_epoch": feed_ts,
        "has_data": fresh is not None,
    }


# ── Pi vitals (generic per topic) ───────────────────────────────────────────
def pi_vitals(ingest, topic):
    e = ingest.get(topic)
    if not e or not e.get("json"):
        return None
    d = e["json"]; g = d.get
    has_nvme = g("nvme_composite_temp_c") is not None
    has_sd = g("sd_wear_pct") is not None
    return {
        "health_score": g("health_score"), "cpu_pct": g("cpu_pct"),
        "cpu_temp_c": g("cpu_temp_c"), "cpu_freq_mhz": g("cpu_freq_mhz"),
        "mem_pct": g("mem_pct"), "mem_used_mb": g("mem_used_mb"), "mem_total_mb": g("mem_total_mb"),
        "swap_pct": g("swap_pct"),
        "load_1m": g("load_1m"), "load_5m": g("load_5m"), "load_15m": g("load_15m"),
        "disk_pct": g("disk_pct"), "disk_used_gb": g("disk_used_gb"), "disk_total_gb": g("disk_total_gb"),
        "uptime_days": g("uptime_days"), "net_rx_mbs": g("net_rx_mbs"), "net_tx_mbs": g("net_tx_mbs"),
        "nvme_composite_temp_c": g("nvme_composite_temp_c"), "nvme_available_spare": g("nvme_available_spare"),
        "nvme_lifetime_written_tb": g("nvme_lifetime_written_tb"), "nvme_model": g("nvme_model"),
        "sd_wear_pct": g("sd_wear_pct"), "sd_years_left": g("sd_years_left"),
        "pi_model": g("pi_model"), "os_kernel": g("os_kernel"),
        "core_voltage_v": g("core_voltage_v"),
        "has_nvme": has_nvme, "has_sd": has_sd,
        "throttle": {
            "undervoltage": bool(g("undervoltage_now")), "freq_capped": bool(g("freq_capped_now")),
            "throttled": bool(g("throttled_now")), "soft_temp": bool(g("soft_temp_limit_now")),
            "undervoltage_ever": bool(g("undervoltage_ever")), "throttled_ever": bool(g("throttled_ever")),
        },
    }


# ── UDM vitals (generic per topic) ──────────────────────────────────────────
def udm_vitals(ingest, topic):
    e = ingest.get(topic)
    if not e or not e.get("json"):
        return None
    d = e["json"]; g = d.get
    up_days = round(g("uptime_sec") / 86400.0, 1) if g("uptime_sec") else None
    return {
        "cpu_pct": g("cpu_pct"), "mem_pct": g("mem_pct"),
        "mem_used_mb": g("mem_used_mb"), "mem_total_mb": g("mem_total_mb"),
        "temp_max": g("temp_max"), "temp_cpu": g("temp_cpu"), "temp_status": g("temp_status"),
        "load_1": g("load_1"), "clients": g("clients"), "power_w": g("power_w"),
        "wan_ip": g("wan_ip"), "version": g("version"), "model": g("model"),
        "reachable": g("reachable"), "uptime_days": up_days,
    }


# ── Energy (Shelly) ─────────────────────────────────────────────────────────
def energy(ingest):
    devices = []; total_power = 0.0; total_cost = 0.0
    for dev in config.SHELLY_DEVICES:
        e = ingest.get(f"shelly_analyzer/{dev}/state")
        if not e or not e.get("json"):
            continue
        d = e["json"]
        pw = d.get("power_w") or 0.0; cost = d.get("cost_eur_today") or 0.0
        total_power += pw; total_cost += cost
        devices.append({"id": dev, "name": d.get("name", dev), "power_w": round(pw, 1),
                        "energy_kwh": d.get("energy_kwh"), "cost_eur_today": round(cost, 2),
                        "voltage_v": d.get("voltage_v"), "current_a": d.get("current_a"),
                        "cosphi": d.get("cosphi"), "co2_g_per_h": d.get("co2_g_per_h")})
    if not devices:
        return None
    devices.sort(key=lambda x: -x["power_w"])
    netz = ingest.get("shelly_analyzer/netz/state")
    grid = netz["json"] if (netz and netz.get("json")) else {}
    return {"devices": devices, "total_power_w": round(total_power, 1),
            "total_cost_today": round(total_cost, 2),
            "spot_price_eur_kwh": grid.get("spot_price_eur_kwh"),
            "tariff_price_eur_kwh": grid.get("tariff_price_eur_kwh"),
            "co2_intensity": grid.get("co2_intensity_g_per_kwh")}


# ── Network top-talkers (flow-collector) ────────────────────────────────────
_VLAN_COLORS = {
    "Büro": "blue", "Buero": "blue", "IoT": "yellow", "SmartHome": "yellow",
    "Gäste": "peach", "Gaeste": "peach", "Kids": "green", "Server": "red",
    "BTC": "peach", "Mobile": "pink", "Heim": "teal", "Default": "subtext",
    "Kameras": "mauve", "Kamera": "mauve", "IoT-Cloud": "sapphire",
}


def top_talkers(ingest, limit=8):
    rows = []
    for topic, e in ingest.match("flowcol/dev/").items():
        if not topic.endswith("/attrs") or not e.get("json"):
            continue
        d = e["json"]
        total = (d.get("ipv4_mb") or 0) + (d.get("ipv6_mb") or 0)
        rows.append({"name": d.get("name_hint") or d.get("ip") or d.get("mac"),
                     "ip": d.get("ip"), "vlan": d.get("vlan"),
                     "vlan_color": _VLAN_COLORS.get(d.get("vlan"), "subtext"),
                     "ipv4_mb": round(d.get("ipv4_mb") or 0, 1), "ipv6_mb": round(d.get("ipv6_mb") or 0, 1),
                     "total_mb": round(total, 1), "v6_share": d.get("v6_share"),
                     "flows": d.get("flows"), "online": bool(d.get("online"))})
    if not rows:
        return None
    rows.sort(key=lambda x: -x["total_mb"])
    return {"rows": rows[:limit], "device_count": len(rows),
            "online_count": sum(1 for r in rows if r["online"])}


# ── BLE-proxy panel (Mike's ble_source_profiler) ────────────────────────────
def ble_panel(ingest, prefix):
    snap = ingest.get(f"{prefix}/snapshot/attributes")
    sources = []
    for key, e in ingest.match(f"{prefix}/").items():
        if not key.endswith("/state") or "snapshot" in key:
            continue
        j = e.get("json")
        if not j:
            continue
        sid = key.split("/")[-2]
        sources.append({"id": sid, "adverts": j.get("adverts"),
                        "unique_devices": j.get("unique_devices"), "rssi_avg": j.get("rssi_avg"),
                        "rssi_best": j.get("rssi_best"), "source_mac": j.get("source_mac")})
    if not sources and not snap:
        return None
    sources.sort(key=lambda x: (x["rssi_avg"] is None, -(x["rssi_avg"] or -999)))
    attrs = snap["json"] if (snap and snap.get("json")) else {}
    # attach friendly source names from snapshot
    name_by_mac = {s.get("source"): s.get("name") for s in attrs.get("sources", [])}
    name_by_key = {s.get("key"): s.get("name") for s in attrs.get("sources", [])}
    for s in sources:
        s["name"] = name_by_key.get(s["id"]) or name_by_mac.get(s["source_mac"]) or s["id"]
    return {"sources": sources, "n_named_devices": attrs.get("n_named_devices"),
            "n_sources": attrs.get("n_sources") or len(sources),
            "sample_seconds": attrs.get("sample_seconds"),
            "named_devices": (attrs.get("named_devices") or [])[:10]}


# ── assemble ────────────────────────────────────────────────────────────────
def _house_status(services):
    counts = {"up": 0, "stale": 0, "down": 0}
    for s in services:
        counts[s["status"]] = counts.get(s["status"], 0) + 1
    if counts["down"]:
        status = "critical"
    elif counts["stale"]:
        status = "degraded"
    else:
        status = "nominal"
    return status, counts


def _raw(ingest, h):
    """Full source payloads for the drill-down modals (every sensor field)."""
    r = {}
    e = ingest.get(h.get("pi_topic", ""))
    if e and e.get("json"):
        r["pi"] = e["json"]
    e = ingest.get(h.get("udm_topic", ""))
    if e and e.get("json"):
        r["udm"] = e["json"]
    if "energy" in h["panels"]:
        devs = {}
        for dev in config.SHELLY_DEVICES:
            de = ingest.get(f"shelly_analyzer/{dev}/state")
            if de and de.get("json"):
                devs[de["json"].get("name", dev)] = de["json"]
        nz = ingest.get("shelly_analyzer/netz/state")
        if nz and nz.get("json"):
            devs["Netz"] = nz["json"]
        if devs:
            r["energy"] = devs
    if "ble" in h["panels"]:
        srcs = {}
        for k, be in ingest.match(h.get("ble_prefix", "") + "/").items():
            if k.endswith("/state") and "snapshot" not in k and be.get("json"):
                srcs[k.split("/")[-2]] = be["json"]
        if srcs:
            r["ble"] = srcs
    return r


def build_state(ingest, ha_sources=None, sec_sources=None, snmp_sources=None, include_docker=True):
    now = time.time()
    all_services = [service_status(s, ingest, now) for s in config.SERVICES]
    containers = docker_probe.containers(config.DOCKER_SOCK) if include_docker else []

    houses = []
    for h in config.HOUSES:
        svc = [s for s in all_services if s["house"] == h["key"]]
        status, counts = _house_status(svc)
        hs = {"key": h["key"], "name": h["name"], "who": h["who"],
              "accent": h["accent"], "live": h["live"], "panels": h["panels"],
              "services": svc, "status": status, "counts": counts}
        if not h["live"]:
            houses.append(hs)
            continue
        # HA snapshot for this house (solar / climate / all-sensors)
        snap, ha_info = _ha_snap(ha_sources, h["key"])
        if ha_info:
            hs["ha"] = ha_info
        if "pi" in h["panels"]:
            hs["pi"] = pi_vitals(ingest, h["pi_topic"])
        if "udm" in h["panels"]:
            hs["udm"] = udm_vitals(ingest, h["udm_topic"])
        if "energy" in h["panels"]:
            hs["energy"] = energy(ingest) if h["key"] == "radeberg" else None
        if "network" in h["panels"]:
            hs["network"] = top_talkers(ingest)
        if "ble" in h["panels"]:
            hs["ble"] = ble_panel(ingest, h["ble_prefix"])
        if "docker" in h["panels"]:
            hs["containers"] = containers
        # HA-derived panels
        if snap:
            if "solar" in h["panels"]:
                hs["solar"] = curate.solar(snap)
            if "climate" in h["panels"]:
                clim = curate.climate(snap)
                # only per-room aggregates in the main state; full lists via /api/sensors
                hs["climate"] = [{k: r[k] for k in ("area", "temp_avg", "humid_avg", "n",
                                                    "climate")} for r in clim] if clim else None
            if "sensors" in h["panels"]:
                hs["sensors_summary"] = curate.summary(snap)
        # security summary
        sec = (sec_sources or {}).get(h["key"])
        if sec and "security" in h["panels"]:
            hs["security"] = _security_summary(sec.snapshot(snap))
        # SNMP per-port
        sp = (snmp_sources or {}).get(h["key"])
        if sp and "snmp" in h["panels"]:
            hs["snmp"] = sp.snapshot()
        hs["raw"] = _raw(ingest, h)
        houses.append(hs)

    # top banner = primary house (Robert's if present, else the only house)
    primary = next((x for x in houses if x["key"] == "radeberg"), houses[0])
    return {
        "generated_at": now,
        "server_ts_iso": datetime.now(timezone.utc).isoformat(),
        "profile": config.PROFILE,
        "overall": {"nominal": "nominal", "degraded": "degraded", "critical": "critical"}[primary["status"]],
        "counts": primary["counts"],
        "mqtt": ingest.conn_info(),
        "refresh_sec": config.REFRESH_SEC,
        "houses": houses,
    }


# ── detail endpoints (heavy payloads served on demand) ──────────────────────
def sensors_detail(ha_sources, house_key):
    """Full exhaustive sensor explorer + full climate detail for one house."""
    src = (ha_sources or {}).get(house_key)
    if not src:
        return {"explorer": None, "climate": None, "info": None}
    snap = src.snapshot()
    return {"explorer": curate.explorer(snap),
            "climate": curate.climate(snap),
            "info": src.info()}


def security_detail(sec_sources, ha_sources, house_key):
    """Full Internet & Security snapshot (flow-collector + NextDNS + UniFi)."""
    sec = (sec_sources or {}).get(house_key)
    if not sec:
        return None
    hs = (ha_sources or {}).get(house_key)
    ha_snap = hs.snapshot() if hs else None
    return sec.snapshot(ha_snap)
