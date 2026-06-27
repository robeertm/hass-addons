import os
from datetime import datetime, timezone

from config import ENTITIES


def _build_solar(snapshot):
    s = ENTITIES.get("solar")
    if not s:
        return None
    out = {}
    for k, eid in s.items():
        out[k] = _safe_float(_state(snapshot, eid), None)
    out["history"] = snapshot.get("histories", {}).get(s.get("pv_power", ""), [])
    out["house_load_history"] = snapshot.get("histories", {}).get(s.get("house_load_w", ""), [])
    out["battery_history"] = snapshot.get("histories", {}).get(s.get("battery_soc", ""), [])
    out["battery_power_history"] = snapshot.get("histories", {}).get(s.get("battery_power", ""), [])
    return out


def _build_pool(snapshot):
    p = ENTITIES.get("pool")
    if not p:
        return None
    out = {
        "wassertemp": _safe_float(_state(snapshot, p.get("wassertemp", "")), None),
        "ph": _safe_float(_state(snapshot, p.get("ph", "")), None),
        "orp": _safe_float(_state(snapshot, p.get("orp", "")), None),
        "filtration_h": _safe_float(_state(snapshot, p.get("filtration_h", "")), None),
        "pumpe_on": _state(snapshot, p.get("pumpe", "")) == "on",
        "laufzeit_h": _safe_float(_state(snapshot, p.get("laufzeit_h", "")), None),
        "soll_h": _safe_float(_state(snapshot, p.get("soll_h", "")), None),
        "manuell_aus": _state(snapshot, p.get("manuell_aus", "")) == "on",
        "status": _state(snapshot, p.get("status", "")),
        "messung_gultig": _state(snapshot, p.get("messung_gultig", "")) == "on",
        "aktion_log": _state(snapshot, p.get("aktion_log", "")),
        "wassertemp_history": snapshot.get("histories", {}).get(p.get("wassertemp", ""), []),
        "ph_history": snapshot.get("histories", {}).get(p.get("ph", ""), []),
        "orp_history": snapshot.get("histories", {}).get(p.get("orp", ""), []),
    }
    return out


def _build_miele(snapshot):
    m = ENTITIES.get("miele")
    if not m:
        return None
    return {
        "wm_phase": _state(snapshot, m.get("wm_phase", "")),
        "wt_phase": _state(snapshot, m.get("wt_phase", "")),
        "wm_finished": _state(snapshot, m.get("wm_finished", "")),
        "wt_finished": _state(snapshot, m.get("wt_finished", "")),
    }


def _build_vacuum(snapshot):
    v = ENTITIES.get("vacuum")
    if not v:
        return None
    return {
        "state": _state(snapshot, v.get("state", "")),
        "status": _state(snapshot, v.get("status", "")),
    }


WEATHER_DE = {
    "sunny": ("☀️", "Sonnig"),
    "clear-night": ("🌙", "Klar"),
    "partlycloudy": ("⛅", "Teils bewölkt"),
    "cloudy": ("☁️", "Bewölkt"),
    "rainy": ("🌧️", "Regen"),
    "pouring": ("🌧️", "Starkregen"),
    "lightning": ("⛈️", "Gewitter"),
    "lightning-rainy": ("⛈️", "Gewitter"),
    "snowy": ("🌨️", "Schnee"),
    "snowy-rainy": ("🌨️", "Schneeregen"),
    "fog": ("🌫️", "Nebel"),
    "windy": ("💨", "Windig"),
    "windy-variant": ("💨", "Windig"),
    "hail": ("🌨️", "Hagel"),
    "exceptional": ("⚠️", "Außergewöhnlich"),
}

GARBAGE_META = {
    "Gelb": {"icon": "🟡", "color": "#f9e2af"},
    "Restmüll": {"icon": "⚫", "color": "#6c7086"},
    "Bio": {"icon": "🟢", "color": "#a6e3a1"},
    "Papier": {"icon": "🔵", "color": "#89b4fa"},
}


