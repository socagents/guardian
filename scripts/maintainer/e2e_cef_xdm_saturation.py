#!/usr/bin/env python3
"""CEF XDM saturation v2 — use the v1 raw payloads (already landed) but
query DM correctly via `datamodel dataset = X | filter <xdm.field> ...`.

Also drops Fortiweb (dataset doesn't exist in operator tenant) and adjusts
TrendMicro cefName to carry the marker.
"""
import json, os, socket, time, urllib.request
from datetime import datetime, timezone

BROKER = ("10.10.0.8", 514)
TOKEN = os.environ["MCP_TOKEN"]
XSIAM_MCP = "http://phantom-connector-xsiam-Cortex_XSIAM:9000/mcp"

BATCH = int(time.time())
ts_bsd = datetime.now(timezone.utc).strftime("%b %d %H:%M:%S")
rt_ms = BATCH * 1000


def cef(vendor, product, version, ev_id, name, sev, ext):
    kv = " ".join(f"{k}={v}" for k, v in ext.items())
    return (f"<134>{ts_bsd} smoke-host CEF:0|{vendor}|{product}|{version}|"
            f"{ev_id}|{name}|{sev}|{kv}")


# ============================================================
# Pack 1: Check Point VPN-1 & FireWall-1
# ============================================================
def cp_payload(marker):
    return cef(
        "Check Point", "VPN-1 & FireWall-1", "R80.40",
        "Log", "VPN-1 & FireWall-1 Log", "3",
        {
            "rt": rt_ms,
            "loguid": "{0x0,0x" + f"{BATCH:x}" + ",0x0,0x0}",
            "cefDeviceEventClassId": "Log",
            "cefDeviceVersion": "R80.40",
            "reason": "Connection_allowed_by_policy",
            "action_reason": "Permitted_by_rule_17",
            "session_id_": f"sess-{BATCH}-final",
            "session_id": f"sess-{BATCH}",
            "proto": "6",  "app": "https",  "service_id": "tcp/443",
            "cs2Label": "Rule Name",
            "cs2": f"Allow_HTTPS-{marker}",
            "cs3Label": "Protection Type",
            "cs3": "Signature_Block",
            "duration": "12",
            "cn1Label": "Elapsed Time in Seconds",
            "cn1": "12",
            "dns_type": "A",
            "dns_query": "example.com",
            "act": "Accept",  "origin": "fw-gw-01",
            "shost": "client.example.com",  "suser": "jdoe",
            "src": "192.0.2.45",  "spt": "54321",  "inzone": "Internal",
            "dhost": "target.example.com",  "duser": "admin",
            "dst": "198.51.100.7",  "dpt": "443",  "outzone": "External",
            "cn2Label": "ICMP Type",  "cn2": "8",
            "cn3Label": "ICMP Code",  "cn3": "0",
            "out": "4096",  "in": "8192",
            "msg": f"Connection_allowed_marker_{marker}",
            "ifname": "eth1",
            "client_outbound_packets": "12",
            "server_outbound_packets": "18",
        }
    )


CP_XDM = [
    "xdm.event.id", "xdm.event.type", "xdm.event.outcome_reason",
    "xdm.network.session_id", "xdm.network.ip_protocol",
    "xdm.network.application_protocol", "xdm.network.rule",
    "xdm.event.duration", "xdm.network.dns.dns_question.type",
    "xdm.network.dns.dns_resource_record.type", "xdm.observer.action",
    "xdm.observer.version", "xdm.observer.name", "xdm.source.host.hostname",
    "xdm.source.user.username", "xdm.source.ipv4", "xdm.source.port",
    "xdm.source.zone", "xdm.target.host.hostname", "xdm.target.user.username",
    "xdm.target.ipv4", "xdm.target.port", "xdm.target.zone",
    "xdm.network.icmp.type", "xdm.network.icmp.code", "xdm.source.sent_bytes",
    "xdm.target.sent_bytes", "xdm.event.description", "xdm.source.interface",
    "xdm.source.sent_packets", "xdm.target.sent_packets"
]


