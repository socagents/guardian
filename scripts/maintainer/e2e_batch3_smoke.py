#!/usr/bin/env python3
"""Batch 3 multi-vendor smoke — 2 syslog vendors + NGINX re-validation.

VENDORS:
  1. CitrixADC        (date format MM/DD/YYYY:HH:MM:SS GMT, target=citrix_adc_raw)
  2. McAfeeNSM        (date format YYYY-MM-DD HH:MM:SS UTC, target=mcafee_nsm_raw)
  3. NGINX            (re-validate prior wire_format_validated_routing_blocked finding)

Same UDP→broker→XSIAM path. Distinguishes status=FAIL (dataset missing) from
SUCCESS,n=0 (dataset exists but our marker didn't land — broker tagging issue).

This pass also fixes the batch2 status=? bug — uses a more defensive query
result-extraction path that captures any reply state including XQL errors.
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


# Citrix ADC — date format MM/DD/YYYY:HH:MM:SS GMT
citrix_ts = datetime.now(timezone.utc).strftime("%m/%d/%Y:%H:%M:%S")
CITRIX_MARKER = f"batch3-citrix-{BATCH}"
citrix_event = (
    f"<134> {citrix_ts} GMT citrix-adc-01 SSLVPN LOGIN INFO "
    f"User {CITRIX_MARKER}_user - Client_ip 10.5.5.10 - Source 10.5.5.10:443 - "
    f"Destination 10.10.10.10:443 - applicationName Workspace - "
    f"connectionId conn-{BATCH} - SessionId: 99999"
)

# McAfee NSM — date format YYYY-MM-DD HH:MM:SS UTC
mcafee_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
MCAFEE_MARKER = f"batch3-mcafee-{BATCH}"
mcafee_event = (
    f"<134>SyslogAlertForwarder Alert: corp-host-{MCAFEE_MARKER} detected "
    f"Test_Attack: (severity = High) 198.51.100.5:1234 -> 10.10.10.20:443 "
    f"at {mcafee_ts} UTC (result = blocked)"
)

# NGINX — access log format from wire_format_library
# <priority>MMM DD HH:MM:SS host nginx: <client-ip> - <user> [DD/Mon/YYYY:HH:MM:SS +nnnn] "METHOD /path HTTP/1.1" <status> <bytes>
nginx_ts_bsd = datetime.now(timezone.utc).strftime("%b %d %H:%M:%S")
nginx_ts_apache = datetime.now(timezone.utc).strftime("%d/%b/%Y:%H:%M:%S +0000")
NGINX_MARKER = f"batch3-nginx-{BATCH}"
nginx_event = (
    f"<190>{nginx_ts_bsd} nginx-host nginx: 198.51.100.7 - "
    f"{NGINX_MARKER}_user [{nginx_ts_apache}] "
    f"\"GET /api/v1/test?marker={NGINX_MARKER} HTTP/1.1\" 200 1024 "
    f"\"https://referrer.example/page\" \"Mozilla/5.0 batch3-smoke\""
)

SMOKES = [
    {"name": "CitrixADC",   "dataset": "citrix_adc_raw",  "event": citrix_event, "marker": CITRIX_MARKER, "marker_field": "_raw_log"},
    {"name": "McAfeeNSM",   "dataset": "mcafee_nsm_raw",  "event": mcafee_event, "marker": MCAFEE_MARKER, "marker_field": "_raw_log"},
    {"name": "NGINX",       "dataset": "nginx_nginx_raw", "event": nginx_event,  "marker": NGINX_MARKER,  "marker_field": "_raw_log"},
]

print("=" * 70)
print(f"BATCH 3 syslog smoke — Citrix + McAfee + NGINX  ({BATCH})")
print("=" * 70)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for s in SMOKES:
    e = s["event"]
    print(f"\n[{s['name']}]  → {BROKER[0]}:{BROKER[1]}  ({len(e)} bytes)")
    print(f"  marker={s['marker']}")
    print(f"  event[:140]={e[:140]}{'...' if len(e) > 140 else ''}")
    for _ in range(3):
        sock.sendto(e.encode(), BROKER)
sock.close()
print(f"\nAll events sent. Waiting 120s...")
for i in range(4):
    time.sleep(30)
    print(f"  +{(i+1)*30}s")


def post_mcp(body, sid=None):
    h = {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json",
         "Accept": "application/json, text/event-stream"}
    if sid:
        h["mcp-session-id"] = sid
    req = urllib.request.Request(XSIAM_MCP, data=json.dumps(body).encode(),
                                 headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read().decode(), resp.headers


def sse_parse(s):
    """Robust SSE parser: capture ANY data event, surface raw text on parse fail."""
    chunks = []
    for ln in s.split("\n"):
        ln = ln.strip()
        if ln.startswith("data:"):
            chunks.append(ln[5:].strip())
    for c in chunks:
        try:
            f = json.loads(c)
            if "result" in f:
                content = f["result"].get("content", [])
                if content:
                    text = content[0].get("text", "")
                    try:
                        return {"_parsed": json.loads(text), "_raw_text": text[:300]}
                    except Exception:
                        return {"_parse_error": "result-content not JSON", "_raw_text": text[:300]}
            elif "error" in f:
                return {"_xql_error": f["error"]}
        except Exception as e:
            return {"_sse_parse_error": str(e)[:200], "_chunk_sample": c[:200]}
    return {"_no_data_events": True, "_sample": s[:200]}


_, h = post_mcp({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                            "clientInfo": {"name": "batch3", "version": "1.0"}}})
sid = h.get("mcp-session-id") or h.get("Mcp-Session-Id")
post_mcp({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, sid)


def xql(q):
    body, _ = post_mcp({"jsonrpc": "2.0", "id": 99, "method": "tools/call",
                        "params": {"name": "run_xql_query",
                                   "arguments": {"request": {"query": q, "tenant_timeframe": {"relativeTime": 900000}}}}}, sid)
    return sse_parse(body)


print("\n" + "=" * 70)
print("VERIFICATION (XQL)")
print("=" * 70)

results = []
for s in SMOKES:
    name = s["name"]
    dataset = s["dataset"]
    marker = s["marker"]
    print(f"\n[{name}] dataset={dataset}, marker={marker}")

    # 1. Try filter by marker
    q1 = f'dataset = {dataset} | filter _raw_log contains "{marker}" | limit 3'
    r1 = xql(q1)
    parsed = r1.get("_parsed", {})
    reply = parsed.get("reply", {}) if isinstance(parsed, dict) else {}
    status1 = reply.get("status", r1.get("_xql_error", {}).get("message", "?") if r1.get("_xql_error") else "?")
    n1 = reply.get("number_of_results", 0)

    if isinstance(reply, dict) and reply.get("status") == "SUCCESS" and n1 > 0:
        row = reply["results"]["data"][0]
        cols = {k: v for k, v in row.items() if v not in (None, "", "null")}
        print(f"  ✅ LANDED in {dataset} (n={n1}, {len(cols)} populated columns)")
        for k in sorted(cols)[:8]:
            print(f"    {k:40} = {str(cols[k])[:80]}")
        results.append({"name": name, "dataset": dataset, "status": "LANDED_MR_FIRED", "n": n1})
        continue

    if isinstance(reply, dict) and reply.get("status") == "FAIL":
        print(f"  ✗ DATASET DOES NOT EXIST (status=FAIL)")
        results.append({"name": name, "dataset": dataset, "status": "DATASET_MISSING"})
        continue

    if isinstance(reply, dict) and reply.get("status") == "SUCCESS" and n1 == 0:
        # Probe: does the dataset have any recent rows at all?
        q2 = f"dataset = {dataset} | limit 1 | fields _time"
        r2 = xql(q2)
        parsed2 = r2.get("_parsed", {})
        reply2 = parsed2.get("reply", {}) if isinstance(parsed2, dict) else {}
        n2 = reply2.get("number_of_results", 0)
        if n2 > 0:
            print(f"  ⚠ dataset exists + has data, but marker not found (broker tagging gap?)")
            results.append({"name": name, "dataset": dataset, "status": "BROKER_TAGGING_GAP"})
        else:
            print(f"  ⊘ dataset exists, currently empty in 15-min window")
            results.append({"name": name, "dataset": dataset, "status": "DATASET_EMPTY"})
        continue

    # Fallback — surface what we got
    print(f"  ? unexpected. status={status1}, n={n1}, raw={r1}")
    results.append({"name": name, "dataset": dataset, "status": f"UNKNOWN_{status1}"})


print("\n" + "=" * 70)
print("BATCH 3 SUMMARY")
print("=" * 70)
print(f"  {'vendor':<25}  {'dataset':<25}  result")
print(f"  {'-'*25}  {'-'*25}  ------")
for r in results:
    icon = {"LANDED_MR_FIRED": "✅", "BROKER_TAGGING_GAP": "⚠", "DATASET_EMPTY": "⊘", "DATASET_MISSING": "✗"}.get(r["status"], "?")
    print(f"  {icon} {r['name']:<23}  {r['dataset']:<25}  {r['status']}")

landed = sum(1 for r in results if r["status"] == "LANDED_MR_FIRED")
print(f"\n  {landed}/{len(results)} fully landed")