def _state(snapshot, eid):
    s = snapshot["states"].get(eid)
    return s.get("state") if s else None


def _attr(snapshot, eid, attr):
    s = snapshot["states"].get(eid)
    if not s:
        return None
    return s.get("attributes", {}).get(attr)


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _parse_iso(s):
    if not s or s in ("unknown", "unavailable"):
        return None
    try:
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        if " " in s:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def transform(snapshot):
    now = datetime.now().astimezone()

    weather_state = _state(snapshot, ENTITIES["weather"])
    weather_icon, weather_label = WEATHER_DE.get(weather_state or "", ("☁️", weather_state or "—"))

    sun_rise = _parse_iso(_state(snapshot, ENTITIES["sun_rising"]))
    sun_set = _parse_iso(_state(snapshot, ENTITIES["sun_setting"]))
    is_night = bool(sun_set and sun_rise and now > sun_set.astimezone())

    persons = []
    for name, eid in ENTITIES["persons"]:
        state = _state(snapshot, eid)
        persons.append({
            "name": name,
            "home": state == "home",
            "state": state or "unknown",
        })

    windows_open = []
    windows_closed = []
    for name, eid in ENTITIES["windows"]:
        state = _state(snapshot, eid)
        target = windows_open if state == "on" else windows_closed
        target.append(name)

    rooms = []
    for entry in ENTITIES.get("rooms", []):
        name = entry[0]
        temp_eid = entry[1]
        soll_eid = entry[2]
        climate_eid = entry[3] if len(entry) > 3 else None
        ventil_eid = entry[4] if len(entry) > 4 else None
        t = _safe_float(_state(snapshot, temp_eid), None)
        soll = _safe_float(_state(snapshot, soll_eid), None)
        trv_state = _state(snapshot, climate_eid) if climate_eid else None
        trv_target = _safe_float(_attr(snapshot, climate_eid, "temperature"), None) if climate_eid else None
        ventil = _safe_float(_state(snapshot, ventil_eid), None) if ventil_eid else None
        rooms.append({
            "name": name,
            "temp": t,
            "soll": soll,
            "trv_state": trv_state,
            "trv_target": trv_target,
            "ventil": ventil,
            "heating": (ventil is not None and ventil > 0) or trv_state == "heat" and (ventil is None or ventil > 0),
        })

    garbage = []
    GARBAGE_KEYWORDS = ["restmüll", "restmuell", "papier", "bio", "gelb", "wertstoff", "abfall", "tonne"]
    seen_garbage_keys = set()

    def _label_for_calendar(summary):
        ll = (summary or "").lower()
        if "restm" in ll: return "Restmüll"
        if "papier" in ll: return "Papier"
        if "bio" in ll: return "Bio"
        if "gelb" in ll or "wertstoff" in ll: return "Gelb"
        return summary or "Abfall"

    for e in snapshot.get("calendar_events", []) or []:
        summary = (e.get("summary") or "").lower()
        if not any(k in summary for k in GARBAGE_KEYWORDS):
            continue
        cal = e.get("_calendar", "") or ""
        if "abfall" not in cal.lower() and "mull" not in cal.lower() and "zaoe" not in cal.lower() and "bautzen" not in cal.lower():
            continue
        start_raw = e.get("start", {})
        s_str = start_raw.get("dateTime") or start_raw.get("date") if isinstance(start_raw, dict) else start_raw
        d = _parse_iso(s_str)
        if not d:
            continue
        label = _label_for_calendar(e.get("summary"))
        meta = GARBAGE_META.get(label, {"icon": "⚪", "color": "#cdd6f4"})
        d_local = d.astimezone()
        today_local = now.replace(hour=0, minute=0, second=0, microsecond=0)
        d_floor = d_local.replace(hour=0, minute=0, second=0, microsecond=0)
        days = (d_floor - today_local).days
        key = (label, d_floor.isoformat())
        if key in seen_garbage_keys:
            continue
        seen_garbage_keys.add(key)
        garbage.append({
            "label": label,
            "icon": meta["icon"],
            "color": meta["color"],
            "date": d_local.isoformat(),
            "days": days,
        })

    # Source 1: explicit input_text/input_datetime helpers (Robert pattern)
    for label_eid, date_eid in ENTITIES.get("garbage", []) or []:
        label = _state(snapshot, label_eid)
        date_str = _state(snapshot, date_eid)
        d = _parse_iso(date_str)
        if d and label:
            d_local = d.astimezone()
            today_local = now.replace(hour=0, minute=0, second=0, microsecond=0)
            d_floor = d_local.replace(hour=0, minute=0, second=0, microsecond=0)
            days = (d_floor - today_local).days
            meta = GARBAGE_META.get(label, {"icon": "⚪", "color": "#cdd6f4"})
            garbage.append({
                "label": label,
                "icon": meta["icon"],
                "color": meta["color"],
                "date": d_local.isoformat(),
                "days": days,
            })
    garbage.sort(key=lambda g: g["date"])

    vacation = None
    v_start = _parse_iso(_state(snapshot, ENTITIES.get("vacation_start", "")))
    v_end = _parse_iso(_state(snapshot, ENTITIES.get("vacation_end", "")))
    v_label = _state(snapshot, ENTITIES.get("vacation_label", ""))
    if v_start and v_end:
        v_start_local = v_start.astimezone()
        v_end_local = v_end.astimezone()
        today_local = now.replace(hour=0, minute=0, second=0, microsecond=0)
        v_start_floor = v_start_local.replace(hour=0, minute=0, second=0, microsecond=0)
        days_until = (v_start_floor - today_local).days
        duration = (v_end_local - v_start_local).days
        vacation = {
            "label": v_label or "Urlaub",
            "start": v_start_local.isoformat(),
            "end": v_end_local.isoformat(),
            "days_until": days_until,
            "duration": duration,
            "active": days_until <= 0 and v_end_local > now,
        }

    forecast = []
    for f in snapshot.get("forecast", []):
        cond = f.get("condition") or f.get("state")
        icon, label = WEATHER_DE.get(cond or "", ("☁️", cond or "—"))
        forecast.append({
            "date": f.get("datetime"),
            "icon": icon,
            "label": label,
            "raw": cond,
            "high": f.get("temperature"),
            "low": f.get("templow"),
            "precip": f.get("precipitation"),
        })

    indoor = {
        "humidity": _safe_float(_state(snapshot, ENTITIES.get("indoor_humidity", "")), None),
        "pressure": _safe_float(_state(snapshot, ENTITIES.get("pressure", "")), None),
        "grid_co2": _safe_float(_state(snapshot, ENTITIES.get("grid_co2", "")), None),
        "co2": _safe_float(_state(snapshot, ENTITIES.get("indoor_co2", "")), None),
        "noise": _safe_float(_state(snapshot, ENTITIES.get("indoor_noise", "")), None),
    }

    weather_extra = {
        "outdoor_humidity": _safe_float(_state(snapshot, ENTITIES.get("outdoor_humidity", "")), None),
        "wind_speed": _safe_float(_state(snapshot, ENTITIES.get("wind_speed", "")), None),
        "wind_dir": _state(snapshot, ENTITIES.get("wind_dir", "")),
        "rain_now": _safe_float(_state(snapshot, ENTITIES.get("rain_now", "")), None),
        "rain_today": _safe_float(_state(snapshot, ENTITIES.get("rain_today", "")), None),
    }

    events = []
    for e in snapshot.get("calendar_events", []):
        start_raw = e.get("start", {})
        end_raw = e.get("end", {})
        if isinstance(start_raw, dict):
            start_str = start_raw.get("dateTime") or start_raw.get("date")
            end_str = end_raw.get("dateTime") or end_raw.get("date")
        else:
            start_str = start_raw
            end_str = end_raw
        sd = _parse_iso(start_str)
        if not sd:
            continue
        ed = _parse_iso(end_str) if end_str else None
        sd_local = sd.astimezone()
        ed_local = ed.astimezone() if ed else None
        all_day = bool(start_raw and isinstance(start_raw, dict) and start_raw.get("date") and not start_raw.get("dateTime"))
        cal = e.get("_calendar", "")
        events.append({
            "summary": e.get("summary") or "",
            "start": sd_local.isoformat(),
            "end": ed_local.isoformat() if ed_local else None,
            "all_day": all_day,
            "calendar": cal.replace("calendar.", ""),
        })
    events.sort(key=lambda x: x["start"])

    energy_subs = []
    for label, power_eid, energy_eid, cost_eid in ENTITIES.get("energy_subs", []):
        energy_subs.append({
            "label": label,
            "power_w": _safe_float(_state(snapshot, power_eid)),
            "energy_kwh": _safe_float(_state(snapshot, energy_eid)),
            "cost_eur": _safe_float(_state(snapshot, cost_eid)),
            "history": snapshot.get("histories", {}).get(power_eid, []),
        })

    batteries = []
    for label, eid, kind in ENTITIES.get("batteries", []):
        v = _safe_float(_state(snapshot, eid), None)
        if v is None:
            continue
        if v >= 70:
            level = "good"
        elif v >= 30:
            level = "mid"
        else:
            level = "low"
        batteries.append({
            "label": label,
            "value": v,
            "kind": kind,
            "level": level,
        })
    batteries.sort(key=lambda b: b["value"])

    histories = snapshot.get("histories", {})
    outdoor_history = histories.get(ENTITIES.get("outdoor_temp", ""), []) or histories.get("sensor.aussentemperatur", [])
    rooms_history = {}
    for room in rooms:
        eid_key = None
        for ent_room in ENTITIES["rooms"]:
            if ent_room[0] == room["name"]:
                eid_key = ent_room[1]
                break
        if eid_key:
            rooms_history[room["name"]] = histories.get(eid_key, [])

    sun_elevation = _safe_float(_attr(snapshot, ENTITIES.get("sun_elevation_attr", "sun.sun"), "elevation"), None)
    sun_azimuth = _safe_float(_attr(snapshot, ENTITIES.get("sun_elevation_attr", "sun.sun"), "azimuth"), None)

    co2_kumuliert = _safe_float(_state(snapshot, ENTITIES.get("co2_kumuliert", "")), None)
    co2_rate = _safe_float(_state(snapshot, ENTITIES.get("co2_rate", "")), None)

    backup_last = _parse_iso(_state(snapshot, ENTITIES.get("backup_last", "")))
    backup_next = _parse_iso(_state(snapshot, ENTITIES.get("backup_next", "")))

    thread_rssi = {
        "best": _safe_float(_state(snapshot, ENTITIES.get("thread_rssi_best", "")), None),
        "avg": _safe_float(_state(snapshot, ENTITIES.get("thread_rssi_avg", "")), None),
        "worst": _safe_float(_state(snapshot, ENTITIES.get("thread_rssi_worst", "")), None),
    }

    internet_down = _safe_float(_state(snapshot, ENTITIES.get("internet_download", "")), None)
    internet_up = _safe_float(_state(snapshot, ENTITIES.get("internet_upload", "")), None)
    internet_down_history = snapshot.get("histories", {}).get(ENTITIES.get("internet_download", ""), [])
    internet_up_history = snapshot.get("histories", {}).get(ENTITIES.get("internet_upload", ""), [])

    clients_map = {}
    prefix = ENTITIES.get("internet_clients_prefix", "sensor.net_")
    for eid, st in snapshot["states"].items():
        if not eid.startswith(prefix) or not st:
            continue
        rest = eid[len(prefix):]
        if rest.endswith("_down"):
            name = rest[:-5]
            try:
                v = float(st.get("state"))
            except (TypeError, ValueError):
                continue
            clients_map.setdefault(name, {})["down"] = v
        elif rest.endswith("_up"):
            name = rest[:-3]
            try:
                v = float(st.get("state"))
            except (TypeError, ValueError):
                continue
            clients_map.setdefault(name, {})["up"] = v

    NAME_FIX = {
        "ev_mike": "EV Mike", "ev_robert": "EV Robert", "ev_dirk": "EV Dirk",
        "macbookpro_robert": "MacBook Robert", "iphone15promax_robert": "iPhone Robert",
        "iphone15promax_oskar": "iPhone Oskar", "iphone15promax_steffi": "iPhone Steffi",
        "pc_oskar": "PC Oskar", "ipad_robert": "iPad Robert",
        "alexa_schlafzimmer": "Alexa SZ", "alexa_kueche": "Alexa Küche",
        "homepod_kueche": "HomePod Küche", "homepod_oskar": "HomePod Oskar",
        "phillips_tv": "Philips TV", "philips_tv": "Philips TV",
        "maro_datacenter": "Maro NAS", "synology_server": "Synology",
        "shelly_energy_analyzer_vm": "Shelly Pi", "pironman5_lan": "HA Pi (LAN)",
        "umbrel": "Umbrel", "miele_trockner": "Trockner", "miele_waschmaschine": "Waschmaschine",
    }
    clients_list = []
    for name, kv in clients_map.items():
        down = kv.get("down", 0)
        up = kv.get("up", 0)
        if down + up < 0.001:
            continue
        clients_list.append({
            "name": NAME_FIX.get(name, name.replace("_", " ").title()),
            "down": down,
            "up": up,
            "total": down + up,
        })
    clients_list.sort(key=lambda c: -c["total"])
    clients_top = clients_list[:8]

    return {
        "now": now.isoformat(),
        "energy_subs": energy_subs,
        "batteries": batteries,
        "outdoor_history": outdoor_history,
        "rooms_history": rooms_history,
        "sun_elevation": sun_elevation,
        "sun_azimuth": sun_azimuth,
        "co2_kumuliert": co2_kumuliert,
        "co2_rate": co2_rate,
        "backup_last": backup_last.astimezone().isoformat() if backup_last else None,
        "backup_next": backup_next.astimezone().isoformat() if backup_next else None,
        "thread_rssi": thread_rssi,
        "internet": {
            "down_mbit": internet_down,
            "up_mbit": internet_up,
            "down_history": internet_down_history,
            "up_history": internet_up_history,
            "clients": clients_top,
        },
        "solar": _build_solar(snapshot),
        "pool": _build_pool(snapshot),
        "miele": _build_miele(snapshot),
        "vacuum": _build_vacuum(snapshot),
        "profile": os.environ.get('TV_PROFILE', 'mike').lower(),
        "outdoor": {
            "temp": _safe_float(_state(snapshot, ENTITIES["outdoor_temp"])),
            "icon": weather_icon,
            "label": weather_label,
            "raw": weather_state,
            "is_night": is_night,
            "sun_rise": sun_rise.astimezone().isoformat() if sun_rise else None,
            "sun_set": sun_set.astimezone().isoformat() if sun_set else None,
            **weather_extra,
        },
        "forecast": forecast,
        "persons": persons,
        "windows": {
            "open": windows_open,
            "closed": windows_closed,
            "count_open": len(windows_open),
            "count_total": len(ENTITIES["windows"]),
        },
        "power": {
            "now_w": _safe_float(_state(snapshot, ENTITIES["power_now"])),
            "today_kwh": _safe_float(_state(snapshot, ENTITIES["energy_today"])),
            "today_eur": _safe_float(_state(snapshot, ENTITIES["cost_today"])),
            "history": snapshot.get("power_history", []),
        },
        "rooms": rooms,
        "garbage": garbage,
        "vacation": vacation,
        "indoor": indoor,
        "events": events,
        "last_fetch": snapshot.get("last_fetch"),
    }
