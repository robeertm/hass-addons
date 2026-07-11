"""entity_history — on-demand per-entity history from the HA recorder.

`services/history.py` keeps a *curated* set of metrics in in-memory ring
buffers (sampled live + backfilled once). That is great for the dashboard's
fixed charts, but the cockpit also wants to show a history sparkline for *any*
sensor a user drills into — including ones that were never curated.

This module fills that gap: given a house and a list of entity_ids it fetches
their recent numeric history straight from that house's Home-Assistant recorder
(`/api/history/period`), on demand, with a short per-entity TTL cache so a burst
of UI requests collapses into one HTTP call.

It is strictly read-only (a single GET per refresh), stdlib-only (like
history.py), thread-safe, and fail-soft: any error yields an empty/partial
result instead of raising, so a wedged tunnel or expired token degrades the
sparkline to "no data" rather than crashing the request.
"""
import json
import threading
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta


def _num(v):
    """Parse a HA state string into a finite float, or None if non-numeric."""
    try:
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _epoch(ts):
    """ISO-8601 (with 'Z' or offset) -> epoch seconds, or None."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


class EntityHistory:
    """On-demand numeric history fetcher for arbitrary HA entities.

    source_resolver(house) -> (url, token) or (None, None) if the house/HA is
    unknown or unconfigured. Wired to the app's HA sources by the caller.
    """

    def __init__(self, source_resolver, ttl_sec=60, timeout=15, cap=200):
        self.source_resolver = source_resolver
        self.ttl_sec = ttl_sec
        self.timeout = timeout
        self.cap = cap
        self._lock = threading.Lock()
        # (house, entity_id) -> (fetched_at_epoch, [[epoch, value], ...])
        self._cache = {}
        self._last_err = None
        self.http_calls = 0        # count of HA HTTP requests actually issued

    # ── public API ────────────────────────────────────────────────────────────
    def fetch(self, house, entity_ids, hours=6):
        """Return {entity_id: [[epoch_float, value_float], ...]} for numeric
        entities only. Cached entities (within ttl_sec) are served without a
        refetch; only stale/uncached ids hit HA, in a single batched call.
        Fail-soft: returns partial/empty on any error, never raises."""
        if not entity_ids:
            return {}

        now = time.time()
        # de-dupe while preserving order
        wanted, seen = [], set()
        for e in entity_ids:
            if e and e not in seen:
                seen.add(e)
                wanted.append(e)

        result = {}
        to_fetch = []
        with self._lock:
            for e in wanted:
                entry = self._cache.get((house, e, hours))   # key by range too
                if entry and (now - entry[0]) < self.ttl_sec:
                    result[e] = entry[1]
                else:
                    to_fetch.append(e)

        if not to_fetch:
            return result

        # resolve this house's HA endpoint
        try:
            url, token = self.source_resolver(house)
        except Exception as ex:
            self._last_err = f"resolver: {ex}"
            url, token = None, None
        if not url or not token:
            # can't reach HA — return whatever the cache already had (partial)
            return result

        fetched = self._fetch_from_ha(url.rstrip("/"), token, to_fetch, hours)
        if fetched is None:                       # hard error → keep cache, partial
            return result

        stamp = time.time()
        with self._lock:
            for e in to_fetch:
                pts = fetched.get(e, [])          # cache empties too (avoids refetch storms)
                self._cache[(house, e, hours)] = (stamp, pts)
                result[e] = pts
        return result

    def stats(self):
        with self._lock:
            return {
                "cached_series": len(self._cache),
                "http_calls": self.http_calls,
                "last_err": self._last_err,
            }

    # ── HA recorder call ──────────────────────────────────────────────────────
    def _fetch_from_ha(self, url, token, entity_ids, hours):
        """One batched GET /api/history/period for all entity_ids.
        Returns {entity_id: downsampled points} or None on hard error."""
        now = datetime.now(timezone.utc)
        start = (now - timedelta(hours=hours)).isoformat()
        csv = urllib.parse.quote(",".join(entity_ids), safe=",")
        # end_time is REQUIRED for windows > 24h: HA's /history/period defaults to
        # a single day from <start>, so without it a 7-day request returns only the
        # first 24h (an old slice) instead of start→now.
        end = urllib.parse.quote(now.isoformat(), safe="")
        api = (f"{url}/api/history/period/{start}"
               f"?filter_entity_id={csv}&end_time={end}&minimal_response&no_attributes")
        req = urllib.request.Request(api, headers={"Authorization": f"Bearer {token}"})
        try:
            with self._lock:
                self.http_calls += 1
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read())
        except Exception as ex:
            self._last_err = f"history: {ex}"
            return None

        out = {}
        if not isinstance(data, list):
            return out
        for series in data:
            # minimal_response: each series is a list; the first element carries
            # the full state incl. entity_id, later elements may be just
            # {"state","last_changed"}. entity_id persists across the series.
            if not series:
                continue
            ent = series[0].get("entity_id")
            if not ent:
                continue
            pts = []
            for p in series:
                val = _num(p.get("state"))
                if val is None:                   # skip unknown/unavailable/non-numeric
                    continue
                ep = _epoch(p.get("last_changed") or p.get("last_updated"))
                if ep is None:
                    continue
                pts.append([round(ep, 1), round(val, 3)])
            out[ent] = self._downsample(pts)
        return out

    def _downsample(self, pts, cap=None):
        """Uniformly thin a series to <= cap points for transport."""
        cap = cap or self.cap
        n = len(pts)
        if n <= cap:
            return pts
        step = n / cap
        return [pts[int(i * step)] for i in range(cap)]