# ============================================================
# Pack 2: Cisco Firepower
# ============================================================
def fp_payload(marker):
    return cef(
        "Cisco", "Firepower", "6.7",
        "IDS-1", "Threat Detected", "4",
        {
            "rt": rt_ms,
            "dpt": "443",  "spt": "54321",
            "bytesIn": "8192", "bytesOut": "4096",
            "act": "Block",  "app": "https",
            "cs2": f"FP_Rule-{marker}",
            "cs3": "DMZ",  "cs4": "External",  "cs5": "Medium",
            "src": "192.0.2.45",  "dst": "198.51.100.7",
            "suser": "jdoe",  "duser": "admin",
            "dvcpid": "12345",
            "reason": "Threat_signature_match",
            "requestClientApplication": "Mozilla/5.0",
            "deviceOutboundInterface": "GigabitEthernet0/1",
            "deviceInboundInterface": "GigabitEthernet0/2",
            "deviceExternalId": "FP-DEV-001",
            "cefSeverity": "4",
            "externalId": f"ext-{marker}",
            "request": "https://target.example.com/login",
            "dvchost": "fp-sensor-01",
            "outcome": "blocked",
            "cefName": "Threat Detected",
            "cefDeviceVendor": "Cisco",  "cefDeviceProduct": "Firepower",
            "fname": "evil.exe",
            "fileHash": "d41d8cd98f00b204e9800998ecf8427e",
            "fileType": "PE32",
        }
    )


FP_XDM = [
    "xdm.target.port", "xdm.source.port", "xdm.target.sent_bytes",
    "xdm.source.sent_bytes", "xdm.observer.action",
    "xdm.network.application_protocol", "xdm.network.rule",
    "xdm.source.zone", "xdm.target.zone", "xdm.alert.category",
    "xdm.source.ipv4", "xdm.target.ipv4", "xdm.source.user.username",
    "xdm.target.user.username", "xdm.source.process.pid",
    "xdm.event.outcome_reason", "xdm.source.application.name",
    "xdm.source.interface", "xdm.target.interface",
    "xdm.observer.unique_identifier", "xdm.alert.severity", "xdm.event.id",
    "xdm.network.http.url", "xdm.observer.name", "xdm.event.outcome",
    "xdm.event.type", "xdm.observer.vendor", "xdm.observer.product",
    "xdm.target.file.filename", "xdm.target.file.md5", "xdm.target.file.file_type"
]


# ============================================================
# Pack 3: Trend Micro DS Agent (FW category)
#   FIX v2: marker in cefName so it propagates to xdm.alert.name + xdm.event.description
# ============================================================
def tm_payload(marker):
    return cef(
        "Trend Micro", "Deep Security Agent", "20.0.0",
        "105", f"Recon-{marker}", "6",         # ← cefName carries marker
        {
            "rt": rt_ms,
            "TrendMicroDsTenant": "TenantA",
            "TrendMicroDsTenantId": "tenant-uuid-001",
            "TrendMicroDsTags": "smoke_tag,test_run",
            "cefDeviceVersion": "20.0.0",
            "cefSeverity": "6",
            "dvc": "192.0.2.45",
            "dvchost": "tm-agent-01",
            "cn1": "100042",
            "act": "Drop",
            "src": "192.0.2.45",  "dst": "198.51.100.7",
            "spt": "54321",  "dpt": "443",
            "smac": "00:11:22:33:44:55",
            "dmac": "AA:BB:CC:DD:EE:FF",
            "out": "4096",  "in": "8192",  "cnt": "3",
            "proto": "TCP",
            "cs4": "8 0",                       # ← clean icmp type/code only
        }
    )


TM_XDM = [
    "xdm.observer.type", "xdm.observer.unique_identifier",
    "xdm.observer.version", "xdm.event.id", "xdm.event.description",
    "xdm.event.tags", "xdm.alert.name", "xdm.alert.severity",
    "xdm.source.agent.type", "xdm.source.agent.identifier",
    "xdm.observer.name", "xdm.source.ipv4", "xdm.source.host.hostname",
    "xdm.source.host.device_id", "xdm.observer.action", "xdm.event.outcome",
    "xdm.event.type", "xdm.source.interface", "xdm.source.port",
    "xdm.source.sent_packets", "xdm.source.sent_bytes",
    "xdm.target.sent_bytes", "xdm.target.ipv4", "xdm.target.port",
    "xdm.target.interface", "xdm.network.icmp.type", "xdm.network.icmp.code",
    "xdm.network.ip_protocol"
]


# ============================================================
# Pack 4: ManageEngine ADAuditPlus
# ============================================================
def me_payload(marker):
    return cef(
        "ManageEngine", "ADAuditPlus", "7.0",
        "USER_LOGON_SUCCESS", f"UserLogon-{marker}", "3",
        {
            "rt": rt_ms,
            "cn1": "42",  "cn2": "100",  "cn3": "200",
            "cs1": "Logon",  "type": "AccountLogon",
            "cs2": "192.0.2.45",
            "shost": "dc-01.example.com",
            "cs3": "wks-01.example.com",
            "cs4": "InteractiveLogon",
            "cs5": "High",  "cefSeverity": "6",
            "msg": f"User_logon_success_marker_{marker}",
            "duid": "S-1-5-21-target-admin",
            "suid": "S-1-5-21-source-jdoe",
            "duser": "admin",  "sproc": "lsass.exe",  "suser": "jdoe",
            "reason": "Interactive_logon",
            "sntdom": "EXAMPLE.COM",
            "cefName": "UserLogonSuccess",
            "cat": "Auth",  "outcome": "Success",
            "fileName": "ntds.dit",
            "filePath": "C:\\Windows\\NTDS\\ntds.dit",
            "fileLocation": "C:\\Windows\\NTDS",
            "cefDeviceVendor": "ManageEngine",
            "cefDeviceProduct": "ADAuditPlus",
            "cefDeviceVersion": "7.0",
            "cefDeviceEventClassId": "USER_LOGON_SUCCESS",
        }
    )


