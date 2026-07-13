"""IPFIX (RFC 7011) Collector → per-host aggregation → JSON HTTP for HA.

Direct IPFIX parser, no python-netflow dependency.
Handles UDM Pro SE IPFIX exports.

v2: hostname resolution from HA device_tracker, 5-min history buckets
    for top-host stack-area plots, extended service map.
v3: per-device aggregation keyed by MAC (IPFIX fields 56/80) so IPv6
    privacy addresses land on the right device, published to HA as one
    MQTT-discovery sensor per device (state = MB today, v4/v6 attrs).
"""
from __future__ import annotations

import ipaddress
import json
import os
import socket
import struct
import threading
import time
from datetime import datetime, timezone
import urllib.request
import urllib.error
from collections import Counter, defaultdict, deque
from http.server import BaseHTTPRequestHandler, HTTPServer

import geoip2.database


# ---------------------------------------------------------------------------
# Config (env)
# ---------------------------------------------------------------------------
COLLECTOR_HOST   = os.environ.get("COLLECTOR_HOST", "0.0.0.0")
COLLECTOR_PORT   = int(os.environ.get("COLLECTOR_PORT", "2055"))
HTTP_PORT        = int(os.environ.get("HTTP_PORT", "3002"))
GEOIP_DB         = os.environ.get("GEOIP_DB", "/home/robeertm/flow-collector/geoip/GeoLite2-Country.mmdb")
TOP_N            = int(os.environ.get("TOP_N", "25"))
TOP_DEST_PER_HOST = int(os.environ.get("TOP_DEST_PER_HOST", "8"))
ROLL_SECONDS     = int(os.environ.get("ROLL_SECONDS", "60"))
DAILY_RESET_HOUR = int(os.environ.get("DAILY_RESET_HOUR", "0"))
HA_URL           = os.environ.get("HA_URL", "")
HA_TOKEN         = os.environ.get("HA_TOKEN", "")
HOSTNAME_REFRESH_SEC = int(os.environ.get("HOSTNAME_REFRESH_SEC", "120"))
HISTORY_BUCKETS  = int(os.environ.get("HISTORY_BUCKETS", "144"))   # 144 × 5min = 12h
HISTORY_BUCKET_SEC = int(os.environ.get("HISTORY_BUCKET_SEC", "300"))  # 5min
MQTT_HOST        = os.environ.get("MQTT_HOST", "")
MQTT_PORT        = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER        = os.environ.get("MQTT_USER", "")
MQTT_PASS        = os.environ.get("MQTT_PASS", "")
MQTT_DISCOVERY_PREFIX = os.environ.get("MQTT_DISCOVERY_PREFIX", "homeassistant")
MQTT_PUBLISH_SEC = int(os.environ.get("MQTT_PUBLISH_SEC", "60"))
DEVICE_PURGE_DAYS = int(os.environ.get("DEVICE_PURGE_DAYS", "7"))


# ---------------------------------------------------------------------------
# IPFIX field IDs from IANA (RFC 5102 + IANA registry)
# ---------------------------------------------------------------------------
F_OCTET_DELTA          = 1
F_PACKET_DELTA         = 2
F_PROTOCOL             = 4
F_SRC_TOS              = 5
F_TCP_FLAGS            = 6
F_SRC_PORT             = 7
F_SRC_IPV4             = 8
F_INGRESS_INTERFACE    = 10
F_DST_PORT             = 11
F_DST_IPV4             = 12
F_EGRESS_INTERFACE     = 14
F_OCTET_TOTAL          = 85
F_PACKET_TOTAL         = 86
F_FLOW_START_SECS      = 150
F_FLOW_END_SECS        = 151
F_FLOW_START_MS        = 152
F_FLOW_END_MS          = 153
F_SAMPLING_INTERVAL    = 34
F_VLAN_ID              = 58
F_POST_VLAN_ID         = 59
F_SRC_IPV6             = 27
F_DST_IPV6             = 28
F_IP_VERSION           = 60
F_FLOW_DIRECTION       = 61
F_IPv6_SRC_PREFIX      = 29
F_IPv6_DST_PREFIX      = 30
F_FLOW_END_REASON      = 136
F_BIFLOW_DIRECTION     = 239
F_SRC_MAC              = 56   # sourceMacAddress
F_DST_MAC              = 80   # destinationMacAddress


# ---------------------------------------------------------------------------
# Local networks
# ---------------------------------------------------------------------------
LOCAL_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

# Known local IPv6 prefix? Will auto-add /56 + /64 from observed traffic.
LOCAL_V6_PREFIXES: set = set()

# Site config via env (JSON) — empty defaults = site-agnostic (add-on build).
# VLANs then show by their IPFIX id, is_local() uses the RFC1918/ULA
# LOCAL_NETWORKS above, and the local IPv6 /56 is auto-learned from observed
# traffic + the host's own GUA. Override per site:
#   VLAN_NAMES_JSON  : {"3":"BTC","6":"Office"}      (IPFIX vlan-id -> name)
#   SUBNET_VLAN_JSON : {"10.20.1.0/24":"BTC"}        (subnet -> name)
#   LOCAL_V6_GUA     : "2a02:810a:8294::/48"          (optional static prefix)
VLAN_NAMES = {int(k): v for k, v in
              json.loads(os.environ.get("VLAN_NAMES_JSON", "{}")).items()}

SUBNET_VLAN = {ipaddress.ip_network(k): v for k, v in
               json.loads(os.environ.get("SUBNET_VLAN_JSON", "{}")).items()}

_gua = os.environ.get("LOCAL_V6_GUA", "").strip()
if _gua:
    LOCAL_V6_PREFIXES.add(ipaddress.ip_network(_gua))


# ---------------------------------------------------------------------------
# Auto-detect local /56 prefix from the Pi's own GUA address.
#
# Vodafone rotates the /56 at reconnect. We poll the Pi's own v6 address
# every 60s and register the parent /56. This is robust because the Pi
# is in SmartHome VLAN and gets a SLAAC address from the current prefix.
# ---------------------------------------------------------------------------
def detect_local_v6_prefixes() -> set:
    """Scan local interfaces for global IPv6 addresses, return set of /56s."""
    import subprocess, re
    prefixes = set()
    try:
        out = subprocess.check_output(
            ["ip", "-6", "-o", "addr", "show", "scope", "global"],
            text=True, timeout=2)
    except Exception:
        return prefixes
    for line in out.splitlines():
        m = re.search(r'inet6\s+([0-9a-f:]+)/(\d+)', line)
        if not m:
            continue
        try:
            addr = ipaddress.IPv6Address(m.group(1))
        except Exception:
            continue
        # GUA only
        if not (0x2000 <= (int(addr) >> 112) <= 0x3fff):
            continue
        # skip tailscale/lo/etc by interface? -o output is "iface\tinet6 ..."
        # we accept all GUA — adding extras doesn't hurt
        try:
            net56 = ipaddress.ip_network((addr, 56), strict=False)
            prefixes.add(net56)
        except Exception:
            pass
    return prefixes


