"""In-memory time-series history for the cockpit charts.

A background sampler snapshots the live registry state every SAMPLE_SEC into
per-(house, metric) ring buffers. Robert's buffers are additionally *backfilled*
from Home Assistant's recorder on startup so the charts are full immediately
(Mike's fill live — the Pi can't reach Mike's HA recorder).
"""
import threading
import time
import json
import urllib.request
from collections import deque
from datetime import datetime, timezone, timedelta

import config


def extract_metrics(house):
    """Flatten a house state dict into {metric_key: numeric_value}."""
    m = {}
    pi = house.get("pi")
    if pi:
        for k in ("cpu_pct", "cpu_temp_c", "mem_pct", "disk_pct", "load_1m", "health_score",
                  "net_rx_mbs", "net_tx_mbs", "nvme_composite_temp_c", "sd_wear_pct", "swap_pct"):
            v = pi.get(k)
            if isinstance(v, (int, float)):
                m[f"pi.{k}"] = v
    udm = house.get("udm")
    if udm:
        for k in ("cpu_pct", "mem_pct", "temp_max", "clients", "power_w"):
            v = udm.get(k)
            if isinstance(v, (int, float)):
                m[f"udm.{k}"] = v
    en = house.get("energy")
    if en:
        if isinstance(en.get("total_power_w"), (int, float)):
            m["energy.total_power_w"] = en["total_power_w"]
        for k in ("spot_price_eur_kwh", "tariff_price_eur_kwh", "co2_intensity", "total_cost_today"):
            v = en.get(k)
            if isinstance(v, (int, float)):
                m[f"energy.{k}"] = v
        for d in en.get("devices", []):
            if isinstance(d.get("power_w"), (int, float)):
                m[f"energy.dev.{d['id']}"] = d["power_w"]
    net = house.get("network")
    if net:
        m["net.online"] = net.get("online_count", 0)
        m["net.total_mb"] = round(sum(r["total_mb"] for r in net.get("rows", [])), 1)
    ble = house.get("ble")
    if ble:
        for s in ble.get("sources", []):
            if isinstance(s.get("unique_devices"), (int, float)):
                m[f"ble.{s['id']}.dev"] = s["unique_devices"]
            if isinstance(s.get("rssi_avg"), (int, float)):
                m[f"ble.{s['id']}.rssi"] = s["rssi_avg"]
    sol = house.get("solar")
    if sol:
        for k in ("pv_w", "house_w", "battery_soc", "battery_power_w",
                  "grid_feed_w", "inverter_ac_w", "efficiency"):
            v = sol.get("now", {}).get(k)
            if isinstance(v, (int, float)):
                m[f"solar.{k}"] = v
        for k in ("pv_kwh", "consume_kwh", "feed_kwh", "grid_kwh"):
            v = sol.get("daily", {}).get(k)
            if isinstance(v, (int, float)):
                m[f"solar.daily_{k}"] = v
        if isinstance(sol.get("autarky_today_pct"), (int, float)):
            m["solar.autarky"] = sol["autarky_today_pct"]
    sec = house.get("security")
    if sec:
        for k in ("live_mbits", "total_gb", "host_count", "nd_block_pct", "v6_share"):
            v = sec.get(k)
            if isinstance(v, (int, float)):
                m[f"sec.{k}"] = v
    return m


class HistoryStore:
    def __init__(self, maxlen=None, sample_sec=None):
        self.maxlen = maxlen or config.HIST_MAXLEN
        self.sample_sec = sample_sec or config.HIST_SAMPLE_SEC
        self._lock = threading.Lock()
        self._buf = {}          # (house, key) -> deque[(epoch, value)]
        self._state_fn = None
        self._started = False

    def _dq(self, house, key):
        k = (house, key)
        dq = self._buf.get(k)
        if dq is None:
            dq = deque(maxlen=self.maxlen)
            self._buf[k] = dq
        return dq

    def add(self, house, key, epoch, value):
        with self._lock:
            dq = self._dq(house, key)
            # keep monotonic, skip dup timestamps
            if dq and epoch <= dq[-1][0]:
                return
            dq.append((round(epoch, 1), round(float(value), 3)))

    # ── sampler ─────────────────────────────────────────────────────────────
    def sample_once(self):
        if not self._state_fn:
            return
        try:
            state = self._state_fn()
        except Exception:
            return
        now = time.time()
        for h in state.get("houses", []):
            if not h.get("live"):
                continue
            for key, val in extract_metrics(h).items():
                self.add(h["key"], key, now, val)

    def _loop(self):
        while True:
            self.sample_once()
            time.sleep(self.sample_sec)

    def start(self, state_fn, ha_sources=None):
        self._state_fn = state_fn
        if self._started:
            return
        self._started = True
        # backfill both houses from their HA recorders (best effort), then sample live
        houses = {h["key"] for h in config.HOUSES}
        if "radeberg" in houses:
            self._safe_backfill("radeberg", config.HA_URL, config.HA_TOKEN,
                                config.CHART_HA_ENTITIES)
        if "klipphausen" in houses:
            self._safe_backfill("klipphausen", config.MIKE_HA_URL, config.MIKE_HA_TOKEN,
                                config.CHART_HA_ENTITIES_MIKE)
        threading.Thread(target=self._loop, daemon=True).start()

    def _safe_backfill(self, house, url, token, mapping):
        try:
            self.backfill_ha(house, url, token, mapping)
        except Exception as e:
            print(f"[history] backfill {house} skipped: {e}", flush=True)

    # ── access ──────────────────────────────────────────────────────────────
    def series(self, house, keys=None, cap=None):
        cap = cap or config.HIST_TRANSPORT_CAP
        out = {}
        with self._lock:
            for (h, key), dq in self._buf.items():
                if h != house:
                    continue
                if keys and key not in keys:
                    continue
                pts = list(dq)
                if len(pts) > cap:                      # uniform downsample for transport
                    step = len(pts) / cap
                    pts = [pts[int(i * step)] for i in range(cap)]
                out[key] = pts
        return out

    def stats(self):
        with self._lock:
            return {"buffers": len(self._buf),
                    "points": sum(len(dq) for dq in self._buf.values())}

    # ── HA recorder backfill (per house) ─────────────────────────────────────
    def backfill_ha(self, house, url, token, mapping):
        if not token or not mapping:
            print(f"[history] {house}: no HA token/mapping → live-only", flush=True)
            return
        ent2key = {v: k for k, v in mapping.items()}
        entities = ",".join(mapping.values())
        start = (datetime.now(timezone.utc) - timedelta(hours=config.HIST_BACKFILL_HOURS)).isoformat()
        api = (f"{url}/api/history/period/{start}"
               f"?filter_entity_id={entities}&minimal_response&no_attributes")
        req = urllib.request.Request(api, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        seeded = 0
        for series in data:
            if not series:
                continue
            ent = series[0].get("entity_id")
            key = ent2key.get(ent)
            if not key:
                continue
            for pt in series:
                st = pt.get("state")
                try:
                    val = float(st)
                except (TypeError, ValueError):
                    continue
                lu = pt.get("last_updated") or pt.get("last_changed")
                if not lu:
                    continue
                try:
                    ep = datetime.fromisoformat(lu.replace("Z", "+00:00")).timestamp()
                except Exception:
                    continue
                self.add(house, key, ep, val)
                seeded += 1
        print(f"[history] {house} backfill: seeded {seeded} pts / {len(mapping)} entities", flush=True)
