"""ha_source — read-only Home-Assistant state poller.

Each HASource polls one HA instance's `/api/states` on a background thread and
caches the snapshot. On Robert's cockpit there are two: `radeberg` (the Pi's own
HA on localhost) and `klipphausen` (Mike's HA over the WireGuard tunnel). On
Mike's own single-house instance there is just one, pointing at localhost.

It is strictly read-only — it only ever GETs `/api/states` and (once) renders a
template to learn each entity's area. It never calls a service, never actuates.
Mike's "niemals testschalten" stays intact.

Unreachable HA (WireGuard down, token expired) fails soft: the last snapshot is
kept and marked stale via `age()`, so the UI degrades honestly instead of
crashing.
"""
import json
import threading
import time
import urllib.request
import urllib.error

# Jinja that dumps one line per entity: id|area|device_class|unit|friendly_name
_AREA_TEMPLATE = (
    "{% for s in states -%}\n"
    "{{ s.entity_id }}|{{ area_name(s.entity_id) }}|"
    "{{ s.attributes.device_class }}|{{ s.attributes.unit_of_measurement }}|"
    "{{ s.attributes.friendly_name }}\n"
    "{% endfor %}"
)


def _num(v):
    try:
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):
            return None
        return f
    except (TypeError, ValueError):
        return None


class HASource:
    def __init__(self, key, url, token, poll_sec=30, timeout=15):
        self.key = key
        self.url = (url or "").rstrip("/")
        self.token = token or ""
        self.poll_sec = poll_sec
        self.timeout = timeout
        self._lock = threading.Lock()
        self._states = {}        # entity_id -> normalized dict
        self._areas = {}         # entity_id -> {area, device_class, unit, name}
        self._last_ok = None     # epoch of last successful poll
        self._last_err = None
        self._started = False

    # ── enabled? ──────────────────────────────────────────────────────────────
    @property
    def enabled(self):
        return bool(self.url and self.token)

    # ── HTTP helpers ─────────────────────────────────────────────────────────
    def _get(self, path):
        req = urllib.request.Request(
            f"{self.url}{path}",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read())

    def _post_template(self):
        body = json.dumps({"template": _AREA_TEMPLATE}).encode()
        req = urllib.request.Request(
            f"{self.url}/api/template", data=body,
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return r.read().decode("utf-8", "replace")

    # ── registry (areas) — fetched once, refreshed lazily ────────────────────
    def _refresh_areas(self):
        try:
            text = self._post_template()
        except Exception as e:
            self._last_err = f"template: {e}"
            return
        areas = {}
        for line in text.splitlines():
            parts = line.split("|")
            if len(parts) < 5:
                continue
            eid, area, dclass, unit, name = parts[0], parts[1], parts[2], parts[3], parts[4]
            if not eid:
                continue
            areas[eid] = {
                "area": None if area in ("None", "") else area,
                "device_class": None if dclass in ("None", "") else dclass,
                "unit": None if unit in ("None", "") else unit,
                "name": None if name in ("None", "") else name,
            }
        if areas:
            with self._lock:
                self._areas = areas

    # ── state poll ────────────────────────────────────────────────────────────
    def poll_once(self):
        if not self.enabled:
            return
        try:
            data = self._get("/api/states")
        except Exception as e:
            self._last_err = f"states: {e}"
            return
        states = {}
        for s in data:
            eid = s.get("entity_id")
            if not eid:
                continue
            attrs = s.get("attributes", {}) or {}
            st = s.get("state")
            states[eid] = {
                "entity_id": eid,
                "state": st,
                "num": _num(st),
                "unit": attrs.get("unit_of_measurement"),
                "device_class": attrs.get("device_class"),
                "name": attrs.get("friendly_name") or eid,
                "icon": attrs.get("icon"),
                "last_changed": s.get("last_changed"),
                "attrs": attrs,
            }
        with self._lock:
            self._states = states
            self._last_ok = time.time()
            self._last_err = None

    def _loop(self):
        # areas first (best effort), then states forever
        self._refresh_areas()
        area_tick = 0
        while True:
            self.poll_once()
            area_tick += 1
            if area_tick % 20 == 0 and not self._areas:   # keep retrying areas
                self._refresh_areas()
            time.sleep(self.poll_sec)

    def start(self):
        if self._started or not self.enabled:
            return
        self._started = True
        threading.Thread(target=self._loop, daemon=True, name=f"ha-{self.key}").start()

    # ── access ────────────────────────────────────────────────────────────────
    def age(self):
        if not self._last_ok:
            return None
        return time.time() - self._last_ok

    def snapshot(self):
        """Return {entity_id: merged dict incl. area} — read from cache."""
        with self._lock:
            states = self._states
            areas = self._areas
        out = {}
        for eid, s in states.items():
            reg = areas.get(eid, {})
            merged = dict(s)
            merged["area"] = reg.get("area")
            if reg.get("device_class") and not merged.get("device_class"):
                merged["device_class"] = reg["device_class"]
            if reg.get("unit") and not merged.get("unit"):
                merged["unit"] = reg["unit"]
            out[eid] = merged
        return out

    def info(self):
        with self._lock:
            n = len(self._states)
            na = len(self._areas)
            ok = self._last_ok
            err = self._last_err
        return {
            "key": self.key, "enabled": self.enabled, "url": self.url,
            "entities": n, "areas_known": na,
            "age_sec": round(time.time() - ok, 1) if ok else None,
            "last_err": err,
        }