# ============================================================
# Pack 5: Trend Micro Deep Security MANAGER (Manager — not Agent)
#   MR filter: cefDeviceProduct = "Deep Security Manager"
#   Sets xdm.event.type = "System" literally; target* depends on targetType
# ============================================================
def tm_mgr_payload(marker):
    return cef(
        "Trend Micro", "Deep Security Manager", "20.0.0",
        "601", f"SystemSettings-{marker}", "4",   # ← cefName carries marker
        {
            "rt": rt_ms,
            "TrendMicroDsTenant": "TenantA",
            "TrendMicroDsTenantId": "tenant-uuid-001",
            "TrendMicroDsTags": "admin_audit,smoke",
            "cefDeviceVersion": "20.0.0",
            "cefSeverity": "4",
            "msg": f"User updated system setting marker_{marker}",  # → alert.description
            "suser": "admin@example.com",
            "src": "192.0.2.45",
            "targetType": "USER",                    # → target.resource.type, drives user/host branch
            "targetID": "user-uuid-001",             # → target.resource.id, target.user.identifier
            "target": "alice@example.com",           # → target.resource.value, target.user.username
        }
    )


TM_MGR_XDM = [
    "xdm.observer.type", "xdm.observer.unique_identifier",
    "xdm.observer.version", "xdm.event.id", "xdm.event.description",
    "xdm.event.tags", "xdm.alert.name", "xdm.alert.severity",
    "xdm.source.agent.type", "xdm.source.agent.identifier",
    "xdm.event.type",                                   # literal "System"
    "xdm.alert.description", "xdm.source.user.username", "xdm.source.ipv4",
    "xdm.target.resource.type", "xdm.target.resource.id",
    "xdm.target.resource.value",
    "xdm.target.user.username", "xdm.target.user.identifier"
]


ME_XDM = [
    "xdm.session_context_id", "xdm.event.id", "xdm.source.ipv4",
    "xdm.source.host.hostname", "xdm.alert.subcategory",
    "xdm.alert.description", "xdm.target.user.identifier",
    "xdm.source.user.identifier", "xdm.event.type",
    "xdm.target.user.username", "xdm.source.process.name",
    "xdm.source.user.username", "xdm.event.outcome_reason",
    "xdm.source.user.domain", "xdm.alert.category", "xdm.event.outcome",
    "xdm.target.file.filename", "xdm.target.file.path",
    "xdm.alert.severity", "xdm.target.file.directory",
    "xdm.observer.vendor", "xdm.observer.product", "xdm.observer.version",
    "xdm.observer.type", "xdm.intermediate.host.hostname"
]


# Per-pack DM filter — picks XDM field that carries the unique marker
PACKS = {
    "checkpoint_vpn_fw": {
        "dataset": "check_point_vpn_1_firewall_1_raw",
        "payload": cp_payload,
        "xdm_fields": CP_XDM,
        "dm_filter_field": "xdm.network.rule",      # carries cs2 marker
    },
    "cisco_firepower": {
        "dataset": "cisco_firepower_raw",
        "payload": fp_payload,
        "xdm_fields": FP_XDM,
        "dm_filter_field": "xdm.network.rule",      # carries cs2 marker
    },
    "trend_micro_ds_agent": {
        "dataset": "trend_micro_deep_security_agent_raw",
        "payload": tm_payload,
        "xdm_fields": TM_XDM,
        "dm_filter_field": "xdm.alert.name",        # carries cefName marker
    },
    "manageengine_adaudit": {
        "dataset": "manageengine_adauditplus_raw",
        "payload": me_payload,
        "xdm_fields": ME_XDM,
        "dm_filter_field": "xdm.alert.description", # carries msg marker
    },
    "trend_micro_ds_manager": {
        "dataset": "trend_micro_deep_security_manager_raw",
        "payload": tm_mgr_payload,
        "xdm_fields": TM_MGR_XDM,
        "dm_filter_field": "xdm.alert.name",        # cefName carries marker
    },
}


