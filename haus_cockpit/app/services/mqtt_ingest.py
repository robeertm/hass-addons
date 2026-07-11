"""MQTT ingest — a resilient read-only subscriber that keeps an in-memory
snapshot of every health feed, with per-topic broker-receive timestamps so the
registry can judge freshness.

Resilience (mirrors the haus-resilience pattern, subscriber-flavoured):
  * connect_async + loop_start  → survives the broker being down at boot
  * (re)subscribe inside on_connect → a broker restart re-arms all topics
  * reconnect_delay_set          → capped backoff, retries forever
The container's restart:unless-stopped policy is the systemd-equivalent layer.
"""
import json
import threading
import time

try:
    import paho.mqtt.client as mqtt
    _V2 = hasattr(mqtt, "CallbackAPIVersion")
except Exception:  # pragma: no cover
    mqtt = None
    _V2 = False

# Topics we care about. `#` under each root keeps us future-proof (new shelly
# devices / new houses appear automatically).
SUB_TOPICS = [
    ("flowcol/#", 0),
    ("rpi_health/#", 0),
    ("udm_health/#", 0),
    ("shelly_analyzer/#", 0),
    # Mike's native BLE-proxy root (used on Mike's own instance; harmless on
    # Robert's broker where it simply never publishes)
    ("mike_ble_source/#", 0),
    # room for the Mike bridge (Phase 2b) — mirrored under mike/*
    ("mike/#", 0),
]


class MqttIngest:
    def __init__(self, host, port, user, password, client_id):
        self.host, self.port = host, port
        self.user, self.password = user, password
        self.client_id = client_id
        self._lock = threading.Lock()
        # topic -> {"payload": str, "json": dict|None, "rx": epoch_seconds}
        self._store = {}
        self._connected = False
        self._connected_since = None
        self._reconnects = -1          # first connect counts as 0
        self._started_at = time.time()
        self._client = None

    # ── lifecycle ───────────────────────────────────────────────────────────
    def start(self):
        if mqtt is None:
            raise RuntimeError("paho-mqtt not installed")
        if _V2:
            c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id)
        else:
            c = mqtt.Client(client_id=self.client_id)
        if self.user:
            c.username_pw_set(self.user, self.password)
        c.reconnect_delay_set(min_delay=1, max_delay=30)
        c.on_connect = self._on_connect
        c.on_disconnect = self._on_disconnect
        c.on_message = self._on_message
        self._client = c
        c.connect_async(self.host, self.port, keepalive=45)
        c.loop_start()

    # ── callbacks ───────────────────────────────────────────────────────────
    def _on_connect(self, client, _ud, _flags, reason_code, _props=None):
        ok = (getattr(reason_code, "value", reason_code) == 0)
        if ok:
            self._connected = True
            self._connected_since = time.time()
            self._reconnects += 1
            for t, q in SUB_TOPICS:
                client.subscribe(t, q)

    def _on_disconnect(self, *_a, **_k):
        self._connected = False

    def _on_message(self, _client, _ud, msg):
        now = time.time()
        try:
            payload = msg.payload.decode("utf-8", "replace")
        except Exception:
            payload = ""
        parsed = None
        p = payload.strip()
        if p[:1] in "{[":
            try:
                parsed = json.loads(p)
            except Exception:
                parsed = None
        with self._lock:
            self._store[msg.topic] = {"payload": payload, "json": parsed, "rx": now}

    # ── access ──────────────────────────────────────────────────────────────
    def get(self, topic):
        with self._lock:
            e = self._store.get(topic)
            return dict(e) if e else None

    def match(self, prefix):
        """All entries whose topic starts with `prefix`. Returns {topic: entry}."""
        with self._lock:
            return {t: dict(e) for t, e in self._store.items() if t.startswith(prefix)}

    def conn_info(self):
        with self._lock:
            return {
                "connected": self._connected,
                "connected_since": self._connected_since,
                "reconnects": max(self._reconnects, 0),
                "uptime_sec": time.time() - self._started_at,
                "topics_tracked": len(self._store),
            }
