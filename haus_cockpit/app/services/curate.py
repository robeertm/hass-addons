"""curate — turn a raw HA snapshot into the structured, grouped views the
cockpit renders.

Three products:
  • solar()    — Huawei EMMA/LUNA2000/SUN2000 power-flow (Mike only). None if absent.
  • climate()  — climate entities + temperature/humidity grouped by room.
  • explorer() — EVERY entity, grouped by area (rooms) with a semantic fallback
                 bucket for area-less entities. This is the exhaustive catch-all:
                 no sensor is ever dropped.

Everything is read-only shaping of already-fetched state.
"""

# ── Huawei solar entity map (Mike) ──────────────────────────────────────────
_SOLAR_NOW = {
    "pv_w":              "sensor.emma_pv_ausgangsleistung",
    "inverter_ac_w":     "sensor.wechselrichter_wirkleistung",
    "inverter_in_w":     "sensor.wechselrichter_eingangsleistung",
    "house_w":           "sensor.hausverbrauch_live",
    "grid_feed_w":       "sensor.emma_einspeiseleistung",
    "grid_active_w":     "sensor.emma_wirkleistung",
    "battery_soc":       "sensor.batterien_batterieladung",
    "battery_power_w":   "sensor.batterien_lade_entladeleistung",   # +charge / -discharge
    "battery_cap_wh":    "sensor.batterien_akkukapazitat",
    "battery_bus_v":     "sensor.batterien_busspannung",
    "battery_bus_a":     "sensor.batterien_busstrom",
    "battery_max_chg_w": "sensor.batterien_maximale_ladeleistung",
    "battery_max_dis_w": "sensor.batterien_maximale_entladeleistung",
    "battery_restzeit":  "sensor.batterie_restzeit",
    "efficiency":        "sensor.wechselrichter_effizienz",
    "peak_today_w":      "sensor.wechselrichter_tages_wirkleistungsspitze",
}
_SOLAR_TEXT = {
    "battery_status":    "sensor.batterien_status",
    "battery_hint":      "sensor.batterie_status",            # friendly emoji sentence
    "inverter_status":   "sensor.wechselrichter_wechselrichterstatus",
    "grid_status":       "sensor.wechselrichter_netztrennung_status",
    "device_status":     "sensor.wechselrichter_geratestatus",
    "pv_link":           "sensor.wechselrichter_pv_verbindungsstatus",
    "alarms":            "sensor.wechselrichter_alarme",
    "start_time":        "sensor.wechselrichter_startzeit",
}
_SOLAR_DAILY = {
    "pv_kwh":         "sensor.emma_pv_ertrag_heute",
    "consume_kwh":    "sensor.emma_verbrauch_heute",
    "feed_kwh":       "sensor.emma_einspeisung_heute",
    "grid_kwh":       "sensor.emma_netzbezug_heute",
    "charge_kwh":     "sensor.emma_heute_geladene_energie",
    "discharge_kwh":  "sensor.emma_heutige_entladene_energie",
    "inverter_kwh":   "sensor.emma_heutiger_wechselrichterertrag",
}
_SOLAR_LIFE = {
    "pv_kwh":         "sensor.emma_gesamte_pv_ertragsleistung",
    "inverter_kwh":   "sensor.wechselrichter_gesamtenergieertrag",
    "feed_kwh":       "sensor.emma_gesamte_einspeisung_ins_netz",
    "grid_kwh":       "sensor.emma_gesamter_netzbezug",
    "charge_kwh":     "sensor.batterien_gesamtladung",
    "discharge_kwh":  "sensor.batterien_gesamtentladung",
}
_SOLAR_STRINGS = [
    ("PV1", "sensor.wechselrichter_pv_1_spannung", "sensor.wechselrichter_pv_1_strom"),
    ("PV2", "sensor.wechselrichter_pv_2_spannung", "sensor.wechselrichter_pv_2_strom"),
]


def _num(snap, eid):
    e = snap.get(eid)
    return e.get("num") if e else None


def _txt(snap, eid):
    e = snap.get(eid)
    if not e:
        return None
    s = e.get("state")
    return None if s in ("unknown", "unavailable", "None", None) else s