def prefix_watcher_loop():
    """Background thread: rescans /56 every 60s, updates LOCAL_V6_PREFIXES."""
    known = set()
    while True:
        try:
            current = detect_local_v6_prefixes()
            new = current - known
            for p in new:
                LOCAL_V6_PREFIXES.add(p)
                print(f"[{time.strftime('%H:%M:%S')}] LOCAL v6 prefix detected: {p}",
                      flush=True)
            known = current
        except Exception as e:
            print(f"prefix_watcher error: {e}", flush=True)
        time.sleep(60)

SERVICE_PORTS = {
    20: "FTP", 21: "FTP", 22: "SSH", 23: "Telnet",
    25: "SMTP", 53: "DNS", 67: "DHCP", 68: "DHCP", 69: "TFTP",
    80: "HTTP", 110: "POP3", 123: "NTP",
    137: "NetBIOS", 138: "NetBIOS", 139: "NetBIOS",
    143: "IMAP", 161: "SNMP", 162: "SNMP",
    179: "BGP", 194: "IRC", 389: "LDAP", 443: "HTTPS", 445: "SMB",
    465: "SMTPS", 514: "Syslog", 515: "Printing",
    548: "AFP", 587: "SMTP", 631: "Printing", 636: "LDAPS",
    873: "rsync", 993: "IMAPS", 995: "POP3S",
    1080: "SOCKS", 1194: "OpenVPN", 1433: "MSSQL", 1521: "Oracle",
    1701: "L2TP", 1723: "PPTP", 1812: "RADIUS", 1900: "SSDP", 1935: "RTMP",
    1883: "MQTT", 2049: "NFS", 2055: "NetFlow", 2222: "SSH-alt",
    2375: "Docker", 2376: "Docker-TLS",
    3000: "Dev", 3128: "Proxy", 3306: "MySQL", 3389: "RDP",
    3478: "STUN", 3479: "STUN",
    4500: "IPsec", 4567: "Sync", 4711: "HASS-MQTT",
    5000: "UPnP", 5001: "Sync",
    5060: "SIP", 5061: "SIP", 5223: "APNs", 5228: "GCM",
    5246: "UniFi-ADP", 5353: "mDNS", 5432: "Postgres",
    5556: "UniFi-WSS", 5683: "CoAP",
    6379: "Redis", 6443: "K8s", 6789: "UniFi", 6881: "BitTorrent", 6882: "BitTorrent",
    7000: "HomeKit", 7777: "HomeKit",
    8000: "HTTP-alt", 8008: "HTTP-alt", 8009: "Chromecast",
    8080: "HTTP-alt", 8123: "HomeAssistant", 8333: "Bitcoin",
    8443: "HTTPS-alt", 8843: "HTTPS-alt", 8883: "MQTTS",
    9000: "PHP-FPM", 9090: "Prometheus",
    9100: "node-exp", 9200: "Elastic", 9333: "Litecoin",
    18333: "BTC-testnet", 27017: "MongoDB", 32400: "Plex",
    41641: "Tailscale", 50000: "Sync",
    51820: "WireGuard", 60001: "MOSH",
    # Erweiterungen aus Beobachtung Roberts Netz
    5222: "XMPP",         # iMessage Push, Jabber
    5228: "GCM-FCM",
    5938: "TeamViewer",
    25565: "Minecraft",
    27015: "Steam-Game", 27036: "Steam",
    3074: "Xbox-Live",
    9987: "TeamSpeak",
    19132: "Minecraft-BE",
    8801: "Zoom", 8802: "Zoom",
    1935: "RTMP",
    11211: "Memcached",
    9418: "git",
    554: "RTSP", 1900: "SSDP",
    5683: "CoAP",
    8009: "Chromecast", 8060: "Roku",
    3479: "STUN", 3480: "STUN",
    1755: "MMS",
}

