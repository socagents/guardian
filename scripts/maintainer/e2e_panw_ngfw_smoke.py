#!/usr/bin/env python3
"""PANW NGFW first-light smoke test.

Sends a CEF traffic event with vendor=panw, product=ngfw_cef to the broker on
phantom-vm and checks where it lands in XSIAM.

WHAT THIS PROVES
================
1. Pack YAML field shapes are wire-format-correct (the synthetic event uses the
   exact field names from the data_source.yaml's fields[] section)
2. Data path is functional (event reaches XSIAM through the broker → MCP)
3. Where the event ACTUALLY landed — likely `unknown_unknown_raw` until the
   operator configures a Broker VM Syslog Applet for vendor=panw, product=ngfw_cef
   AND installs the upstream Cortex PANW NGFW pack in their XSIAM tenant

This is a deliberate first-light smoke — not a full saturation. Tests one CEF
event with the marker `panw-ngfw-smoke-<batch>` in session_id. Once the broker
applet config is in place, this same script will start finding the event in
`panw_ngfw_traffic_raw` instead of `unknown_unknown_raw`.

USAGE
=====
    set -a && source .env.vm && set +a
    gcloud compute start-iap-tunnel ...   # see CLAUDE.md for full pattern
    SSHPASS=... sshpass -e ssh ... \\
      'MCP_TOKEN=$(sudo docker exec phantom_agent env | grep ^MCP_TOKEN= | cut -d= -f2-)
       sudo docker exec -e MCP_TOKEN -i phantom_agent python3 -' \\
      < scripts/maintainer/e2e_panw_ngfw_smoke.py
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
import urllib.request
from datetime import datetime, timezone


BROKER = ("10.10.0.8", 514)  # phantom-vm broker default port
TOKEN = os.environ["MCP_TOKEN"]
XSIAM_MCP = "http://phantom-connector-xsiam-Cortex_XSIAM:9000/mcp"

BATCH = int(time.time())
MARKER = f"panw-ngfw-smoke-{BATCH}"
ts_bsd = datetime.now(timezone.utc).strftime("%b %d %H:%M:%S")


# PANW NGFW traffic event — uses raw fields from the panw_ngfw_traffic_raw
# data_source.yaml schema. Field names match what `ngfw_standalone` + the
# traffic MODEL block expect.
ext = {
    # log_type discrimination (Cortex routes by this in the upstream pack's PR)
    "log_type": "traffic",
    "sub_type": "end",  # traffic end event — has bytes/packets

    # Session identification (the marker carrier)
    "session_id": MARKER,

    # Network 5-tuple
    "source_ip": "10.1.2.3",
    "source_port": "54321",
    "dest_ip": "10.20.30.40",
    "dest_port": "443",
    "protocol": "tcp",

    # App-ID classification
    "app": "ssl",
    "app_category": "general-internet",
    "app_sub_category": "encrypted-tunnel",

    # Security policy + zones
    "rule_matched": "Allow-Outbound-Web",
    "from_zone": "trust",
    "to_zone": "untrust",
    "action": "allow",
    "inbound_if": "ethernet1/1",
    "outbound_if": "ethernet1/2",

    # User-ID
    "source_user": "corp\\alice",
    "dest_user": "",  # outbound traffic — no dest user

    # Traffic-specific volumetrics (the 5 fields that differentiate traffic_raw)
    "bytes_sent": "4096",
    "bytes_received": "16384",
    "packets_sent": "28",
    "packets_received": "42",
    "total_time_elapsed": "60",  # seconds; MR multiplies by 1000

    # Log source identity
    "log_source": "panw-ngfw",
    "log_source_name": "pa-fw-smoke-01",
    "log_source_id": "001801000099",

    # NAT / proxy flags
    "is_nat": "false",
    "is_proxy": "false",
}

kv = " ".join(f"{k}={v}" for k, v in ext.items())
msg = (
    f"<134>{ts_bsd} smoke-host CEF:0|panw|ngfw_cef|10.2.0|"
    f"TRAFFIC|Session-end|6|{kv}"
)

print(f"=== PANW NGFW first-light smoke ===")
print(f"BATCH={BATCH}  MARKER={MARKER}")
print(f"CEF header: vendor=panw, product=ngfw_cef")
print(f"Extensions: {len(ext)}, CEF length: {len(msg)} bytes")
print(f"  (under UDP MTU 1500: {'YES' if len(msg) < 1500 else 'NO'})")
print()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for _ in range(3):
    sock.sendto(msg.encode(), BROKER)
sock.close()
print(f"Sent 3× UDP packets to {BROKER[0]}:{BROKER[1]}")

print(f"\nWait 120s for ingestion + XDM materialization...")
for i in range(4):
    time.sleep(30)
    print(f"  +{(i+1)*30}s")


# ============================================================
# XSIAM MCP boilerplate (matches FortiGate followup pattern)
# ============================================================

def post_mcp(body, sid=None):
    h = {
        "Authorization": "Bearer " + TOKEN,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if sid:
        h["mcp-session-id"] = sid
    req = urllib.request.Request(
        XSIAM_MCP, data=json.dumps(body).encode(), headers=h, method="POST"
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read().decode(), resp.headers


def sse(s):
    for ln in s.split("\n"):
        ln = ln.strip()
        if ln.startswith("data:"):
            try:
                f = json.loads(ln[5:].strip())
                if "result" in f:
                    c = f["result"].get("content", [])
                    if c:
                        return json.loads(c[0].get("text", "{}"))
            except Exception:
                pass
    return {}


_, h = post_mcp({
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "panw-smoke", "version": "1.0"},
    },
})
sid = h.get("mcp-session-id") or h.get("Mcp-Session-Id")
post_mcp(
    {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
    sid,
)


def xql(sid, q):
    body, _ = post_mcp({
        "jsonrpc": "2.0", "id": 99, "method": "tools/call",
        "params": {
            "name": "run_xql_query",
            "arguments": {"request": {"query": q}},
        },
    }, sid)
    return sse(body)


# ============================================================
# Look in all 4 candidate landing datasets
# ============================================================

CANDIDATES = [
    ("panw_ngfw_traffic_raw", "Where it SHOULD land (if upstream Cortex PANW pack + broker applet configured)"),
    ("panw_ngfw_cef_raw",     "No-hit catch-all in PANW NGFW PR — falls here if PR found, but no per-log_type filter matched"),
    ("xlog_unknown_raw",      "Phantom's own catch-all (if event came through xlog bridge)"),
    ("unknown_unknown_raw",   "XSIAM final catch-all when broker can't tag vendor/product"),
]

print(f"\n=== Searching candidate datasets for marker `{MARKER}` ===\n")

landed_in = []
for dataset, hint in CANDIDATES:
    q = (
        f"dataset = {dataset} "
        f"| filter session_id contains \"{MARKER}\" "
        f"   or _raw_log contains \"{MARKER}\" "
        f"   or msg contains \"{MARKER}\" "
        f"| fields _time, session_id, log_type, sub_type, action, app, "
        f"         xdm.event.id, xdm.event.type, xdm.event.operation_sub_type, "
        f"         xdm.observer.action, xdm.network.application_protocol, "
        f"         xdm.source.ipv4, xdm.target.ipv4 "
        f"| limit 3"
    )
    print(f"  [{dataset}]  {hint}")
    try:
        r = xql(sid, q)
        reply = r.get("reply", {})
        nresults = reply.get("number_of_results", 0)
        status = reply.get("status", "?")
        if status == "SUCCESS" and nresults > 0:
            print(f"    ✅ FOUND {nresults} result(s)")
            row = reply["results"]["data"][0]
            populated = {k: v for k, v in row.items() if v not in (None, "", "null")}
            print(f"    Populated columns: {len(populated)}")
            for k, v in sorted(populated.items())[:15]:
                print(f"      {k:42} = {str(v)[:60]}")
            landed_in.append((dataset, nresults))
        else:
            print(f"    ⊘ no hits (status={status}, n={nresults})")
    except Exception as e:
        print(f"    ⚠ query error: {type(e).__name__}: {str(e)[:120]}")
    print()


# ============================================================
# Summary
# ============================================================

print("=" * 60)
print("SUMMARY")
print("=" * 60)
if landed_in:
    for dataset, n in landed_in:
        print(f"  ✓ Event found in {dataset} ({n} row{'s' if n != 1 else ''})")
    if any(d == "panw_ngfw_traffic_raw" for d, _ in landed_in):
        print(f"\n✅ PERFECT — event routed to panw_ngfw_traffic_raw.")
        print("   This means: broker applet + upstream Cortex PANW NGFW pack are both configured.")
        sys.exit(0)
    elif any(d == "panw_ngfw_cef_raw" for d, _ in landed_in):
        print(f"\n⚠ PARTIAL — event landed in panw_ngfw_cef_raw (PR catch-all).")
        print("   Likely the Cortex PANW NGFW pack's per-log_type INGEST filters")
        print("   are missing from the deployed PR. Operator should install the")
        print("   upstream pack from XSIAM Marketplace.")
        sys.exit(0)
    else:
        print(f"\n⚠ GAP — event landed in catch-all dataset.")
        print("   Broker doesn't have a PANW applet, OR the applet config doesn't")
        print("   tag vendor=panw, product=ngfw_cef. Operator should configure:")
        print("     XSIAM → Settings → Configurations → Data Broker → Applets →")
        print("       Add Applet (Syslog) →")
        print("         Vendor: panw")
        print("         Product: ngfw_cef")
        print("         Port: (dedicated, e.g. 1516)")
        print("   Then re-point this script to send to the new port.")
        sys.exit(1)
else:
    print(f"\n✗ Event NOT FOUND in any candidate dataset.")
    print("   Either broker isn't ingesting on port 514, or events are being dropped.")
    print("   Operator should check: docker logs phantom-broker on phantom-vm.")
    sys.exit(1)
