"""security — the Internet & Security panel.

Fuses three sources per house (all optional, all read-only):
  • flow-collector  (:3002/api/state) — IPFIX per-device traffic with GeoIP:
       top countries, top services, per-VLAN, and per-host foreign destinations.
       Robert runs it on the Pi; Mike gets it as a HAOS add-on (until then this
       source is simply absent and the panel falls back to UniFi).
  • NextDNS  (api.nextdns.io) — DNS query/block analytics. Only when an API key
       is configured; otherwise a "configure key" placeholder. (Mike: none.)
  • UniFi  (from the HA snapshot) — WAN throughput / IP / client count. Always
       available where the UniFi integration exists; the honest fallback.

A background poller keeps flow-collector + NextDNS fresh; UniFi is read straight
from the already-polled HA snapshot at request time.
"""
import json
import threading
import time
import urllib.request

# rough service → risk tint used by the frontend (defensive context only)
RISK = {"Bitcoin": "peach", "Tor": "red", "port-": "subtext"}

_HOME_CC = "DE"


def _flag(cc):
    if not cc or len(cc) != 2 or not cc.isalpha():
        return "🏳️"
    cc = cc.upper()
    try:
        return chr(0x1F1E6 + ord(cc[0]) - 65) + chr(0x1F1E6 + ord(cc[1]) - 65)
    except Exception:
        return "🏳️"


def _mb(b):
    try:
        return round(b / 1_000_000, 1)
    except Exception:
        return None