def solar(snap):
    """Huawei PV structured view, or None if this house has no solar."""
    if "sensor.hausverbrauch_live" not in snap and "sensor.emma_wirkleistung" not in snap:
        return None
    now = {k: _num(snap, eid) for k, eid in _SOLAR_NOW.items()}
    txt = {k: _txt(snap, eid) for k, eid in _SOLAR_TEXT.items()}
    daily = {k: _num(snap, eid) for k, eid in _SOLAR_DAILY.items()}
    life = {k: _num(snap, eid) for k, eid in _SOLAR_LIFE.items()}
    strings = []
    for name, v_eid, a_eid in _SOLAR_STRINGS:
        v, a = _num(snap, v_eid), _num(snap, a_eid)
        if v is None and a is None:
            continue
        strings.append({"name": name, "voltage_v": v, "current_a": a,
                        "power_w": round(v * a, 1) if (v is not None and a is not None) else None})
    # self-sufficiency today = (consume - grid_import) / consume
    autarky = None
    if daily.get("consume_kwh"):
        gi = daily.get("grid_kwh") or 0
        autarky = round(max(0.0, (daily["consume_kwh"] - gi) / daily["consume_kwh"]) * 100, 1)
    # entity map so the drill-down can chart any field
    ent = {}
    for grp in (_SOLAR_NOW, _SOLAR_DAILY, _SOLAR_LIFE):
        ent.update(grp)
    return {"now": now, "text": txt, "daily": daily, "lifetime": life,
            "strings": strings, "autarky_today_pct": autarky, "entity_map": ent}


# ── climate / environment by room ───────────────────────────────────────────
# names that mark a *device* temperature (CPU/battery/heating flow/…), not room air
_DEV_TEMP = ("cpu", "nvme", "gpu", "core", "prozessor", "festplatte", "ssd", "hdd",
             "akku", "batter", "vorlauf", "rucklauf", "ruecklauf", "kompressor",
             "abluft", "zuluft", "wasser", "water", "pool", "kessel", "kuhl", "kuehl",
             "motor", "drive", "chip", "board", "modul", "wechselrichter", "emma")


def _is_ambient(eid, num):
    low = eid.lower()
    if any(m in low for m in _DEV_TEMP):
        return False
    if not isinstance(num, (int, float)):
        return False
    return -20 <= num <= 45           # plausible indoor/outdoor air


def climate(snap):
    """Room comfort: thermostats + ambient air temp/humidity, per room only.

    Device temperatures (CPU, battery, heating flow) are excluded from the room
    view — they live in the explorer and their own panels — so room averages
    stay meaningful.
    """
    rooms = {}
    for eid, e in snap.items():
        area = e.get("area")
        if not area:                  # room view = rooms only
            continue
        dom = eid.split(".", 1)[0]
        dc = e.get("device_class")
        if dom == "climate":
            rooms.setdefault(area, {"climate": [], "temp": [], "humid": []})
            rooms[area]["climate"].append({
                "entity_id": eid, "name": e.get("name"), "state": e.get("state"),
                "current": (e.get("attrs") or {}).get("current_temperature"),
                "target": (e.get("attrs") or {}).get("temperature"),
            })
        elif dc == "temperature" and dom == "sensor" and _is_ambient(eid, e.get("num")):
            rooms.setdefault(area, {"climate": [], "temp": [], "humid": []})
            rooms[area]["temp"].append({"entity_id": eid, "name": e.get("name"),
                                        "num": e.get("num"), "unit": e.get("unit")})
        elif dc == "humidity" and dom == "sensor" and isinstance(e.get("num"), (int, float)):
            rooms.setdefault(area, {"climate": [], "temp": [], "humid": []})
            rooms[area]["humid"].append({"entity_id": eid, "name": e.get("name"),
                                         "num": e.get("num"), "unit": e.get("unit")})
    out = []
    for area, d in rooms.items():
        temps = [t["num"] for t in d["temp"] if isinstance(t["num"], (int, float))]
        hums = [h["num"] for h in d["humid"] if isinstance(h["num"], (int, float))]
        if not (temps or hums or d["climate"]):
            continue
        out.append({
            "area": area,
            "climate": d["climate"], "temp": d["temp"], "humid": d["humid"],
            "temp_avg": round(sum(temps) / len(temps), 1) if temps else None,
            "humid_avg": round(sum(hums) / len(hums), 1) if hums else None,
            "n": len(d["climate"]) + len(d["temp"]) + len(d["humid"]),
        })
    out.sort(key=lambda r: (r["temp_avg"] is None, -r["n"]))
    return out if out else None


