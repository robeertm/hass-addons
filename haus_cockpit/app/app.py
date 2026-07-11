"""haus-cockpit — Flask entrypoint.

Read-only ops board for Robert's + Mike's home infrastructure. Background
workers keep everything live:
  • MqttIngest    — the resilience health feeds (service registry, Pi/UDM/BLE).
  • HASource(s)   — read-only /api/states poll of each house's Home Assistant
                    (all sensors, Huawei solar, climate). Robert local + Mike
                    over WireGuard; on Mike's own instance just the local one.
  • SecuritySource(s) — flow-collector (IPFIX/GeoIP) + NextDNS + UniFi.
  • HistoryStore  — time-series for the charts, backfilled from HA recorders.

The browser polls /api/state (lean), /api/sensors (exhaustive explorer) and
/api/security (internet/GeoIP detail) and animates the rest. Nothing actuates.
"""
from flask import Flask, jsonify, render_template, request

import config
from services.mqtt_ingest import MqttIngest
from services import registry
from services.history import HistoryStore
from services.ha_source import HASource
from services.security import SecuritySource

app = Flask(__name__)

# ── MQTT resilience feeds ───────────────────────────────────────────────────
ingest = MqttIngest(
    config.MQTT_HOST, config.MQTT_PORT,
    config.MQTT_USER, config.MQTT_PASS, config.MQTT_CLIENT_ID,
)
ingest.start()

# ── HA sources (read-only) + Security sources, one per house ────────────────
ha_sources = {}
sec_sources = {}
for h in config.HOUSES:
    src = HASource(h["key"], h.get("ha_url"), h.get("ha_token"), poll_sec=config.HA_POLL_SEC)
    src.start()
    ha_sources[h["key"]] = src
    sec = SecuritySource(h["key"], flowcol_url=h.get("flowcol_url"),
                         nextdns_key=h.get("nextdns_key"),
                         nextdns_profile=h.get("nextdns_profile"))
    sec.start()
    sec_sources[h["key"]] = sec


def _build(include_docker=True):
    return registry.build_state(ingest, ha_sources, sec_sources, include_docker=include_docker)


# ── history sampler ─────────────────────────────────────────────────────────
history = HistoryStore()
history.start(lambda: _build(include_docker=False), ha_sources=ha_sources)


@app.route("/")
def index():
    return render_template("cockpit.html", refresh_sec=config.REFRESH_SEC,
                           profile=config.PROFILE)


@app.route("/api/state")
def api_state():
    return jsonify(_build())


@app.route("/api/sensors")
def api_sensors():
    house = request.args.get("house", config.HOUSES[0]["key"])
    return jsonify({"house": house, "generated_at": __import__("time").time(),
                    **registry.sensors_detail(ha_sources, house)})


@app.route("/api/security")
def api_security():
    house = request.args.get("house", config.HOUSES[0]["key"])
    return jsonify({"house": house, "generated_at": __import__("time").time(),
                    "security": registry.security_detail(sec_sources, ha_sources, house)})


@app.route("/api/history")
def api_history():
    house = request.args.get("house", config.HOUSES[0]["key"])
    keys = request.args.get("keys")
    keys = set(keys.split(",")) if keys else None
    return jsonify({
        "house": house,
        "sample_sec": config.HIST_SAMPLE_SEC,
        "generated_at": __import__("time").time(),
        "series": history.series(house, keys),
    })


@app.route("/healthz")
def healthz():
    info = ingest.conn_info()
    code = 200 if info["connected"] else 503
    return jsonify({"ok": info["connected"], **info,
                    "profile": config.PROFILE,
                    "ha": {k: s.info() for k, s in ha_sources.items()},
                    "history": history.stats()}), code


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT)