class SecuritySource:
    def __init__(self, key, flowcol_url=None, nextdns_key=None, nextdns_profile=None,
                 poll_sec=15, timeout=8):
        self.key = key
        self.flowcol_url = (flowcol_url or "").rstrip("/")
        self.nextdns_key = nextdns_key or ""
        self.nextdns_profile = nextdns_profile or ""
        self.poll_sec = poll_sec
        self.timeout = timeout
        self._lock = threading.Lock()
        self._flow = None
        self._flow_ok = None
        self._nextdns = None
        self._nextdns_ok = None
        self._started = False

    @property
    def has_flow(self):
        return bool(self.flowcol_url)

    @property
    def has_nextdns(self):
        return bool(self.nextdns_key and self.nextdns_profile)

    # ── flow-collector ────────────────────────────────────────────────────────
    def _fetch_flow(self):
        if not self.has_flow:
            return
        try:
            with urllib.request.urlopen(f"{self.flowcol_url}/api/state", timeout=self.timeout) as r:
                raw = json.loads(r.read())
        except Exception:
            return
        flow = self._shape_flow(raw)
        with self._lock:
            self._flow = flow
            self._flow_ok = time.time()

    def _shape_flow(self, raw):
        totals = raw.get("totals", {}) or {}
        live = raw.get("live", {}) or {}
        countries = []
        for c in (raw.get("top_countries") or [])[:10]:
            cc = c.get("cc")
            countries.append({"cc": cc, "flag": _flag(cc), "mb": _mb(c.get("bytes")),
                              "foreign": bool(cc and cc != _HOME_CC and cc != "??")})
        services = [{"name": s.get("name"), "mb": _mb(s.get("bytes"))}
                    for s in (raw.get("top_services") or [])[:10]]
        hosts = []
        for h in (raw.get("top_hosts") or [])[:12]:
            dests = []
            for d in (h.get("top_dest") or [])[:5]:
                dests.append({"ip": d.get("ip"), "mb": _mb(d.get("bytes"))})
            hcountries = [{"cc": c.get("cc"), "flag": _flag(c.get("cc")), "mb": _mb(c.get("bytes"))}
                          for c in (h.get("top_countries") or [])[:4]]
            foreign_mb = sum((c["mb"] or 0) for c in hcountries if c["cc"] not in (_HOME_CC, "??", None))
            hosts.append({
                "ip": h.get("ip"), "name": h.get("name"), "vlan": h.get("vlan_name"),
                "total_mb": _mb(h.get("total")), "v6_share": h.get("v6_share"),
                "flows": h.get("flows"), "dests": dests, "countries": hcountries,
                "foreign_mb": round(foreign_mb, 1),
                "top_service": (h.get("top_services") or [{}])[0].get("name"),
            })
        vlans = []
        pv = raw.get("per_vlan") or []
        pv_items = pv.items() if isinstance(pv, dict) else enumerate(pv)
        for vid, v in pv_items:
            if isinstance(v, dict):
                vlans.append({"id": v.get("id", vid),
                              "name": v.get("name") or v.get("vlan_name"),
                              "mb": _mb(v.get("total") if v.get("total") is not None else v.get("bytes")),
                              "hosts": v.get("hosts") or v.get("host_count")})
        vlans.sort(key=lambda x: -(x["mb"] or 0))
        return {
            "live": {"mbits": live.get("throughput_mbits"), "flows_s": live.get("flows_per_sec")},
            "totals": {"gb": round((totals.get("bytes") or 0) / 1e9, 2),
                       "v6_share": totals.get("v6_share"),
                       "gb_v4": round((totals.get("bytes_v4") or 0) / 1e9, 2),
                       "gb_v6": round((totals.get("bytes_v6") or 0) / 1e9, 2)},
            "host_count": raw.get("host_count"),
            "countries": countries, "services": services, "hosts": hosts, "vlans": vlans,
        }

    # ── NextDNS ───────────────────────────────────────────────────────────────
    def _fetch_nextdns(self):
        if not self.has_nextdns:
            return
        base = f"https://api.nextdns.io/profiles/{self.nextdns_profile}"
        hdr = {"X-Api-Key": self.nextdns_key}
        try:
            def _g(path):
                req = urllib.request.Request(base + path, headers=hdr)
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.loads(r.read())
            status = _g("/analytics/status?from=-24h")
            domains = _g("/analytics/domains?from=-24h&limit=8")
            blocked = _g("/analytics/domains?from=-24h&limit=8&status=blocked")
        except Exception:
            return
        rows = {d.get("status", "?"): d.get("queries") for d in status.get("data", [])}
        total = sum(v for v in rows.values() if isinstance(v, (int, float)))
        blk = rows.get("blocked", 0) or 0
        shaped = {
            "queries": total, "blocked": blk,
            "block_pct": round(blk / total * 100, 1) if total else None,
            "allowed": rows.get("default", 0) or rows.get("allowed", 0),
            "top_domains": [{"domain": d.get("domain"), "queries": d.get("queries")}
                            for d in domains.get("data", [])[:8]],
            "top_blocked": [{"domain": d.get("domain"), "queries": d.get("queries")}
                            for d in blocked.get("data", [])[:8]],
        }
        with self._lock:
            self._nextdns = shaped
            self._nextdns_ok = time.time()

    # ── loop ──────────────────────────────────────────────────────────────────
    def _loop(self):
        while True:
            self._fetch_flow()
            self._fetch_nextdns()
            time.sleep(self.poll_sec)

    def start(self):
        if self._started or not (self.has_flow or self.has_nextdns):
            return
        self._started = True
        threading.Thread(target=self._loop, daemon=True, name=f"sec-{self.key}").start()

    # ── UniFi from HA snapshot (read at request time) ─────────────────────────
    def _unifi(self, ha_snap):
        if not ha_snap:
            return None
        def n(eid):
            e = ha_snap.get(eid)
            return e.get("num") if e else None
        def s(eid):
            e = ha_snap.get(eid)
            return e.get("state") if e else None
        # try both houses' UDM naming
        dl = n("sensor.unifi_gesamt_download") or n("sensor.udm_wan_download")
        ul = n("sensor.unifi_gesamt_upload") or n("sensor.udm_wan_upload")
        wan = (s("sensor.udm_pro_se_sonnenrain_wan_ipv4")
               or s("sensor.udm_pro_se_radeberg_wan_ip") or s("sensor.udm_wan_ip"))
        if dl is None and ul is None and wan is None:
            return None
        return {"download_mbit": dl, "upload_mbit": ul, "wan_ip": wan}

    def snapshot(self, ha_snap=None):
        with self._lock:
            flow = self._flow
            flow_age = round(time.time() - self._flow_ok, 1) if self._flow_ok else None
            nextdns = self._nextdns
            nd_age = round(time.time() - self._nextdns_ok, 1) if self._nextdns_ok else None
        return {
            "key": self.key,
            "flow": flow, "flow_age_sec": flow_age, "flow_enabled": self.has_flow,
            "nextdns": nextdns, "nextdns_age_sec": nd_age,
            "nextdns_enabled": self.has_nextdns,
            "unifi": self._unifi(ha_snap),
        }