# Protocol numbers
PROTO_NAMES = {
    1: "ICMP", 2: "IGMP", 6: "TCP", 17: "UDP",
    41: "IPv6", 47: "GRE", 50: "ESP", 51: "AH",
    58: "ICMPv6", 89: "OSPF", 132: "SCTP",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def is_local(ip_obj) -> bool:
    if ip_obj is None:
        return False
    try:
        for n in LOCAL_NETWORKS:
            if ip_obj.version == n.version and ip_obj in n:
                return True
        for n in LOCAL_V6_PREFIXES:
            if ip_obj.version == 6 and ip_obj in n:
                return True
    except (ValueError, TypeError):
        return False
    return False


def classify_service(port: int, proto: int) -> str:
    if port in SERVICE_PORTS:
        return SERVICE_PORTS[port]
    if proto == 1:  return "ICMP"
    if proto == 58: return "ICMPv6"
    if proto == 50: return "ESP"
    if proto == 41: return "IPv6-Tunnel"
    if proto == 47: return "GRE"
    if port > 49151: return "Ephemeral"
    if port == 0: return PROTO_NAMES.get(proto, f"proto-{proto}")
    return f"port-{port}"


def vlan_name_for(vlan_id, ip) -> str:
    if vlan_id and vlan_id in VLAN_NAMES:
        return VLAN_NAMES[vlan_id]
    if ip is not None:
        try:
            for net, name in SUBNET_VLAN.items():
                if ip.version == net.version and ip in net:
                    return name
        except (ValueError, TypeError):
            pass
    if vlan_id is not None and vlan_id > 0:
        return f"VLAN {vlan_id}"
    return "Default"


# ---------------------------------------------------------------------------
# IPFIX parser (RFC 7011)
# ---------------------------------------------------------------------------
class IPFIXParser:
    def __init__(self):
        # {observation_domain_id: {template_id: [(field_id, length), ...]}}
        self.templates: dict[int, dict[int, list]] = defaultdict(dict)
        # options templates -- parsed but not interpreted (still need to skip the data)
        self.options_templates: dict[int, dict[int, list]] = defaultdict(dict)

    def parse(self, data: bytes):
        """Yield (field_dict, observation_domain_id) for each data record."""
        if len(data) < 16:
            return
        version, length, _, _, dom = struct.unpack(">HHIII", data[:16])
        if version != 10:
            return
        length = min(length, len(data))
        pos = 16
        while pos + 4 <= length:
            try:
                set_id, set_len = struct.unpack(">HH", data[pos:pos+4])
            except struct.error:
                return
            if set_len < 4 or pos + set_len > length:
                return
            set_end = pos + set_len
            body = data[pos+4:set_end]

            if set_id == 2:
                # Template Set
                self._parse_template_set(dom, body)
            elif set_id == 3:
                # Options Template Set
                self._parse_options_template_set(dom, body)
            elif set_id >= 256:
                # Data Set
                fields = self.templates.get(dom, {}).get(set_id)
                if fields is None:
                    # might be an options-template data set; skip
                    fields_opts = self.options_templates.get(dom, {}).get(set_id)
                    if fields_opts:
                        # parse but only to consume; ignore content
                        for _ in self._records(body, fields_opts):
                            pass
                else:
                    for rec in self._records(body, fields):
                        yield rec, dom
            pos = set_end

    def _parse_template_set(self, dom, body):
        p = 0
        while p + 4 <= len(body):
            tid, count = struct.unpack(">HH", body[p:p+4])
            p += 4
            fields = []
            for _ in range(count):
                if p + 4 > len(body):
                    return
                fid, flen = struct.unpack(">HH", body[p:p+4])
                p += 4
                if fid & 0x8000:
                    # enterprise PEN follows
                    if p + 4 > len(body):
                        return
                    pen, = struct.unpack(">I", body[p:p+4])
                    p += 4
                    fields.append((fid & 0x7FFF, flen, pen))
                else:
                    fields.append((fid, flen, 0))
            self.templates[dom][tid] = fields

    def _parse_options_template_set(self, dom, body):
        p = 0
        while p + 6 <= len(body):
            tid, total, scope = struct.unpack(">HHH", body[p:p+6])
            p += 6
            fields = []
            for _ in range(total):
                if p + 4 > len(body):
                    return
                fid, flen = struct.unpack(">HH", body[p:p+4])
                p += 4
                if fid & 0x8000:
                    if p + 4 > len(body):
                        return
                    pen, = struct.unpack(">I", body[p:p+4])
                    p += 4
                    fields.append((fid & 0x7FFF, flen, pen))
                else:
                    fields.append((fid, flen, 0))
            self.options_templates[dom][tid] = fields

    def _records(self, body, fields):
        rec_size = sum(flen if flen != 0xFFFF else 1 for _, flen, _ in fields)
        if rec_size == 0:
            return
        offset = 0
        while offset + rec_size <= len(body):
            record = {}
            p = offset
            for fid, flen, _pen in fields:
                if flen == 0xFFFF:
                    # variable length
                    if p + 1 > len(body):
                        return
                    vl = body[p]; p += 1
                    if vl == 255:
                        if p + 2 > len(body):
                            return
                        vl = struct.unpack(">H", body[p:p+2])[0]
                        p += 2
                    record[fid] = body[p:p+vl]
                    p += vl
                else:
                    record[fid] = body[p:p+flen]
                    p += flen
            yield record
            offset += rec_size


def field_int(rec: dict, fid: int, default: int = 0) -> int:
    v = rec.get(fid)
    if v is None:
        return default
    if isinstance(v, (bytes, bytearray)):
        return int.from_bytes(v, "big")
    return int(v)


def field_ip(rec: dict, fid_v4: int, fid_v6: int):
    """Return ipaddress object or None."""
    if fid_v4 in rec:
        v = rec[fid_v4]
        if len(v) == 4:
            return ipaddress.IPv4Address(bytes(v))
    if fid_v6 in rec:
        v = rec[fid_v6]
        if len(v) == 16:
            return ipaddress.IPv6Address(bytes(v))
    return None


def field_mac(rec: dict, fid: int):
    """Return 'aa:bb:cc:dd:ee:ff' or None. Filters empty/multicast/broadcast."""
    v = rec.get(fid)
    if not isinstance(v, (bytes, bytearray)) or len(v) != 6:
        return None
    if v == b"\x00" * 6 or (v[0] & 0x01):
        return None
    return ":".join(f"{b:02x}" for b in v)


# ---------------------------------------------------------------------------
# Aggregator state
# ---------------------------------------------------------------------------
class HostStat:
    __slots__ = ("ip","name","vlan","vlan_name",
                  "sent_v4","rcvd_v4","sent_v6","rcvd_v6",
                  "packets_sent","packets_rcvd","flows",
                  "first_seen","last_seen",
                  "dest_ips","dest_countries","services",
                  "history")

    def __init__(self, ip: str):
        self.ip = ip
        self.name = ip
        self.vlan = None
        self.vlan_name = ""
        self.sent_v4 = 0; self.rcvd_v4 = 0
        self.sent_v6 = 0; self.rcvd_v6 = 0
        self.packets_sent = 0; self.packets_rcvd = 0
        self.flows = 0
        self.first_seen = time.time()
        self.last_seen = time.time()
        self.dest_ips: Counter = Counter()
        self.dest_countries: Counter = Counter()
        self.services: Counter = Counter()
        # rolling 12h history in 5min buckets: deque of (bucket_ts, bytes)
        self.history: deque = deque(maxlen=HISTORY_BUCKETS)

    def total(self) -> int:
        return self.sent_v4 + self.rcvd_v4 + self.sent_v6 + self.rcvd_v6

    def total_v4(self) -> int: return self.sent_v4 + self.rcvd_v4
    def total_v6(self) -> int: return self.sent_v6 + self.rcvd_v6


class DeviceStat:
    """Per-physical-device aggregation keyed by MAC. Collects v4 + all v6
    privacy addresses of the same device. Survives daily reset (counters
    zeroed, identity kept) so MQTT sensors stay stable."""
    __slots__ = ("mac","name","vlan_name","vlan_from_v4",
                 "sent_v4","rcvd_v4","sent_v6","rcvd_v6","flows",
                 "ips_v4","ips_v6","first_seen","last_seen",
                 "_rt_snap_up","_rt_snap_dn","_rt_snap_ts",
                 "rate_up_mbps","rate_dn_mbps")

    def __init__(self, mac: str):
        self.mac = mac
        self.name = ""
        self.vlan_name = ""
        self.vlan_from_v4 = False
        self.sent_v4 = 0; self.rcvd_v4 = 0
        self.sent_v6 = 0; self.rcvd_v6 = 0
        self.flows = 0
        self.ips_v4: set = set()
        self.ips_v6: set = set()
        self.first_seen = time.time()
        self.last_seen = time.time()
        # live throughput: delta of cumulative up/down bytes between publish
        # cycles (~MQTT_PUBLISH_SEC) -> average Mbit/s. up=sent, down=rcvd.
        self._rt_snap_up = 0
        self._rt_snap_dn = 0
        self._rt_snap_ts = time.time()
        self.rate_up_mbps = 0.0
        self.rate_dn_mbps = 0.0

    def update_rate(self, now: float):
        """Compute avg Mbit/s (up=sent, down=rcvd) since last call from the
        cumulative byte counters. Guards the midnight reset (counters drop)."""
        up_bytes = self.sent_v4 + self.sent_v6
        dn_bytes = self.rcvd_v4 + self.rcvd_v6
        dt = now - self._rt_snap_ts
        d_up = up_bytes - self._rt_snap_up
        d_dn = dn_bytes - self._rt_snap_dn
        if dt >= 1 and d_up >= 0 and d_dn >= 0:
            self.rate_up_mbps = round(d_up * 8 / dt / 1e6, 2)
            self.rate_dn_mbps = round(d_dn * 8 / dt / 1e6, 2)
        else:                       # first cycle or after daily reset -> re-baseline
            self.rate_up_mbps = 0.0
            self.rate_dn_mbps = 0.0
        self._rt_snap_up = up_bytes
        self._rt_snap_dn = dn_bytes
        self._rt_snap_ts = now

    def total(self) -> int:
        return self.sent_v4 + self.rcvd_v4 + self.sent_v6 + self.rcvd_v6

    def total_v4(self) -> int: return self.sent_v4 + self.rcvd_v4
    def total_v6(self) -> int: return self.sent_v6 + self.rcvd_v6

    def reset_counters(self):
        self.sent_v4 = 0; self.rcvd_v4 = 0
        self.sent_v6 = 0; self.rcvd_v6 = 0
        self.flows = 0
        self.ips_v6.clear()   # privacy addresses rotate; refill within a day


class State:
    def __init__(self):
        self.lock = threading.RLock()
        self.started_at = time.time()
        self.day_started_at = time.time()
        # monotonic lifetime counters (never reset, only restart-reset which
        # state_class: total_increasing handles)
        self.lifetime = {"sent_v4": 0, "rcvd_v4": 0, "sent_v6": 0, "rcvd_v6": 0}
        self.hosts: dict[str, HostStat] = {}
        # MAC -> DeviceStat (v3 device aggregation, feeds MQTT discovery)
        self.devices: dict[str, DeviceStat] = {}
        # MACs purged after DEVICE_PURGE_DAYS; mqtt_loop clears their topics
        self.purged_devices: list[str] = []
        # IP -> name (from HA device_tracker, refreshed periodically)
        self.hostnames: dict[str, str] = {}
        # MAC -> name (from HA device_tracker `mac` attribute)
        self.macnames: dict[str, str] = {}
        # MAC -> True/False (device_tracker state home/not_home)
        self.mac_online: dict[str, bool] = {}
        # IP -> device MAC, learned from outbound flows + HA trackers.
        # Routed flows carry the UDM interface MAC, so this mapping is the
        # authoritative way to attribute inbound (and v6 privacy) traffic.
        self.ip2mac: dict[str, str] = {}
        # router detection: MAC seen as src for many distinct v4 IPs = gateway
        self.mac_src_ips: dict[str, set] = defaultdict(set)
        self.router_macs: set = set()
        self.device_miss = 0   # flows we could not attribute to a device
        # global throughput history: deque of (bucket_ts, bytes_v4, bytes_v6, flows)
        self.global_history: deque = deque(maxlen=HISTORY_BUCKETS)
        # per-vlan history: name -> deque of (bucket_ts, bytes_v4, bytes_v6)
        self.vlan_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=HISTORY_BUCKETS))
        # internal accumulators per bucket
        self._bucket_ts = self._cur_bucket_ts()
        self._bucket_global = [0, 0, 0]   # v4, v6, flows
        self._bucket_vlans: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # v4, v6
        self._bucket_hosts: dict[str, int] = defaultdict(int)   # ip -> bytes
        self.vlans: dict[str, dict] = defaultdict(lambda: {
            "sent_v4": 0, "rcvd_v4": 0,
            "sent_v6": 0, "rcvd_v6": 0,
            "hosts": set(),
        })
        self.totals = {"sent_v4": 0, "rcvd_v4": 0, "sent_v6": 0, "rcvd_v6": 0}
        self.global_services: Counter = Counter()
        self.global_countries: Counter = Counter()
        self.packets_recv = 0
        self.packets_drop = 0
        self.flows_processed = 0
        self.flows_skipped = 0
        self.window: deque = deque(maxlen=ROLL_SECONDS)
        self.last_window_sec = int(time.time())
        self.window_bytes = 0
        self.window_flows = 0
        # template stats
        self.template_count = 0

    def _cur_bucket_ts(self) -> int:
        return int(time.time() // HISTORY_BUCKET_SEC) * HISTORY_BUCKET_SEC

    def tick_window(self):
        now_sec = int(time.time())
        with self.lock:
            while self.last_window_sec < now_sec:
                self.window.append((self.window_bytes, self.window_flows))
                self.window_bytes = 0
                self.window_flows = 0
                self.last_window_sec += 1
            # bucket flush?
            cur = self._cur_bucket_ts()
            if cur > self._bucket_ts:
                # flush completed bucket
                self.global_history.append((self._bucket_ts, *self._bucket_global))
                for vn, bv in self._bucket_vlans.items():
                    self.vlan_history[vn].append((self._bucket_ts, bv[0], bv[1]))
                for ip, b in self._bucket_hosts.items():
                    h = self.hosts.get(ip)
                    if h is not None:
                        h.history.append((self._bucket_ts, b))
                self._bucket_ts = cur
                self._bucket_global = [0, 0, 0]
                self._bucket_vlans = defaultdict(lambda: [0, 0])
                self._bucket_hosts = defaultdict(int)

    def add_window(self, b):
        with self.lock:
            self.window_bytes += b
            self.window_flows += 1

    def reset_daily_if_needed(self):
        now = time.time()
        local = time.localtime(now)
        if local.tm_hour == DAILY_RESET_HOUR and (now - self.day_started_at) > 23 * 3600:
            self.reset_daily()

    def reset_daily(self):
        with self.lock:
            self.hosts.clear()
            self.vlans.clear()
            for k in self.totals:
                self.totals[k] = 0
            self.global_services.clear()
            self.global_countries.clear()
            # devices: keep identity (stable MQTT sensors), zero the counters;
            # drop devices not seen for DEVICE_PURGE_DAYS (guest phones etc.)
            cutoff = time.time() - DEVICE_PURGE_DAYS * 86400
            for mac in list(self.devices):
                d = self.devices[mac]
                if d.last_seen < cutoff:
                    self.purged_devices.append(mac)
                    del self.devices[mac]
                else:
                    d.reset_counters()
            self.day_started_at = time.time()
            print(f"[{time.strftime('%H:%M:%S')}] DAILY RESET", flush=True)


# ---------------------------------------------------------------------------
# GeoIP
# ---------------------------------------------------------------------------
class GeoLookup:
    def __init__(self, db_path: str):
        self.reader = None
        try:
            self.reader = geoip2.database.Reader(db_path)
            print(f"GeoIP loaded: {db_path}", flush=True)
        except Exception as e:
            print(f"GeoIP load failed: {e}", flush=True)
        self.cache: dict[str, str] = {}

    def country(self, ip_obj) -> str:
        if ip_obj is None or self.reader is None or is_local(ip_obj):
            return ""
        ip_str = str(ip_obj)
        if ip_str in self.cache:
            return self.cache[ip_str]
        try:
            r = self.reader.country(ip_str)
            code = r.country.iso_code or "??"
        except Exception:
            code = "??"
        if len(self.cache) > 50000:
            self.cache.clear()
        self.cache[ip_str] = code
        return code


# ---------------------------------------------------------------------------
# Processor: take parsed records, update state
# ---------------------------------------------------------------------------
class Processor:
    def __init__(self, state: State, geo: GeoLookup):
        self.state = state
        self.geo   = geo
        self.sampling_default = int(os.environ.get("DEFAULT_SAMPLING_RATE", "1"))

    def process(self, record: dict):
        bytes_ = field_int(record, F_OCTET_DELTA)
        if bytes_ == 0:
            bytes_ = field_int(record, F_OCTET_TOTAL)
        pkts   = field_int(record, F_PACKET_DELTA)
        if pkts == 0:
            pkts = field_int(record, F_PACKET_TOTAL)
        proto   = field_int(record, F_PROTOCOL)
        sport   = field_int(record, F_SRC_PORT)
        dport   = field_int(record, F_DST_PORT)
        vlan_id = field_int(record, F_VLAN_ID)
        sampling = field_int(record, F_SAMPLING_INTERVAL, self.sampling_default)
        if sampling < 1:
            sampling = self.sampling_default

        src_ip = field_ip(record, F_SRC_IPV4, F_SRC_IPV6)
        dst_ip = field_ip(record, F_DST_IPV4, F_DST_IPV6)
        if src_ip is None or dst_ip is None or bytes_ == 0:
            self.state.flows_skipped += 1
            return

        bytes_ *= sampling
        pkts   *= sampling
        ver = src_ip.version if src_ip else (dst_ip.version if dst_ip else 4)

        src_local = is_local(src_ip)
        dst_local = is_local(dst_ip)

        # remember discovered local IPv6 prefixes
        if src_ip.version == 6 and src_local:
            try:
                net = ipaddress.ip_network((src_ip, 64), strict=False)
                LOCAL_V6_PREFIXES.add(net)
            except Exception:
                pass

        if not (src_local or dst_local):
            return

        self.state.add_window(bytes_)
        self.state.flows_processed += 1

        with self.state.lock:
            if src_local:
                # outbound: local=src(sport), peer=dst(dport)
                self._add_host(src_ip, vlan_id, True,  bytes_, pkts, ver, dst_ip, dport, sport, proto)
                mac = self._device_mac(src_ip, field_mac(record, F_SRC_MAC), learn=True)
                if mac:
                    self._add_device(mac, src_ip, vlan_id, True, bytes_, ver)
            if dst_local:
                # inbound: local=dst(dport), peer=src(sport)
                self._add_host(dst_ip, vlan_id, False, bytes_, pkts, ver, src_ip, sport, dport, proto)
                mac = self._device_mac(dst_ip, field_mac(record, F_DST_MAC), learn=False)
                if mac:
                    self._add_device(mac, dst_ip, vlan_id, False, bytes_, ver)

            # global totals (daily, resets at midnight)
            if src_local:
                key = "sent_v6" if ver == 6 else "sent_v4"
                self.state.totals[key] += bytes_
                self.state.lifetime[key] += bytes_
            if dst_local and not (src_local and dst_local):
                key = "rcvd_v6" if ver == 6 else "rcvd_v4"
                self.state.totals[key] += bytes_
                self.state.lifetime[key] += bytes_

            # history buckets
            if ver == 6:
                self.state._bucket_global[1] += bytes_
            else:
                self.state._bucket_global[0] += bytes_
            self.state._bucket_global[2] += 1

            # global services / countries
            svc_port = min(sport, dport) if (sport and dport) else max(sport, dport)
            svc = classify_service(svc_port, proto)
            self.state.global_services[svc] += bytes_

            ext_ip = None
            if src_local and not dst_local:   ext_ip = dst_ip
            elif dst_local and not src_local: ext_ip = src_ip
            if ext_ip is not None:
                cc = self.geo.country(ext_ip)
                if cc:
                    self.state.global_countries[cc] += bytes_

    def _add_host(self, ip_obj, vlan_id, sent, bytes_, pkts, ver, peer_ip_obj, peer_port, local_port, proto):
        ip = str(ip_obj)
        h = self.state.hosts.get(ip)
        if h is None:
            h = HostStat(ip); self.state.hosts[ip] = h
        h.last_seen = time.time()

        if vlan_id and not h.vlan:
            h.vlan = int(vlan_id)
        if not h.vlan_name:
            h.vlan_name = vlan_name_for(h.vlan, ip_obj)

        if sent:
            if ver == 6: h.sent_v6 += bytes_
            else:        h.sent_v4 += bytes_
            h.packets_sent += pkts
        else:
            if ver == 6: h.rcvd_v6 += bytes_
            else:        h.rcvd_v4 += bytes_
            h.packets_rcvd += pkts
        h.flows += 1

        if peer_ip_obj is not None and not is_local(peer_ip_obj):
            peer_ip = str(peer_ip_obj)
            h.dest_ips[peer_ip] += bytes_
            cc = self.geo.country(peer_ip_obj)
            if cc:
                h.dest_countries[cc] += bytes_

        svc_port = min(peer_port, local_port) if (peer_port and local_port) else max(peer_port, local_port)
        h.services[classify_service(svc_port, proto)] += bytes_

        vname = h.vlan_name or "Default"
        v = self.state.vlans[vname]
        v["hosts"].add(ip)
        if sent:
            if ver == 6: v["sent_v6"] += bytes_
            else:        v["sent_v4"] += bytes_
        else:
            if ver == 6: v["rcvd_v6"] += bytes_
            else:        v["rcvd_v4"] += bytes_

        # bucket accumulators
        bv = self.state._bucket_vlans[vname]
        if ver == 6: bv[1] += bytes_
        else:        bv[0] += bytes_
        self.state._bucket_hosts[ip] += bytes_

        # apply hostname from HA if available
        if h.name == h.ip:
            nm = self.state.hostnames.get(ip)
            if nm:
                h.name = nm

    def _device_mac(self, ip_obj, flow_mac, learn: bool):
        """Resolve the device MAC for a local IP. The learned ip→mac table
        wins because routed flows carry the UDM interface MAC instead of the
        client MAC. Outbound flows (learn=True) teach the table — including
        IPv6 privacy addresses — unless the MAC turns out to be a router."""
        st = self.state
        ip = str(ip_obj)
        if flow_mac and flow_mac not in st.router_macs and learn:
            if ip_obj.version == 4:
                s = st.mac_src_ips[flow_mac]
                if len(s) < 16:
                    s.add(ip)
                if len(s) > 4:
                    # gateway/BVI MAC: fronts many source IPs — disqualify it
                    st.router_macs.add(flow_mac)
                    st.mac_src_ips.pop(flow_mac, None)
                    if flow_mac in st.devices:
                        del st.devices[flow_mac]
                        st.purged_devices.append(flow_mac)
                    st.ip2mac = {k: v for k, v in st.ip2mac.items() if v != flow_mac}
                    print(f"[{time.strftime('%H:%M:%S')}] router MAC detected: {flow_mac}",
                          flush=True)
                    flow_mac = None
        known = st.ip2mac.get(ip)
        if known:
            return known
        if flow_mac and flow_mac not in st.router_macs:
            if learn:
                if len(st.ip2mac) > 20000:
                    st.ip2mac.clear()
                st.ip2mac[ip] = flow_mac
                return flow_mac
            # inbound fallback: only trust the flow MAC if it is already a
            # known device (otherwise it is likely an unseen gateway MAC)
            if flow_mac in st.devices:
                return flow_mac
        self.state.device_miss += 1
        return None

    def _add_device(self, mac, ip_obj, vlan_id, sent, bytes_, ver):
        d = self.state.devices.get(mac)
        if d is None:
            d = DeviceStat(mac)
            self.state.devices[mac] = d
        d.last_seen = time.time()
        if ver == 6:
            if len(d.ips_v6) < 64:
                d.ips_v6.add(str(ip_obj))
            if sent: d.sent_v6 += bytes_
            else:    d.rcvd_v6 += bytes_
        else:
            if len(d.ips_v4) < 16:
                d.ips_v4.add(str(ip_obj))
            if sent: d.sent_v4 += bytes_
            else:    d.rcvd_v4 += bytes_
        d.flows += 1
        # v4-derived VLAN mapping is authoritative (v6 prefixes may be ambiguous)
        if not d.vlan_name or (ver == 4 and not d.vlan_from_v4):
            vn = vlan_name_for(int(vlan_id) if vlan_id else None, ip_obj)
            if vn:
                d.vlan_name = vn
                d.vlan_from_v4 = (ver == 4)
        if not d.name:
            nm = self.state.macnames.get(mac)
            if nm:
                d.name = nm


# ---------------------------------------------------------------------------
# HA hostname resolver (polls device_tracker.* for IP→Name map)
# ---------------------------------------------------------------------------
def resolve_loop(state: State):
    if not (HA_URL and HA_TOKEN):
        print("HA lookup disabled (HA_URL/HA_TOKEN not set)", flush=True)
        return
    url = HA_URL.rstrip("/") + "/api/states"
    req_headers = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}
    while True:
        try:
            req = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=10) as r:
                states_list = json.loads(r.read())
            mapping = {}
            mac_mapping = {}
            mac_online = {}
            for s in states_list:
                eid = s.get("entity_id", "")
                if not eid.startswith("device_tracker."):
                    continue
                attrs = s.get("attributes", {}) or {}
                ip = attrs.get("ip")
                mac_attr = attrs.get("mac")
                if not ip and not mac_attr:
                    continue
                # Prefer friendly_name (human label like "Hue Bridge Arbeitszimmer"),
                # then host_name (often MAC for shitty devices), then entity slug.
                fn = attrs.get("friendly_name")
                hn = attrs.get("host_name")
                # Avoid MAC-like host_names (hex blob, length 12)
                def is_mac_like(s):
                    if not isinstance(s, str): return False
                    s2 = s.lower().replace(":","").replace("-","")
                    return len(s2) == 12 and all(c in "0123456789abcdef" for c in s2)
                if fn and not (isinstance(fn,str) and is_mac_like(fn)):
                    candidate = fn
                elif hn and not is_mac_like(hn):
                    candidate = hn
                else:
                    candidate = eid.split(".",1)[1]
                # de-dup repeated friendly_name like "umbrel umbrel" or
                # "Hue Bridge Arbeitszimmer Hue Bridge Arbeitszimmer"
                if isinstance(candidate, str):
                    # exact half-duplication: "A A" where A is the first half
                    n = len(candidate)
                    if n >= 4 and n % 2 == 1 and candidate[n//2] == ' ':
                        h = candidate[:n//2]
                        if candidate == h + ' ' + h:
                            candidate = h
                    # token-level "X X X X" → "X X"
                    parts = candidate.split()
                    if len(parts) >= 2 and len(parts) % 2 == 0:
                        half = len(parts) // 2
                        if parts[:half] == parts[half:]:
                            candidate = ' '.join(parts[:half])
                if ip:
                    mapping[ip] = candidate
                if isinstance(mac_attr, str) and len(mac_attr) >= 12:
                    mac_mapping[mac_attr.lower()] = candidate
                    mac_online[mac_attr.lower()] = (s.get("state") == "home")
            with state.lock:
                state.hostnames = mapping
                state.macnames = mac_mapping
                state.mac_online = mac_online
                # apply to already-seen hosts
                for ip, h in state.hosts.items():
                    nm = mapping.get(ip)
                    if nm and h.name == h.ip:
                        h.name = nm
                # devices: always refresh (UniFi renames should flow through)
                for mac, d in state.devices.items():
                    nm = mac_mapping.get(mac)
                    if nm:
                        d.name = nm
            print(f"[{time.strftime('%H:%M:%S')}] HA hostnames loaded: {len(mapping)} "
                  f"(macs: {len(mac_mapping)})", flush=True)
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] HA lookup error: {e}", flush=True)
        time.sleep(HOSTNAME_REFRESH_SEC)


# ---------------------------------------------------------------------------
# MQTT discovery publisher: one HA sensor per device (state = MB today,
# ipv4/ipv6 split as attributes). Entities appear/disappear automatically.
# ---------------------------------------------------------------------------
def _fmt_mb(mb: float) -> str:
    if mb >= 1024:
        return f"{mb/1024:.2f} GB"
    if mb >= 100:
        return f"{mb:.0f} MB"
    return f"{mb:.1f} MB"


def _slugify(s: str) -> str:
    import unicodedata, re
    s = (s or "").lower()
    for a, b in (("ä","ae"),("ö","oe"),("ü","ue"),("ß","ss")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


def mqtt_loop(state: State):
    if not MQTT_HOST:
        print("MQTT publish disabled (MQTT_HOST not set)", flush=True)
        return
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("MQTT disabled: paho-mqtt not installed", flush=True)
        return

    def on_message(_cli, _ud, msg):
        # import retained attrs from a previous session so device identity
        # (name, purge clock) survives collector restarts
        try:
            p = json.loads(msg.payload.decode())
            mac = p.get("mac")
            if not mac:
                return
            with state.lock:
                if mac not in state.devices:
                    d = DeviceStat(mac)
                    d.name = p.get("name_hint") or ""
                    d.vlan_name = p.get("vlan") or ""
                    if p.get("ip"):
                        d.ips_v4.add(p["ip"])
                    d.last_seen = float(p.get("last_seen_ts") or time.time())
                    d.first_seen = d.last_seen
                    state.devices[mac] = d
        except Exception:
            pass

    republish_flag = {"do": False}

    def on_connect(cli, _ud, _flags, reason_code, _props=None):
        print(f"[{time.strftime('%H:%M:%S')}] MQTT connected: {reason_code}", flush=True)
        cli.publish("flowcol/status", "online", retain=True)
        cli.subscribe("flowcol/dev/+/attrs")
        republish_flag["do"] = True   # force full discovery re-publish on (re)connect

    try:
        cli = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="flow-collector")
    except AttributeError:  # paho 1.x fallback
        cli = mqtt.Client(client_id="flow-collector")
    if MQTT_USER:
        cli.username_pw_set(MQTT_USER, MQTT_PASS)
    cli.will_set("flowcol/status", "offline", retain=True)
    cli.on_connect = on_connect
    cli.on_message = on_message
    cli.reconnect_delay_set(2, 60)
    while True:
        try:
            cli.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            break
        except Exception as e:
            print(f"MQTT connect failed: {e} — retry in 15s", flush=True)
            time.sleep(15)
    cli.loop_start()
    # publishes before CONNACK is processed are silently dropped at QoS 0 —
    # wait for the connection to be fully up before the first cycle
    t0 = time.time()
    while not cli.is_connected() and time.time() - t0 < 30:
        time.sleep(0.5)

    # wait for the first HA name resolve so entity_ids get pretty slugs
    t0 = time.time()
    while not state.macnames and time.time() - t0 < 180:
        time.sleep(5)

    published_cfg: dict = {}   # mac -> last config json (republish only on change)
    while True:
      try:
        cli.publish("flowcol/heartbeat",
                    json.dumps({"ts": datetime.now(timezone.utc).isoformat()}), retain=True)
        if republish_flag["do"]:
            published_cfg.clear()          # re-send all discovery after a (re)connect
            republish_flag["do"] = False
        with state.lock:
            devs = list(state.devices.values())
            purged = state.purged_devices[:]
            state.purged_devices.clear()

        for mac in purged:
            ms = mac.replace(":", "")
            cli.publish(f"{MQTT_DISCOVERY_PREFIX}/sensor/flowdev_{ms}/config", "", qos=1, retain=True)
            for sfx in ("v4", "v6"):
                cli.publish(f"{MQTT_DISCOVERY_PREFIX}/sensor/flowdev_{ms}_{sfx}/config", "", qos=1, retain=True)
            cli.publish(f"flowcol/dev/{ms}/state", "", retain=True)
            cli.publish(f"flowcol/dev/{ms}/attrs", "", retain=True)
            published_cfg.pop(mac, None)

        now = time.time()
        for d in devs:
            first_publish = d.mac not in published_cfg
            if first_publish:
                if d.total() == 0 and not d.name:
                    continue                      # nameless AND silent — skip
                if not d.name and (now - d.first_seen) < 600:
                    continue                      # give HA resolver a chance first
            ms = d.mac.replace(":", "")
            name = d.name or f"Gerät …{d.mac[-5:]}"
            slug = _slugify(d.name) or f"mac_{ms[-6:]}"
            base = f"flowcol/dev/{ms}"
            config = {
                "name": None,
                "unique_id": f"flowdev_{ms}",
                "default_entity_id": f"sensor.devtraffic_{slug}",
                "state_topic": base + "/state",
                "json_attributes_topic": base + "/attrs",
                "unit_of_measurement": "MB",
                "device_class": "data_size",
                "state_class": "total_increasing",
                "suggested_display_precision": 0,
                "icon": "mdi:swap-vertical",
                "availability_topic": "flowcol/status",
                "device": {
                    "identifiers": [f"flowdev_{ms}"],
                    "name": name,
                    "manufacturer": "Flow-Collector",
                    "model": "IPFIX Geräte-Traffic",
                },
            }
            cfg_json = json.dumps(config, ensure_ascii=False, sort_keys=True)
            if published_cfg.get(d.mac) != cfg_json:
                info = cli.publish(f"{MQTT_DISCOVERY_PREFIX}/sensor/flowdev_{ms}/config",
                                   cfg_json, qos=1, retain=True)
                # v4/v6 sub-sensors read from the same attrs topic — real
                # entities (with recorder history) instead of attributes,
                # so per-device plots can show three lines
                all_ok = info.rc == 0
                for sfx, key in (("v4", "ipv4_mb"), ("v6", "ipv6_mb")):
                    sub = {
                        "name": f"IPv{sfx[1]}",
                        "unique_id": f"flowdev_{ms}_{sfx}",
                        "default_entity_id": f"sensor.devtraffic_{slug}_{sfx}",
                        "state_topic": base + "/attrs",
                        "value_template": "{{ value_json.%s | float(0) }}" % key,
                        "unit_of_measurement": "MB",
                        "device_class": "data_size",
                        "state_class": "total_increasing",
                        "suggested_display_precision": 0,
                        "icon": f"mdi:alpha-{sfx[1]}-circle-outline",
                        "availability_topic": "flowcol/status",
                        "device": config["device"],
                    }
                    inf2 = cli.publish(f"{MQTT_DISCOVERY_PREFIX}/sensor/flowdev_{ms}_{sfx}/config",
                                       json.dumps(sub, ensure_ascii=False, sort_keys=True),
                                       qos=1, retain=True)
                    all_ok = all_ok and inf2.rc == 0
                if all_ok:   # only mark as sent if the broker took everything
                    published_cfg[d.mac] = cfg_json
            v4mb = d.total_v4() / 1e6
            v6mb = d.total_v6() / 1e6
            tot  = v4mb + v6mb
            d.update_rate(time.time())
            attrs = {
                "ipv4": "v4 " + _fmt_mb(v4mb),
                "ipv6": "v6 " + _fmt_mb(v6mb),
                "ipv4_mb": round(v4mb, 1),
                "ipv6_mb": round(v6mb, 1),
                "v6_share": round(v6mb / tot * 100, 1) if tot else 0.0,
                "rate_dn_mbps": d.rate_dn_mbps,
                "rate_up_mbps": d.rate_up_mbps,
                "ip": sorted(d.ips_v4)[0] if d.ips_v4 else "",
                "v6_adressen": len(d.ips_v6),
                "vlan": d.vlan_name or "?",
                "mac": d.mac,
                "flows": d.flows,
                "online": state.mac_online.get(d.mac),
                "last_seen_ts": int(d.last_seen),
                "name_hint": d.name,
                "src": "flowcol",
            }
            cli.publish(base + "/state", f"{tot:.1f}", retain=True)
            cli.publish(base + "/attrs",
                        json.dumps(attrs, ensure_ascii=False), retain=True)
      except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] MQTT publish cycle error: {e}", flush=True)
      time.sleep(MQTT_PUBLISH_SEC)


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------
def _v6_short_label(ip_str: str) -> str:
    """Make a friendly compact label for an IPv6 host without a known name."""
    try:
        ip = ipaddress.IPv6Address(ip_str)
        # last 64 bits as 4 groups of hex
        suffix = format(int(ip) & 0xFFFFFFFFFFFFFFFF, '016x')
        # show last 8 hex digits as identifier
        return f"v6 …{suffix[-8:-4]}:{suffix[-4:]}"
    except Exception:
        return ip_str