def send_all(markers):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for key, spec in PACKS.items():
        marker = markers[key]
        msg = spec["payload"](marker)
        print(f"[{key}] len={len(msg)}  marker={marker}")
        for _ in range(3):
            sock.sendto(msg.encode(), BROKER)
    sock.close()


def post_mcp(body, sid=None):
    h = {"Authorization": "Bearer " + TOKEN,
         "Content-Type": "application/json",
         "Accept": "application/json, text/event-stream"}
    if sid:
        h["mcp-session-id"] = sid
    req = urllib.request.Request(XSIAM_MCP, data=json.dumps(body).encode(),
                                 headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read().decode(), resp.headers


def parse_sse(text):
    for ln in text.split("\n"):
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


def mcp_session():
    _, h = post_mcp({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                     "params": {"protocolVersion": "2024-11-05",
                                "capabilities": {},
                                "clientInfo": {"name": "s", "version": "1.0"}}})
    sid = h.get("mcp-session-id") or h.get("Mcp-Session-Id")
    post_mcp({"jsonrpc": "2.0", "method": "notifications/initialized",
              "params": {}}, sid)
    return sid


def xql(sid, q):
    body, _ = post_mcp({"jsonrpc": "2.0", "id": 99, "method": "tools/call",
                        "params": {"name": "run_xql_query",
                                   "arguments": {"request": {"query": q}}}}, sid)
    return parse_sse(body)


def query_pack(sid, key, spec, marker):
    dataset = spec["dataset"]
    xdm_fields = spec["xdm_fields"]
    filter_field = spec["dm_filter_field"]
    print(f"\n=== {key} → {dataset} ===")

    # Datamodel-first syntax with XDM-field marker filter
    fields_clause = ", ".join(xdm_fields)
    q_dm = (f'datamodel dataset = {dataset} | filter {filter_field} contains "{marker}" '
            f'| fields {fields_clause} | limit 1')
    rdm = xql(sid, q_dm)
    rep_dm = rdm.get("reply", {})

    if rep_dm.get("status") != "SUCCESS":
        # Fallback: sort by insert time + grab latest, find by marker substring
        q_fb = (f'datamodel dataset = {dataset} | sort desc _insert_time '
                f'| fields {fields_clause}, {filter_field} | limit 10')
        rdm = xql(sid, q_fb)
        rep_dm = rdm.get("reply", {})
        if rep_dm.get("status") == "SUCCESS":
            rows = rep_dm.get("results", {}).get("data", [])
            matched = next((r for r in rows
                            if marker in (str(r.get(filter_field, "")) or "")), None)
            if not matched:
                print(f"  ❌ DM: no row with {filter_field}~='{marker}' in latest 10")
                return None
            dm_row = matched
        else:
            print(f"  ❌ DM query failed: {rep_dm.get('error', {})}")
            return None
    else:
        if rep_dm.get("number_of_results", 0) == 0:
            print(f"  ⚠️ DM: 0 rows match filter")
            return None
        dm_row = rep_dm["results"]["data"][0]

    populated = {f: dm_row.get(f) for f in xdm_fields
                 if dm_row.get(f) not in (None, "", "null")}
    n_pop = len(populated)
    pct = 100 * n_pop // len(xdm_fields)
    print(f"  ✅ DM: {n_pop}/{len(xdm_fields)} XDM fields populated ({pct}%)")
    for k in list(populated.keys())[:8]:
        print(f"     [+] {k} = {populated[k]!r}")
    if n_pop > 8:
        print(f"     ... and {n_pop - 8} more populated")
    missing = [f for f in xdm_fields if f not in populated]
    if missing:
        print(f"  Missing ({len(missing)}): {', '.join(missing)}")
    return {
        "populated": n_pop, "total": len(xdm_fields), "pct": pct,
        "missing": missing,
    }


if __name__ == "__main__":
    markers = {k: f"{k}-{BATCH}" for k in PACKS}
    print(f"BATCH={BATCH}\n")

    send_all(markers)

    WAIT = 180
    print(f"\nWait {WAIT}s for broker → PR → MR ingestion...")
    for i in range(WAIT // 30):
        time.sleep(30)
        print(f"  +{(i+1)*30}s")

    sid = mcp_session()
    print(f"\nMCP session id = {sid}")

    results = {}
    for key, spec in PACKS.items():
        results[key] = query_pack(sid, key, spec, markers[key])

    print("\n\n================ SATURATION SUMMARY ================")
    print(f"{'pack':<24}{'populated':<14}{'%':<6}{'missing':<10}")
    for key, r in results.items():
        if r is None:
            print(f"{key:<24}{'?':<14}{'?':<6}{'(error)':<10}")
        else:
            print(f"{key:<24}{r['populated']}/{r['total']:<10}{r['pct']:<6}"
                  f"{len(r['missing'])}")