# ── exhaustive sensor explorer (every entity) ───────────────────────────────
# semantic buckets for entities without a room (area is None)
_SEMANTIC = [
    ("☀️ Solar & Speicher", ("emma_", "batterie", "batterien_", "wechselrichter_",
                             "hausverbrauch", "eigenverbrauch", "fusion_solar", "huawei_solar",
                             "poolpumpe_energie", "pv_")),
    ("🌐 Netzwerk & Internet", ("unifi", "udm_", "udm_pro", "devtraffic", "flow_", "flowcol",
                               "net_", "_wan", "wan_", "download", "upload", "_rx", "_tx",
                               "ping", "speedtest", "nextdns", "traffic")),
    ("🔋 Batterien", ("_batterie", "_battery", "battery_level", "batteriespannung")),
    ("🖥️ System & Server", ("rpi_", "_docker_", "cpu_", "memory", "speicher_", "disk",
                            "uptime", "supervisor", "backup", "load_", "swap", "nvme",
                            "sd_wear", "processor", "last_boot")),
    ("📍 Präsenz & Personen", ("device_tracker.", "person.", "_home", "anwesen", "presence",
                              "geocoded")),
    ("🚪 Fenster & Türen", ("fenster", "tur_", "_tur", "tuer", "door", "window", "kontakt")),
    ("🏃 Bewegung", ("bewegung", "motion", "occupancy", "pir_")),
]


def _bucket(eid, dclass):
    low = eid.lower()
    for label, needles in _SEMANTIC:
        for n in needles:
            if n in low:
                return label
    if dclass == "battery":
        return "🔋 Batterien"
    if dclass in ("temperature", "humidity"):
        return "🌡️ Klima"
    if dclass in ("power", "energy", "current", "voltage", "monetary"):
        return "⚡ Energie & Leistung"
    dom = eid.split(".", 1)[0]
    return {
        "automation": "🤖 Automationen", "script": "🤖 Automationen",
        "switch": "🔌 Schalter & Steckdosen", "light": "💡 Licht",
        "binary_sensor": "🔔 Binär-Sensoren", "update": "⬆️ Updates",
        "button": "🔘 Buttons", "number": "🎚️ Regler", "select": "🎛️ Auswahl",
        "input_number": "🎚️ Regler", "input_boolean": "🎚️ Helfer",
        "input_text": "🎚️ Helfer", "input_datetime": "🎚️ Helfer",
        "media_player": "🔊 Medien", "scene": "🎬 Szenen", "cover": "🪟 Rollos",
        "calendar": "📅 Kalender", "todo": "📝 Listen", "event": "⚡ Events",
        "remote": "📱 Fernbedienung", "vacuum": "🧹 Staubsauger",
    }.get(dom, "📦 Sonstiges")


def explorer(snap):
    """Group EVERY entity: by room when known, else by semantic bucket."""
    groups = {}
    for eid, e in snap.items():
        dom = eid.split(".", 1)[0]
        area = e.get("area")
        grp = area if area else _bucket(eid, e.get("device_class"))
        g = groups.setdefault(grp, {"name": grp, "is_room": bool(area), "items": []})
        g["items"].append({
            "entity_id": eid, "domain": dom, "name": e.get("name"),
            "state": e.get("state"), "num": e.get("num"), "unit": e.get("unit"),
            "device_class": e.get("device_class"), "icon": e.get("icon"),
        })
    out = []
    for grp, g in groups.items():
        g["items"].sort(key=lambda x: (x["domain"], x["name"] or x["entity_id"]))
        g["n"] = len(g["items"])
        out.append(g)
    # rooms first (by size), then semantic buckets (by size)
    out.sort(key=lambda g: (not g["is_room"], -g["n"]))
    return {"groups": out, "total": sum(g["n"] for g in out), "n_groups": len(out)}


def summary(snap):
    """Small counts block for the main /api/state (cheap)."""
    by_domain = {}
    n_num = 0
    for eid, e in snap.items():
        dom = eid.split(".", 1)[0]
        by_domain[dom] = by_domain.get(dom, 0) + 1
        if e.get("num") is not None:
            n_num += 1
    return {"total": len(snap), "numeric": n_num,
            "sensors": by_domain.get("sensor", 0),
            "by_domain": by_domain}
