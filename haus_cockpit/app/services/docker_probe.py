"""Minimal read-only Docker probe over the unix socket — no docker SDK dep.

Returns the container list (name, state, status text, health, uptime) so the
cockpit can show the stack at a glance. Fails soft: if the socket is absent
(e.g. running outside the Pi) it returns an empty list, never raising.
"""
import http.client
import json
import socket
import time


class _UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, sock_path, timeout=3):
        super().__init__("localhost", timeout=timeout)
        self._sock_path = sock_path

    def connect(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect(self._sock_path)
        self.sock = s


def _get(sock_path, path):
    conn = _UnixHTTPConnection(sock_path)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        if resp.status != 200:
            return None
        return json.loads(body)
    finally:
        conn.close()


def containers(sock_path="/var/run/docker.sock"):
    """List running+recent containers as dashboard-ready dicts. Never raises."""
    try:
        raw = _get(sock_path, "/v1.41/containers/json?all=1")
    except Exception:
        return []
    if not raw:
        return []
    out = []
    now = time.time()
    for c in raw:
        name = (c.get("Names") or ["?"])[0].lstrip("/")
        state = c.get("State", "unknown")          # running / exited / ...
        status = c.get("Status", "")               # "Up 3 days (healthy)"
        created = c.get("Created", 0)
        health = None
        s = status.lower()
        if "healthy" in s:
            health = "healthy"
        elif "unhealthy" in s:
            health = "unhealthy"
        elif "starting" in s:
            health = "starting"
        out.append({
            "name": name,
            "state": state,
            "status": status,
            "health": health,
            "up": state == "running",
            "age_sec": max(0, now - created) if created else None,
            "image": c.get("Image", ""),
        })
    out.sort(key=lambda x: (not x["up"], x["name"]))
    return out
