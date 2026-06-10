#!/usr/bin/env python3
"""Batch 2 multi-vendor smoke — 3 syslog-based vendors from the operator's PR+MR paste.

VENDORS (all UDP→broker→XSIAM path):
  1. cisco-ise            (syslog RFC 3164 with CISE_<type> tokens)
  2. LinuxEventsCollection (RFC 3339 syslog with auth.log / messages content)
  3. ProofpointServerProtection (RFC 5424 with k=v structured fields)

For each: send 3× UDP packets to phantom-vm broker port 514, wait 120s, then
query XSIAM XQL for the marker. Distinguish `status=FAIL` (dataset doesn't exist)
from `SUCCESS, n=0` (dataset exists but no row matched).

USAGE
=====
    SSHPASS=... sshpass -e ssh ... \\
      'MCP_TOKEN=$(sudo docker exec phantom_agent env | grep ^MCP_TOKEN= | cut -d= -f2-)
       sudo docker exec -e MCP_TOKEN -i phantom_agent python3 -' \\
      < scripts/maintainer/e2e_batch2_smoke.py
"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.request
from datetime import datetime, timezone


BROKER = ("10.10.0.8", 514)
TOKEN = os.environ["MCP_TOKEN"]
XSIAM_MCP = "http://phantom-connector-xsiam-Cortex_XSIAM:9000/mcp"

BATCH = int(time.time())
ts_bsd = datetime.now(timezone.utc).strftime("%b %d %H:%M:%S")
ts_iso_offset = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")
ts_iso_z = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


# ============================================================
# Per-vendor synthetic events
# ============================================================

# (1) Cisco ISE — RFC 3164 format with CISE_<log_type> token
# The MR matches logType ~= CISE_Passed_Authentications, CISE_Failed_Attempts, etc.
ISE_MARKER = f"batch2-ise-{BATCH}"
ise_event = (
    f"<134>{ts_bsd} ise-host CISE_Passed_Authentications 0000000001 1 0 "
    f"2026-05-27 10:00:00.000 +00:00 12345 NOTICE "
    f"Authentication succeeded, ConfigVersionId=1, Device IP Address=10.5.5.5, "
    f"NetworkDeviceName=corp-switch-01, User-Name=alice@corp.example, "
    f"Framed-IP-Address=10.10.10.10, AcsSessionID={ISE_MARKER}, "
    f"EapAuthentication=EAP-TLS, AuthenticationMethod=dot1x, "
    f"Calling-Station-ID=00:50:56:aa:bb:01, Called-Station-ID=00:50:56:cc:dd:02, "
    f"NAS-Port=50101"
)

# (2) LinuxEventsCollection — RFC 3339 syslog (auth.log style)
LINUX_MARKER = f"batch2-linux-{BATCH}"
linux_event = (
    f"<86>{ts_iso_z} linux-host sshd[12345]: "
    f"Accepted password for {LINUX_MARKER}_user from 198.51.100.7 port 53245 ssh2"
)

# (3) ProofpointServerProtection — RFC 5424 with ISO+offset, k=v structured data
PPS_MARKER = f"batch2-pps-{BATCH}"
pps_event = (
    f"<134>{ts_iso_offset} pps-host filter[9876]: "
    f"alert=\"{PPS_MARKER}\" mod=\"filter\" rule=\"AntiVirus\" from=\"<attacker@malicious.example>\" "
    f"to=\"victim@corp.example\" subject=\"Urgent invoice\" "
    f"size=\"4096\" mime=\"application/pdf\" oext=\"pdf\" "
    f"file=\"invoice.pdf\" action=\"reject\" cmd=\"DATA\" "
    f"ip=\"203.0.113.10\" host=\"mail.malicious.example\" "
    f"x=\"msg-id-{PPS_MARKER}\" s=\"<smtp-{PPS_MARKER}@malicious>\""
)

SMOKES = [
    {"name": "cisco-ise",                    "dataset": "cisco_ise_raw",       "event": ise_event,   "marker": ISE_MARKER,   "marker_field": "AcsSessionID"},
    {"name": "LinuxEventsCollection",        "dataset": "linux_linux_raw",     "event": linux_event, "marker": LINUX_MARKER, "marker_field": "_raw_log"},
    {"name": "ProofpointServerProtection",   "dataset": "proofpoint_ps_raw",   "event": pps_event,   "marker": PPS_MARKER,   "marker_field": "_raw_log"},
]


# ============================================================
# Send all events
# ============================================================

print("=" * 70)
print(f"BATCH 2 syslog smoke — 3 vendors  ({BATCH})")
print("=" * 70)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for s in SMOKES:
    e = s["event"]
    print(f"\n[{s['name']}]  → {BROKER[0]}:{BROKER[1]}  ({len(e)} bytes)")
    print(f"  marker={s['marker']}")
    print(f"  event[:120]={e[:120]}{'...' if len(e) > 120 else ''}")
    for _ in range(3):
        sock.sendto(e.encode(), BROKER)
sock.close()
print(f"\nAll events sent. Waiting 120s for ingestion + XDM materialization...")
for i in range(4):
    time.sleep(30)
    print(f"  +{(i+1)*30}s")


# ============================================================
# XSIAM MCP boilerplate
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
        "clientInfo": {"name": "batch2-smoke", "version": "1.0"},
    },
})
sid = h.get("mcp-session-id") or h.get("Mcp-Session-Id")
post_mcp(
    {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
    sid,
)


def xql(q):
    body, _ = post_mcp({
        "jsonrpc": "2.0", "id": 99, "method": "tools/call",
        "params": {
            "name": "run_xql_query",
            "arguments": {
                "request": {
                    "query": q,
                    "tenant_timeframe": {"relativeTime": 900000},  # last 15 min
                },
            },
        },
    }, sid)
    return sse(body)


# ============================================================
# Per-vendor verification
# ============================================================

print("\n" + "=" * 70)
print("VERIFICATION (XQL searches)")
print("=" * 70)

results = []
for s in SMOKES:
    name = s["name"]
    dataset = s["dataset"]
    marker = s["marker"]
    marker_field = s["marker_field"]

    print(f"\n[{name}] dataset={dataset}, marker={marker}")

    # Primary search: target dataset
    q = (
        f"dataset = {dataset} "
        f"| filter {marker_field} contains \"{marker}\" "
        f"| fields _time, _raw_log, xdm.event.type, xdm.event.outcome, "
        f"         xdm.source.ipv4, xdm.target.ipv4, xdm.source.user.username "
        f"| limit 3"
    )
    try:
        r = xql(q)
        reply = r.get("reply", {})
        status = reply.get("status", "?")
        n = reply.get("number_of_results", 0)
        if status == "SUCCESS" and n > 0:
            row = reply["results"]["data"][0]
            populated = {k: v for k, v in row.items() if v not in (None, "", "null")}
            print(f"  ✅ LANDED in {dataset} (n={n}, {len(populated)} populated cols)")
            for k in ("_raw_log", "xdm.event.type", "xdm.event.outcome", "xdm.source.ipv4", "xdm.target.ipv4", "xdm.source.user.username"):
                v = row.get(k)
                if v not in (None, "", "null"):
                    print(f"    {k:35} = {str(v)[:80]}")
            results.append({"name": name, "dataset": dataset, "status": "LANDED_MR_FIRED", "n": n, "populated": len(populated)})
        elif status == "SUCCESS" and n == 0:
            print(f"  ⊘ dataset EXISTS but no row matched marker (status=SUCCESS, n=0)")
            print(f"  Probing for raw event landing without marker filter...")
            q_raw = f"dataset = {dataset} | limit 1 | fields _time, _raw_log"
            r2 = xql(q_raw)
            n2 = r2.get("reply", {}).get("number_of_results", 0)
            if n2 > 0:
                results.append({"name": name, "dataset": dataset, "status": "DATASET_EMPTY_OR_MARKER_LOST", "n": 0, "populated": 0})
                print(f"    ↳ dataset has data ({n2} sample row) but our marker didn't reach. Either:")
                print(f"      (a) broker dropped/dropped vendor tag, or")
                print(f"      (b) PR/MR didn't preserve the marker field shape")
            else:
                results.append({"name": name, "dataset": dataset, "status": "DATASET_EXISTS_BUT_EMPTY", "n": 0, "populated": 0})
        elif status == "FAIL":
            print(f"  ✗ DATASET DOES NOT EXIST (status=FAIL) — upstream Cortex pack not installed in tenant")
            results.append({"name": name, "dataset": dataset, "status": "DATASET_MISSING", "n": 0, "populated": 0})
        else:
            print(f"  ? unexpected status={status}, n={n}")
            results.append({"name": name, "dataset": dataset, "status": f"UNKNOWN_{status}", "n": n, "populated": 0})
    except Exception as e:
        print(f"  ⚠ XQL error: {type(e).__name__}: {str(e)[:120]}")
        results.append({"name": name, "dataset": dataset, "status": "XQL_ERROR", "n": 0, "populated": 0})


# ============================================================
# Summary
# ============================================================

print("\n" + "=" * 70)
print("BATCH 2 SUMMARY")
print("=" * 70)
print(f"  {'vendor':<32}  {'dataset':<30}  result")
print(f"  {'-'*32}  {'-'*30}  ------")
for r in results:
    icon = {"LANDED_MR_FIRED": "✅", "DATASET_EMPTY_OR_MARKER_LOST": "⚠", "DATASET_EXISTS_BUT_EMPTY": "⊘", "DATASET_MISSING": "✗"}.get(r["status"], "?")
    print(f"  {icon} {r['name']:<30}  {r['dataset']:<30}  {r['status']}")

print()
landed = sum(1 for r in results if r["status"] == "LANDED_MR_FIRED")
empty = sum(1 for r in results if r["status"] == "DATASET_EMPTY_OR_MARKER_LOST")
missing = sum(1 for r in results if r["status"] == "DATASET_MISSING")
print(f"  {landed}/{len(results)} fully landed, {empty}/{len(results)} broker-tagging gaps, {missing}/{len(results)} upstream pack missing")
