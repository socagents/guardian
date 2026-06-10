#!/usr/bin/env python3
"""FortiGate follow-up: send a small (<1500 bytes) event with ONLY the
fields that were missing from round 1. Proves UDP truncation was the
cause, not wire-format errors."""

import json, os, socket, time, urllib.request
from datetime import datetime, timezone

BROKER = ("10.10.0.8", 514)
TOKEN = os.environ["MCP_TOKEN"]
XSIAM_MCP = "http://phantom-connector-xsiam-Cortex_XSIAM:9000/mcp"

BATCH = int(time.time())
BATCH_NS = BATCH * 1_000_000_000
ts_bsd = datetime.now(timezone.utc).strftime("%b %d %H:%M:%S")
MARKER = f"fortigate-followup-{BATCH}"

# Just the missing fields plus minimal PR-filter satisfaction
ext = {
    "FTNTFGTeventtime": BATCH_NS,         # PR filter requirement
    "FTNTFGTduration": "1",
    # The missing 8 XDM-populating fields:
    "FTNTFGTapp": "Microsoft_Teams",      # → target.application.name
    "FTNTFGTappid": "5511",               # → target.application.name (concat appendix)
    "FTNTFGTfiletype": "msi",             # → target.file.file_type
    "FTNTFGTfilehash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # 64 = sha256
    "fsize": "8192",                      # → target.file.size
    "in": "16384",                        # → target.sent_bytes (SQL keyword)
    "FTNTFGTrcvdpkt": "42",               # → target.sent_packets
    "duser": "target_user",               # → target.user.username
    # Plus IPv6 VPN for intermediate.ipv6 + network.vpn.allocated_ipv6
    "FTNTFGTtunnelip": "2001:db8:vpn::1",  # IPv6 → vpn_tunnel_ipv6
    "FTNTFGTassignip": "2001:db8:vpn::2",  # IPv6 → vpn_tunnel_assigned_ipv6
    # Marker
    "msg": f"Followup_marker_{MARKER}",
}

kv = " ".join(f"{k}={v}" for k, v in ext.items())
msg = (
    f"<134>{ts_bsd} smoke-host CEF:0|Fortinet|Fortigate|7.4.4|"
    f"00000002|Followup_test|3|{kv}"
)
print(f"BATCH={BATCH}  MARKER={MARKER}")
print(f"Extensions: {len(ext)}, CEF length: {len(msg)} bytes")
print(f"  (under UDP MTU 1500: {'YES' if len(msg) < 1500 else 'NO'})")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for _ in range(3):
    sock.sendto(msg.encode(), BROKER)
sock.close()

print(f"\nWait 120s...")
for i in range(4):
    time.sleep(30)
    print(f"  +{(i+1)*30}s")


def post_mcp(body, sid=None):
    h = {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json",
         "Accept": "application/json, text/event-stream"}
    if sid: h["mcp-session-id"] = sid
    req = urllib.request.Request(XSIAM_MCP, data=json.dumps(body).encode(),
                                 headers=h, method="POST")
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
                    if c: return json.loads(c[0].get("text", "{}"))
            except: pass
    return {}


_, h = post_mcp({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                            "clientInfo": {"name": "f", "version": "1.0"}}})
sid = h.get("mcp-session-id") or h.get("Mcp-Session-Id")
post_mcp({"jsonrpc": "2.0", "method": "notifications/initialized",
          "params": {}}, sid)


def xql(sid, q):
    body, _ = post_mcp({"jsonrpc": "2.0", "id": 99, "method": "tools/call",
                        "params": {"name": "run_xql_query",
                                   "arguments": {"request": {"query": q}}}}, sid)
    return sse(body)


# Raw check
q_raw = f'dataset = fortinet_fortigate_raw | filter msg contains "{MARKER}" | limit 1'
r = xql(sid, q_raw)
reply = r.get("reply", {})
print(f"\n=== RAW ===")
if reply.get("status") == "SUCCESS" and reply.get("number_of_results", 0) > 0:
    row = reply["results"]["data"][0]
    populated_ext = {k: v for k, v in row.items()
                     if v not in (None, "", "null") and not k.startswith("_")}
    print(f"  ✅ raw landed with {len(populated_ext)} cols")
    # Show the followup-specific fields
    for k in ("FTNTFGTapp", "FTNTFGTappid", "FTNTFGTfiletype", "FTNTFGTfilehash",
              "fsize", "in", "FTNTFGTrcvdpkt", "duser", "FTNTFGTtunnelip",
              "FTNTFGTassignip"):
        v = row.get(k)
        if v not in (None, "", "null"):
            print(f"    raw.{k:25} = {str(v)[:60]}")
        else:
            print(f"    raw.{k:25} = (missing)")

# DM check — the 10 fields
TARGETS = ["xdm.target.application.name", "xdm.target.file.file_type",
           "xdm.target.file.md5", "xdm.target.file.sha256",
           "xdm.target.file.size", "xdm.target.sent_bytes",
           "xdm.target.sent_packets", "xdm.target.user.username",
           "xdm.intermediate.ipv6", "xdm.network.vpn.allocated_ipv6"]
fc = ", ".join(TARGETS)
q_dm = (f'datamodel dataset = fortinet_fortigate_raw '
        f'| filter xdm.event.description contains "{MARKER}" '
        f'| fields {fc} | limit 1')
rdm = xql(sid, q_dm)
rep_dm = rdm.get("reply", {})
print(f"\n=== DM ===")
if rep_dm.get("status") == "SUCCESS" and rep_dm.get("number_of_results", 0) > 0:
    dm_row = rep_dm["results"]["data"][0]
    n_pop = 0
    for f in TARGETS:
        v = dm_row.get(f)
        if v not in (None, "", "null"):
            print(f"  ✅ {f:40} = {str(v)[:60]}")
            n_pop += 1
        else:
            print(f"  ❌ {f:40} (still missing)")
    print(f"\n  Followup: {n_pop}/{len(TARGETS)} populated")
else:
    print(f"  ⚠️ DM no match  status={rep_dm.get('status')}")