def snapshot(state: State) -> dict:
    with state.lock:
        hosts = sorted(state.hosts.values(), key=lambda h: h.total(), reverse=True)
        top_hosts = []
        for h in hosts[:TOP_N]:
            t = h.total()
            display_name = h.name
            if display_name == h.ip and ":" in h.ip:
                display_name = _v6_short_label(h.ip)
            top_hosts.append({
                "ip":           h.ip,
                "name":         display_name,
                "vlan":         h.vlan,
                "vlan_name":    h.vlan_name,
                "sent":         h.sent_v4 + h.sent_v6,
                "rcvd":         h.rcvd_v4 + h.rcvd_v6,
                "total":        t,
                "sent_v4":      h.sent_v4,
                "rcvd_v4":      h.rcvd_v4,
                "sent_v6":      h.sent_v6,
                "rcvd_v6":      h.rcvd_v6,
                "total_v4":     h.total_v4(),
                "total_v6":     h.total_v6(),
                "v6_share":     round(h.total_v6() / t * 100, 1) if t else 0,
                "packets":      h.packets_sent + h.packets_rcvd,
                "flows":        h.flows,
                "last_seen":    int(h.last_seen),
                "top_dest":     [{"ip": ip, "bytes": b} for ip, b in h.dest_ips.most_common(TOP_DEST_PER_HOST)],
                "top_services": [{"name": s, "bytes": b} for s, b in h.services.most_common(5)],
                "top_countries":[{"cc": c, "bytes": b} for c, b in h.dest_countries.most_common(5)],
            })

        per_vlan = []
        for name, v in state.vlans.items():
            total = v["sent_v4"] + v["rcvd_v4"] + v["sent_v6"] + v["rcvd_v6"]
            per_vlan.append({
                "name":     name,
                "hosts":    len(v["hosts"]),
                "sent":     v["sent_v4"] + v["sent_v6"],
                "rcvd":     v["rcvd_v4"] + v["rcvd_v6"],
                "total":    total,
                "total_v4": v["sent_v4"] + v["rcvd_v4"],
                "total_v6": v["sent_v6"] + v["rcvd_v6"],
                "v6_share": round((v["sent_v6"]+v["rcvd_v6"])/total*100,1) if total else 0,
            })
        per_vlan.sort(key=lambda x: x["total"], reverse=True)

        bps = flows_per_sec = 0
        if state.window:
            total_b = sum(b for b, _ in state.window)
            total_f = sum(f for _, f in state.window)
            bps = total_b / len(state.window) * 8
            flows_per_sec = total_f / len(state.window)

        total_v4 = state.totals["sent_v4"] + state.totals["rcvd_v4"]
        total_v6 = state.totals["sent_v6"] + state.totals["rcvd_v6"]
        total   = total_v4 + total_v6

        # global history: serialize last 144 buckets (12h × 5min)
        gh_list = [{"ts": ts, "v4": v4, "v6": v6, "flows": fl}
                   for (ts, v4, v6, fl) in list(state.global_history)]

        # per-vlan history
        vlan_history = {}
        for vn, dq in state.vlan_history.items():
            vlan_history[vn] = [{"ts": ts, "v4": v4, "v6": v6}
                                for (ts, v4, v6) in list(dq)]

        # top-5 host stack-area-friendly history
        top5_history = []
        for h in hosts[:5]:
            top5_history.append({
                "ip":      h.ip,
                "name":    h.name,
                "vlan_name": h.vlan_name,
                "history": [{"ts": ts, "b": b} for (ts, b) in list(h.history)],
            })

        return {
            "ts":         int(time.time()),
            "started_at": int(state.day_started_at),
            "live": {
                "throughput_bps":  int(bps),
                "throughput_mbits":round(bps / 1_000_000, 3),
                "flows_per_sec":   round(flows_per_sec, 2),
            },
            "totals": {
                "bytes":      total,
                "bytes_v4":   total_v4,
                "bytes_v6":   total_v6,
                "v6_share":   round(total_v6 / total * 100, 2) if total else 0,
                "sent_v4":    state.totals["sent_v4"],
                "rcvd_v4":    state.totals["rcvd_v4"],
                "sent_v6":    state.totals["sent_v6"],
                "rcvd_v6":    state.totals["rcvd_v6"],
            },
            "lifetime": {
                "sent_v4":    state.lifetime["sent_v4"],
                "rcvd_v4":    state.lifetime["rcvd_v4"],
                "sent_v6":    state.lifetime["sent_v6"],
                "rcvd_v6":    state.lifetime["rcvd_v6"],
            },
            "host_count":   len(state.hosts),
            "top_hosts":    top_hosts,
            "per_vlan":     per_vlan,
            "top_services": [{"name": s, "bytes": b} for s, b in state.global_services.most_common(15)],
            "top_countries":[{"cc": c, "bytes": b} for c, b in state.global_countries.most_common(15)],
            "history": {
                "bucket_sec":   HISTORY_BUCKET_SEC,
                "global":       gh_list,
                "per_vlan":     vlan_history,
                "top5_hosts":   top5_history,
            },
            "stats": {
                "packets_recv":     state.packets_recv,
                "packets_drop":     state.packets_drop,
                "flows_processed":  state.flows_processed,
                "flows_skipped":    state.flows_skipped,
                "templates_known":  state.template_count,
                "hostnames_known":  len(state.hostnames),
                "v6_prefixes":      sorted(str(p) for p in LOCAL_V6_PREFIXES
                                            if p.version == 6 and p.prefixlen >= 32),
            },
        }


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class HTTPHandler(BaseHTTPRequestHandler):
    state: State = None

    def log_message(self, *a, **k): pass

    def do_GET(self):
        if self.path.startswith("/api/state"):
            payload = json.dumps(snapshot(self.state), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)
        elif self.path == "/healthz":
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
        elif self.path == "/api/state_lean":
            # without history (smaller payload for HA REST sensor that has 16384b attr limit)
            snap = snapshot(self.state)
            snap.pop("history", None)
            # keep top_hosts services+countries but trim destinations
            for h in snap.get("top_hosts", [])[:15]:
                h.pop("top_dest", None)
                h.pop("first_seen", None)
                h.pop("last_seen", None)
                h.pop("packets", None)
            snap["top_hosts"] = snap["top_hosts"][:15]
            payload = json.dumps(snap, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(payload)
        elif self.path == "/api/devices":
            with self.state.lock:
                devs = sorted(self.state.devices.values(),
                              key=lambda d: d.total(), reverse=True)
                out = [{"mac": d.mac, "name": d.name,
                        "vlan": d.vlan_name,
                        "ip": sorted(d.ips_v4)[0] if d.ips_v4 else "",
                        "v6_ips": len(d.ips_v6),
                        "mb_v4": round(d.total_v4() / 1e6, 1),
                        "mb_v6": round(d.total_v6() / 1e6, 1),
                        "mb_total": round(d.total() / 1e6, 1),
                        "rate_dn_mbps": d.rate_dn_mbps,
                        "rate_up_mbps": d.rate_up_mbps,
                        "last_seen": int(d.last_seen)} for d in devs]
            payload = json.dumps({"count": len(out),
                                  "miss": self.state.device_miss,
                                  "router_macs": sorted(self.state.router_macs),
                                  "ip2mac_size": len(self.state.ip2mac),
                                  "devices": out},
                                 ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(payload)
        elif self.path == "/api/history":
            snap = snapshot(self.state)
            payload = json.dumps(snap.get("history", {}), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(payload)
        elif self.path == "/templates":
            # debug — show known templates
            payload = json.dumps({"templates": {
                str(d): {str(t): [list(f) for f in fields]
                          for t, fields in tpls.items()}
                for d, tpls in PARSER.templates.items()},
            }, default=str).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.end_headers(); self.wfile.write(payload)
        else:
            self.send_response(404); self.end_headers()


# Global parser instance
PARSER = IPFIXParser()


def collector_loop(state: State, processor: Processor):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
    sock.bind((COLLECTOR_HOST, COLLECTOR_PORT))
    sock.settimeout(1.0)
    print(f"IPFIX collector listening on UDP/{COLLECTOR_PORT}", flush=True)

    log_counter = 0
    while True:
        try:
            data, addr = sock.recvfrom(8192)
        except socket.timeout:
            state.tick_window()
            continue
        state.packets_recv += 1
        try:
            for record, _dom in PARSER.parse(data):
                processor.process(record)
        except Exception as e:
            state.packets_drop += 1
        state.tick_window()
        log_counter += 1
        if log_counter % 500 == 0:
            t_count = sum(len(t) for t in PARSER.templates.values())
            state.template_count = t_count
            print(f"[{time.strftime('%H:%M:%S')}] pkts={state.packets_recv} "
                  f"flows={state.flows_processed} skip={state.flows_skipped} "
                  f"hosts={len(state.hosts)} tpls={t_count}", flush=True)


def maintenance_loop(state: State):
    while True:
        time.sleep(60)
        state.reset_daily_if_needed()


def main():
    state = State()
    geo   = GeoLookup(GEOIP_DB)
    proc  = Processor(state, geo)

    threading.Thread(target=collector_loop, args=(state, proc), daemon=True).start()
    threading.Thread(target=maintenance_loop, args=(state,),    daemon=True).start()
    threading.Thread(target=resolve_loop,    args=(state,),    daemon=True).start()
    threading.Thread(target=prefix_watcher_loop, daemon=True).start()
    threading.Thread(target=mqtt_loop,       args=(state,),    daemon=True).start()

    HTTPHandler.state = state
    print(f"HTTP :{HTTP_PORT}/api/state", flush=True)
    HTTPServer(("0.0.0.0", HTTP_PORT), HTTPHandler).serve_forever()


if __name__ == "__main__":
    main()
