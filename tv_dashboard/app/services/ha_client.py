import threading
import time
from datetime import datetime, timezone, timedelta
import requests

from config import HA_BASE_URL, HA_TOKEN, REFRESH_INTERVAL_SEC, ENTITIES


class HAClient:
    def __init__(self):
        self._lock = threading.Lock()
        self._states = {}
        self._weather_forecast = []
        self._power_history = []
        self._calendar_events = []
        self._histories = {}
        self._last_fetch = None
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {HA_TOKEN}",
            "Content-Type": "application/json",
        })

    def start_polling(self):
        t = threading.Thread(target=self._poll_loop, daemon=True)
        t.start()

    def _poll_loop(self):
        while True:
            try:
                self._fetch_all()
            except Exception as e:
                print(f"[HA] poll error: {e}", flush=True)
            time.sleep(REFRESH_INTERVAL_SEC)

    def _get(self, path):
        r = self._session.get(f"{HA_BASE_URL}{path}", timeout=10)
        r.raise_for_status()
        return r.json()

    def _post(self, path, body):
        r = self._session.post(f"{HA_BASE_URL}{path}", json=body, timeout=10)
        r.raise_for_status()
        return r.json()

    def _fetch_all(self):
        states = {}
        try:
            all_states = self._get("/api/states")
            states = {s["entity_id"]: s for s in all_states if s and "entity_id" in s}
        except Exception as e:
            print(f"[HA] bulk states error: {e}", flush=True)

        forecast = self._fetch_weather_forecast(ENTITIES["weather"])
        power = self._fetch_power_history()
        calendar_events = self._fetch_calendar_events()
        histories = self._fetch_histories_bulk(ENTITIES.get("history_entities", []))

        with self._lock:
            self._states = states
            self._weather_forecast = forecast
            self._power_history = power
            self._calendar_events = calendar_events
            self._histories = histories
            self._last_fetch = datetime.now(timezone.utc)

    def _collect_entity_ids(self):
        ids = set()
        for key, val in ENTITIES.items():
            if isinstance(val, str):
                ids.add(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, tuple):
                        for sub in item:
                            if isinstance(sub, str) and "." in sub:
                                ids.add(sub)
                    elif isinstance(item, str):
                        ids.add(item)
        return ids

    def _fetch_weather_forecast(self, weather_entity):
        try:
            body = {"entity_id": weather_entity, "type": "daily"}
            r = self._session.post(
                f"{HA_BASE_URL}/api/services/weather/get_forecasts?return_response",
                json=body, timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            response = data.get("service_response", {}).get(weather_entity, {})
            return response.get("forecast", [])[:5]
        except Exception as e:
            print(f"[HA] forecast error: {e}", flush=True)
            return []

    def _fetch_power_history(self):
        return self._fetch_history_for(ENTITIES["power_now"], target_points=120, hours_back=24, allow_zero=True, max_v=25000)

    def _fetch_history_for(self, entity_id, target_points=60, hours_back=24, allow_zero=True, max_v=None):
        try:
            now = datetime.now(timezone.utc)
            start = now - timedelta(hours=hours_back)
            url = (
                f"/api/history/period/{start.isoformat()}"
                f"?filter_entity_id={entity_id}"
                f"&minimal_response"
            )
            data = self._get(url)
            if not data:
                return []
            series = data[0] if data else []
            samples = []
            for row in series:
                try:
                    v = float(row["state"])
                    if v < 0 and not allow_zero:
                        continue
                    if max_v is not None and v > max_v:
                        continue
                    t = row["last_changed"]
                    samples.append({"t": t, "v": v})
                except (ValueError, KeyError, TypeError):
                    continue
            if len(samples) > target_points:
                bucket = max(1, len(samples) // target_points)
                aggregated = []
                for i in range(0, len(samples), bucket):
                    chunk = samples[i:i + bucket]
                    if not chunk:
                        continue
                    avg = sum(c["v"] for c in chunk) / len(chunk)
                    aggregated.append({"t": chunk[-1]["t"], "v": avg})
                samples = aggregated
            return samples
        except Exception as e:
            print(f"[HA] history {entity_id} error: {e}", flush=True)
            return []

    def _fetch_histories_bulk(self, entities, target_points=60, hours_back=24):
        out = {}
        for eid in entities:
            tp = 120 if "power" in eid.lower() else target_points
            mv = 25000 if "power" in eid.lower() else None
            out[eid] = self._fetch_history_for(eid, target_points=tp, hours_back=hours_back, max_v=mv)
        return out

    def _fetch_calendar_events(self):
        out = []
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
        for cal in ENTITIES.get("calendars", []):
            try:
                url = (
                    f"/api/calendars/{cal}"
                    f"?start={start.isoformat().replace('+00:00','Z')}"
                    f"&end={end.isoformat().replace('+00:00','Z')}"
                )
                events = self._get(url)
                for e in events or []:
                    e["_calendar"] = cal
                    out.append(e)
            except Exception as ex:
                print(f"[HA] calendar {cal} error: {ex}", flush=True)
        return out

    def snapshot(self):
        with self._lock:
            return {
                "states": dict(self._states),
                "forecast": list(self._weather_forecast),
                "power_history": list(self._power_history),
                "calendar_events": list(self._calendar_events),
                "histories": dict(self._histories),
                "last_fetch": self._last_fetch.isoformat() if self._last_fetch else None,
            }
