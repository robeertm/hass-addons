"""snmp_poll — read-only SNMPv3 per-port interface poller for the UniFi UDM-SE.

Each SnmpPoller polls one UDM's IF-MIB counters on a background thread and
caches a per-port throughput snapshot. On Robert's cockpit there are two: `rad`
(the Radeberg UDM at 10.30.1.1) and `kli` (Mike's Klipphausen UDM at 10.10.2.1,
reachable over the WireGuard tunnel). Both answer the same SNMPv3 user.

It is strictly read-only — it only ever issues SNMP GET / bulk-WALK requests via
the net-snmp CLI (snmpget / snmpbulkwalk). It never SETs anything, so Mike's
"niemals testschalten" stays intact.

An unreachable UDM (WireGuard down, box rebooting) fails soft: the last snapshot
is kept and marked stale via `age_sec`, so the UI degrades honestly instead of
crashing.

Per-port throughput is derived from the 64-bit ifHCIn/OutOctets counters by
diffing two consecutive samples:

    rate_mbits = (delta_octets * 8) / delta_seconds / 1e6

The first poll has no previous sample, so it yields 0 rates. A negative delta
(Counter64 wrap or box reboot) is skipped for that direction.
"""
import re
import subprocess
import threading
import time

# ── IF-MIB OIDs (numeric, so no MIB files need to be installed) ──────────────
OID_SYSDESCR = "1.3.6.1.2.1.1.1.0"          # sysDescr.0            -> model string
OID_IFNAME = "1.3.6.1.2.1.31.1.1.1.1"       # ifName               -> per-index name
OID_IN_OCTETS = "1.3.6.1.2.1.31.1.1.1.6"    # ifHCInOctets         -> Counter64
OID_OUT_OCTETS = "1.3.6.1.2.1.31.1.1.1.10"  # ifHCOutOctets        -> Counter64
OID_HIGH_SPEED = "1.3.6.1.2.1.31.1.1.1.15"  # ifHighSpeed          -> Mbit/s
OID_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"     # ifOperStatus         -> 1=up

# Keep only the physical uplink/downlink ports; everything else (loopback,
# tunnels, dummies, VLAN sub-interfaces like eth10.2, …) is dropped.
_KEEP_ETH = re.compile(r"^eth\d+$")


def _num(v):
    try:
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _is_up(v):
    # ifOperStatus. Depending on net-snmp output flags this is "1" or "up(1)"
    # or "up" — accept all of them, everything else counts as down.
    s = str(v).strip().lower()
    return s == "1" or s.startswith("up")


def _keep_name(name):
    return bool(_KEEP_ETH.match(name)) or name == "switch0"


class SnmpPoller:
    def __init__(self, key, host, user, auth_pass, priv_pass, poll_sec=30, timeout=8):
        self.key = key
        self.host = host or ""
        self.user = user or ""
        self.auth_pass = auth_pass or ""
        self.priv_pass = priv_pass or ""
        self.poll_sec = poll_sec
        self.timeout = timeout
        self._lock = threading.Lock()
        self._ports = []            # list of port dicts (published snapshot)
        self._model = None          # sysDescr.0, fetched once
        self._prev = {}             # ifIndex -> (in_octets, out_octets)
        self._prev_t = None         # epoch of the previous counter sample
        self._last_ok = None        # epoch of last successful poll
        self._last_err = None
        self._started = False

    # ── enabled? ──────────────────────────────────────────────────────────────
    @property
    def enabled(self):
        return bool(self.host and self.user and self.auth_pass and self.priv_pass)

    # ── SNMP CLI helpers (strictly GET / WALK — never SET) ───────────────────
    def _auth_args(self):
        # SNMPv3 authPriv. Secrets come from the constructor, never hardcoded.
        return [
            "-v3", "-u", self.user, "-l", "authPriv",
            "-a", "SHA", "-A", self.auth_pass,
            "-x", "AES", "-X", self.priv_pass,
        ]

    def _run(self, argv):
        p = subprocess.run(
            argv, capture_output=True, text=True, timeout=self.timeout,
        )
        if p.returncode != 0 and not p.stdout.strip():
            err = (p.stderr or p.stdout or "snmp failed").strip()
            raise RuntimeError(err.splitlines()[0] if err else "snmp failed")
        return p.stdout

    def _walk(self, oid):
        """bulk-WALK one column -> {ifIndex(str): value(str)}."""
        argv = (
            ["snmpbulkwalk"] + self._auth_args()
            + ["-O", "qn", "-t", "4", "-r", "1", self.host, oid]
        )
        out = {}
        for line in self._run(argv).splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            oid_part = parts[0]
            val = parts[1].strip() if len(parts) > 1 else ""
            if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
                val = val[1:-1]
            idx = oid_part.rsplit(".", 1)[-1]
            out[idx] = val
        return out

    def _fetch_model(self):
        try:
            argv = (
                ["snmpget"] + self._auth_args()
                + ["-O", "qv", "-t", "4", "-r", "1", self.host, OID_SYSDESCR]
            )
            val = self._run(argv).strip()
            if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
                val = val[1:-1]
            if val:
                with self._lock:
                    self._model = val
        except Exception as e:
            self._last_err = f"sysDescr: {e}"

    # ── poll ──────────────────────────────────────────────────────────────────
    def poll_once(self):
        if not self.enabled:
            return
        try:
            names = self._walk(OID_IFNAME)
            in_oct = self._walk(OID_IN_OCTETS)
            out_oct = self._walk(OID_OUT_OCTETS)
            speed = self._walk(OID_HIGH_SPEED)
            oper = self._walk(OID_OPER_STATUS)
        except Exception as e:
            self._last_err = f"walk: {e}"
            return

        now = time.time()
        prev = self._prev
        dt = (now - self._prev_t) if self._prev_t else None

        ports = []
        new_prev = {}
        for idx, name in names.items():
            in_c = _int(in_oct.get(idx))
            out_c = _int(out_oct.get(idx))
            if in_c is not None and out_c is not None:
                new_prev[idx] = (in_c, out_c)

            in_mb = 0.0
            out_mb = 0.0
            if dt and dt > 0 and idx in prev and in_c is not None and out_c is not None:
                p_in, p_out = prev[idx]
                d_in = in_c - p_in
                d_out = out_c - p_out
                if d_in >= 0:                       # skip Counter64 wrap / reboot
                    in_mb = d_in * 8 / dt / 1e6
                if d_out >= 0:
                    out_mb = d_out * 8 / dt / 1e6

            if not _keep_name(name):
                continue

            sp = _num(speed.get(idx))
            ports.append({
                "name": name,
                "in_mbits": round(in_mb, 3),
                "out_mbits": round(out_mb, 3),
                "oper": "up" if _is_up(oper.get(idx)) else "down",
                "speed_mbit": int(sp) if sp and sp > 0 else None,
            })

        ports.sort(key=lambda p: p["in_mbits"] + p["out_mbits"], reverse=True)

        with self._lock:
            self._ports = ports
            self._prev = new_prev
            self._prev_t = now
            self._last_ok = now
            self._last_err = None

    def _loop(self):
        self._fetch_model()          # best effort once
        tick = 0
        while True:
            self.poll_once()
            tick += 1
            if tick % 20 == 0 and not self._model:   # keep retrying model
                self._fetch_model()
            time.sleep(self.poll_sec)

    def start(self):
        if self._started or not self.enabled:
            return
        self._started = True
        threading.Thread(target=self._loop, daemon=True, name=f"snmp-{self.key}").start()

    # ── access ────────────────────────────────────────────────────────────────
    def age(self):
        if not self._last_ok:
            return None
        return time.time() - self._last_ok

    def snapshot(self):
        with self._lock:
            ports = list(self._ports)
            model = self._model
            ok = self._last_ok
        return {
            "host": self.host,
            "age_sec": round(time.time() - ok, 1) if ok else None,
            "ports": ports,
            "model": model,
        }

    def info(self):
        with self._lock:
            n = len(self._ports)
            ok = self._last_ok
            err = self._last_err
        return {
            "key": self.key,
            "enabled": self.enabled,
            "host": self.host,
            "age_sec": round(time.time() - ok, 1) if ok else None,
            "last_err": err,
            "ports": n,
        }
