#!/usr/bin/env python3
"""FortiGate XDM saturation harness.

Sends a comprehensive CEF event with ~130 FTNTFGT* extensions designed
to populate every XDM target the modeling rule defines (~116 targets).

PR critical requirements:
  - CEF header: vendor=Fortinet, product=Fortigate (exact case)
  - FTNTFGTeventtime: 19-digit nanosecond epoch (PR filter strips last 9
    digits as fractional seconds + subtracts FTNTFGTduration)
  - Field whitelist: only FTNTFG* + ~30 CEF dictionary fields survive

Marker placement: `msg` → `xdm.event.description` (used for DM query filter).
"""

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
BATCH_NS = BATCH * 1_000_000_000  # 19-digit nanoseconds (PR filter requirement)
ts_bsd = datetime.now(timezone.utc).strftime("%b %d %H:%M:%S")
MARKER = f"fortigate-saturation-{BATCH}"


def build_extensions():
    """Build the full FortiGate CEF extension dict."""
    return {
        # ===== PR critical =====
        "FTNTFGTeventtime": BATCH_NS,             # PR filter requires 19+ digit epoch
        "FTNTFGTduration": "12",                   # Event duration in seconds

        # ===== Alert (8 XDM targets) =====
        "FTNTFGTviruscat": "Phishing",             # → xdm.alert.category
        "FTNTFGTref": f"Reference_doc_{MARKER}",   # → xdm.alert.description
        "FTNTFGTincidentserialno": f"INC-{BATCH}", # → xdm.alert.original_alert_id
        "FTNTFGTattackid": "12345",                # → coalesce → xdm.alert.original_threat_id
        "FTNTFGTvirusid": "67890",
        "FTNTFGTvulnid": "11111",
        "FTNTFGTcveid": "CVE-2026-1234",
        "FTNTFGTattack": "SQL_Injection",          # → coalesce → xdm.alert.original_threat_name
        "FTNTFGTvirus": "Test_Virus.exe",
        "FTNTFGTvulnname": "Vuln_Name",
        "FTNTFGTthreattype": "Malware",
        "FTNTFGTCRlevel": "high",                  # → coalesce → xdm.alert.severity (preferred)
        "FTNTFGTseverity": "medium",
        "FTNTFGTapprisk": "elevated",
        "FTNTFGTlogdesc": "Test_subcategory",      # → xdm.alert.subcategory

        # ===== Event (8 XDM targets) =====
        "msg": f"Saturation_event_marker_{MARKER}",  # → xdm.event.description (MARKER)
        "FTNTFGTlogid": f"LOG-{BATCH}",             # → xdm.event.id
        "FTNTFGTlevel": "warning",                  # → xdm.event.log_level (also via cef_pri_level)
        "cefSeverity": "4",                          # → xdm.event.log_level (alt path)
        "FTNTFGTsubtype": "system",                  # → xdm.event.operation_sub_type AND .type
        "outcome": "success",                        # → xdm.event.outcome (preferred branch)
        "FTNTFGTresult": "OK",                       # → xdm.event.outcome (fallback)
        "reason": "Connection_permitted",            # → xdm.event.outcome_reason (preferred)
        "FTNTFGTerror": "no_error",
        "FTNTFGTerror_num": "0",

        # ===== Intermediate VPN/AP (10 XDM targets) =====
        "FTNTFGTtunnelid": "tunnel-001",             # → xdm.intermediate.host.device_id
        "FTNTFGTapsn": "AP-SN-001",                  # → coalesce → host.hardware_uuid
        "FTNTFGTsnclosest": "AP-SN-002",
        "FTNTFGTvpntunnel": "vpn-tunnel-01",         # → coalesce → host.hostname
        "FTNTFGTap": "ap-01",
        "FTNTFGTbssid": "00:11:22:33:44:55",         # → host.mac_addresses (regex-filtered)
        "FTNTFGTstamac": "AA:BB:CC:DD:EE:FF",
        "FTNTFGTassignip": "10.0.0.10",              # → vpn_tunnel_assigned_ipv4 → intermediate.ipv4
        "FTNTFGTtunnelip": "10.0.0.20",              # → vpn_tunnel_ipv4 (also src_ip_addresses)
        "FTNTFGTgateway": "192.168.1.1",             # → ppp_gateway_ipv4 → intermediate
        "FTNTFGTopercountry": "United_States",       # → intermediate.location.country
        "FTNTFGTxauthgroup": "vpn_admins",           # → intermediate.user.groups (must != N/A)
        "FTNTFGTxauthuser": "N/A",                   # → intermediate.user.username (MR bug: must equal N/A)

        # ===== Network application (2 XDM targets) =====
        "app": "https",                              # → coalesce → xdm.network.application_protocol
        "FTNTFGTmethod": "GET",
        "FTNTFGTvoip_proto": "sip",
        "FTNTFGTappcat": "Web.Browsing",             # → xdm.network.application_protocol_category

        # ===== Network DHCP (2 XDM targets) =====
        "FTNTFGTdhcp_msg": "DISCOVER",               # → uppercase → DHCP_MESSAGE_TYPE_DHCPDISCOVER
        "FTNTFGTlease": "86400",                     # → xdm.network.dhcp.lease

        # ===== Network DNS (7 XDM targets) =====
        "FTNTFGTqclass": "IN",                       # → dns_record_class=1
        "FTNTFGTqname": "example.com",
        "FTNTFGTqtype": "A",                         # → DNS_RECORD_TYPE_A
        "FTNTFGTipaddr": "93.184.216.34",
        "FTNTFGTeventtype": "dns-response",          # → xdm.network.dns.is_response=true

        # ===== Network HTTP (6 XDM targets) =====
        "FTNTFGTforwardedfor": "192.0.2.1",          # → http.http_header.value + header=X-Forwarded-For
        "FTNTFGThttpmethod": "GET",                  # → HTTP_METHOD_GET
        "FTNTFGTreferralurl": "https://referrer.example.com/",
        "FTNTFGThttpcode": "200",                    # → HTTP_RSP_CODE_OK
        "request": "/api/v1/test",                   # → target_url construction (must start with /)
        "requestContext": "Web.Browsing",            # → url_category (non-"unknown" to populate)
        "requestClientApplication": "Mozilla_5.0_test_agent",
        "requestCookies": "session_test123",

        # ===== Network ICMP (2 XDM targets — labels are swapped in MR) =====
        "FTNTFGTicmptype": "0x8",                    # echo request — note: maps to xdm.network.icmp.code (MR bug)
        "FTNTFGTicmpcode": "0x0",                    # → xdm.network.icmp.type (MR bug)

        # ===== Network ip_protocol + rule (2 XDM targets) =====
        "proto": "6",                                # → IP_PROTOCOL_TCP
        "FTNTFGTpolicyname": f"saturation_policy_{BATCH}",  # part of network_rules array
        "FTNTFGTprofile": "Default_Profile",
        "FTNTFGTapplist": "default_applist",
        "FTNTFGTpolicy_id": "100",
        "FTNTFGTpolicyid": "100",
        "FTNTFGTshapingpolicyid": "10",

        # ===== Network session/TLS/VPN (7 XDM targets) =====
        "externalId": f"sess-{BATCH}",               # → xdm.network.session_id AND xdm.session_context_id
        "FTNTFGTcipher": "TLS_AES_256_GCM_SHA384",
        "FTNTFGTccertissuer": "CN=Client_CA",
        "FTNTFGTtlsver": "TLSv1.3",
        "FTNTFGTscertissuer": "CN=Server_CA",
        "FTNTFGTscertcname": "target.example.com",

        # ===== Observer (5 XDM targets) =====
        "act": "block",                              # → coalesce → xdm.observer.action
        "FTNTFGTsslaction": "ssl-deny",
        "FTNTFGTutmaction": "blocked",
        "dvchost": "fortigate-fw-01",                # → xdm.observer.name (preferred)
        "deviceExternalId": "FGT-DEV-001",           # → xdm.observer.unique_identifier
        "cat": "26",                                  # → cat_string → "Malicious Websites" (FortiGuard cat code)
        "cefDeviceVersion": "7.4.4",                 # → xdm.observer.version

        # ===== Source host (10 XDM targets) =====
        "FTNTFGTdevtype": "Workstation",             # → source.host.device_category
        "FTNTFGTsrcfamily": "Windows",
        "FTNTFGTsrcuuid": "src-uuid-001",            # → source.host.device_id
        "shost": "client.example.com",               # → source.host.fqdn AND .hostname
        "FTNTFGTmastersrcmac": "00:11:22:33:44:55",
        "FTNTFGTsrcmac": "00:11:22:33:44:56",
        "FTNTFGTtamac": "00:11:22:33:44:57",
        "FTNTFGTsrchwvendor": "Dell",
        "FTNTFGTmanuf": "Dell_Inc",
        "FTNTFGTosname": "Windows_10",               # → src_os → OS_FAMILY_WINDOWS

        # ===== Source IP/port (4 XDM targets — plus host.ipv4_addresses arrays) =====
        "src": "192.0.2.45",                         # → src_ip_addresses → xdm.source.ipv4
        "sourceTranslatedAddress": "203.0.113.45",   # → xdm.source.host.ipv4_public_addresses
        "FTNTFGTnat": "203.0.113.45",
        "FTNTFGTsaddr": "192.0.2.45",
        "FTNTFGTlocal": "10.0.0.45",
        "FTNTFGTtrueclntip": "192.0.2.50",
        "FTNTFGTassigned": "10.0.1.45",
        "FTNTFGTbanned_src": "192.0.2.99",
        "c6a2": "2001:db8::1",                       # → xdm.source.ipv6 (first IPv6)
        "spt": "54321",                              # → coalesce → xdm.source.port
        "FTNTFGTpsrcport": "54322",
        "sourceTranslatedPort": "55000",

        # ===== Source location (3 XDM targets) =====
        "FTNTFGTsrccity": "San_Francisco",
        "FTNTFGTsrccountry": "United_States",
        "FTNTFGTsrcregion": "CA",

        # ===== Source process + bytes (4 XDM targets) =====
        "sproc": "chrome.exe",                       # → xdm.source.process.name
        "fname": "downloaded_file.exe",              # → source.process.executable.filename AND target.file.filename
        "out": "4096",                               # → xdm.source.sent_bytes
        "FTNTFGTsentpkt": "10",                      # → xdm.source.sent_packets

        # ===== Source user (5 XDM targets) =====
        "suser": "jdoe",                             # → coalesce → xdm.source.user.username (preferred)
        "FTNTFGTlogin": "jdoe_login",
        "FTNTFGinitiator": "jdoe_init",              # NOTE: missing T (MR typo)
        "FTNTFGTunauthuser": "anonymous",
        "FTNTFGTvd": "root_vdom",                    # → xdm.source.user.domain
        "FTNTFGTgroup": "users",                     # → user.groups (must != N/A)
        "FTNTFGTadgroup": "domain_users",
        "FTNTFGTfctuid": "fct-uuid-001",             # → xdm.source.user.identifier

        # ===== Target host (12 XDM targets) =====
        "FTNTFGTdstdevtype": "Server",               # → target.host.device_category
        "FTNTFGTdstfamily": "Linux",
        "FTNTFGTdsthwversion": "v2.0",               # → target.host.device_model
        "dhost": "target.example.com",               # → target.host.fqdn AND .hostname (preferred)
        "FTNTFGTserialno": "SN-001",                 # → coalesce → target.host.hardware_uuid
        "FTNTFGTsn": "SN-002",
        "FTNTFGTdst_host": "internal.example.com",
        "FTNTFGTdstauthserver": "auth-server.example.com",
        "FTNTFGTmasterdstmac": "AA:BB:CC:DD:EE:00",
        "FTNTFGTdstmac": "AA:BB:CC:DD:EE:01",
        "FTNTFGTinvalidmac": "AA:BB:CC:DD:EE:02",
        "FTNTFGTdsthwvendor": "Cisco",               # → target.host.manufacturer
        "FTNTFGTdstosname": "Ubuntu_22.04",          # → dst_os → OS_FAMILY_UBUNTU

        # ===== Target IP/port (4 XDM targets) =====
        "dst": "198.51.100.7",                       # → dst_ip_address array → target.ipv4
        "FTNTFGTdaddr": "198.51.100.8",
        "FTNTFGTserver": "198.51.100.10",
        "FTNTFGTremote": "198.51.100.15",
        "c6a3": "2001:db8::2",                       # → IPv6 in dst array → target.ipv6
        "dpt": "443",                                # → coalesce → target.port
        "FTNTFGTpdstport": "444",

        # ===== Target location (3 XDM targets) =====
        "FTNTFGTdstcity": "New_York",
        "FTNTFGTdstcountry": "United_States",
        "FTNTFGTdstregion": "NY",

        # ===== Target process/resource (5 XDM targets) =====
        "FTNTFGTcommand": "wget_https_example_com",
        "FTNTFGToldvalue": "old_value_1",            # → coalesce → target.resource_before.value
        "FTNTFGTold_value": "old_value_2",
        "FTNTFGTold_status": "disabled",
        "FTNTFGToldwprof": "old_profile",
        "FTNTFGTcfgattr": "config_attribute",        # → coalesce → target.resource.name
        "FTNTFGTpoolname": "pool_01",
        "FTNTFGTauditreporttype": "audit_report",    # → coalesce → target.resource.type
        "FTNTFGTreporttype": "summary_report",
        "FTNTFGTcfgpath": "system_global",
        "FTNTFGTnewvalue": "new_value_1",            # → coalesce → target.resource.value
        "FTNTFGTnew_value": "new_value_2",
        "FTNTFGTnew_status": "enabled",
        "FTNTFGTcfgobj": "config_obj",

        # ===== Target file (3 XDM targets — SHA256 chosen over MD5) =====
        "FTNTFGTfiletype": "executable",             # → target.file.file_type
        "FTNTFGTfilehash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # 64 chars = SHA256
        "fsize": "2048",                             # → target.file.size

        # ===== Target bytes/packets (2 XDM targets) =====
        "in": "8192",                                # → target.sent_bytes (note: backtick in MR `in`)
        "FTNTFGTrcvdpkt": "15",                      # → target.sent_packets

        # ===== Target URL/user (2 XDM targets) =====
        "duser": "admin",                            # → coalesce → target.user.username (preferred)
        "FTNTFGTdstuser": "admin_dst",
        "FTNTFGTdstunauthuser": "guest",

        # ===== Target application =====
        "FTNTFGTappid": "12345",                     # → target.application.name (with FTNTFGTapp)
        "FTNTFGTapp": "Google_Drive",
    }


def cef_message(extensions: dict) -> str:
    """Build syslog-framed CEF message."""
    kv = " ".join(f"{k}={v}" for k, v in extensions.items())
    return (
        f"<134>{ts_bsd} smoke-host CEF:0|Fortinet|Fortigate|7.4.4|"
        f"00000001|VPN_connection_established|3|{kv}"
    )


# ============================================================
# Send
# ============================================================

ext = build_extensions()
msg = cef_message(ext)
print(f"BATCH={BATCH}  MARKER={MARKER}")
print(f"Extensions count: {len(ext)}")
print(f"Total CEF length: {len(msg)} bytes")
print(f"First 250 chars: {msg[:250]}...")
print()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for i in range(3):
    sock.sendto(msg.encode(), BROKER)
sock.close()
print(f"Sent 3x UDP to {BROKER}")

# ============================================================
# Wait + query DM
# ============================================================

WAIT = 180
print(f"\nWaiting {WAIT}s for broker → PR → MR pipeline...")
for i in range(WAIT // 30):
    time.sleep(30)
    print(f"  +{(i+1)*30}s")


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
                                "clientInfo": {"name": "f", "version": "1.0"}}})
    sid = h.get("mcp-session-id") or h.get("Mcp-Session-Id")
    post_mcp({"jsonrpc": "2.0", "method": "notifications/initialized",
              "params": {}}, sid)
    return sid


def xql(sid, q):
    body, _ = post_mcp({"jsonrpc": "2.0", "id": 99, "method": "tools/call",
                        "params": {"name": "run_xql_query",
                                   "arguments": {"request": {"query": q}}}}, sid)
    return parse_sse(body)


sid = mcp_session()
print(f"\nMCP session id = {sid}")

# Full list of XDM targets from FortiGate MR (116 total)
XDM_FIELDS = [
    "xdm.alert.category", "xdm.alert.description", "xdm.alert.original_alert_id",
    "xdm.alert.original_threat_id", "xdm.alert.original_threat_name",
    "xdm.alert.risks", "xdm.alert.severity", "xdm.alert.subcategory",
    "xdm.event.description", "xdm.event.duration", "xdm.event.id",
    "xdm.event.is_completed", "xdm.event.log_level", "xdm.event.operation_sub_type",
    "xdm.event.outcome", "xdm.event.outcome_reason", "xdm.event.type",
    "xdm.intermediate.host.device_id", "xdm.intermediate.host.hardware_uuid",
    "xdm.intermediate.host.hostname", "xdm.intermediate.host.ipv4_addresses",
    "xdm.intermediate.host.ipv4_public_addresses",
    "xdm.intermediate.host.ipv6_addresses", "xdm.intermediate.host.mac_addresses",
    "xdm.intermediate.ipv4", "xdm.intermediate.ipv6",
    "xdm.intermediate.location.country", "xdm.intermediate.user.groups",
    "xdm.intermediate.user.username", "xdm.network.application_protocol",
    "xdm.network.application_protocol_category", "xdm.network.dhcp.lease",
    "xdm.network.dhcp.message_type", "xdm.network.dns.dns_question.class",
    "xdm.network.dns.dns_question.name", "xdm.network.dns.dns_question.type",
    "xdm.network.dns.dns_resource_record.class",
    "xdm.network.dns.dns_resource_record.name",
    "xdm.network.dns.dns_resource_record.type",
    "xdm.network.dns.dns_resource_record.value", "xdm.network.dns.is_response",
    "xdm.network.http.http_header.header", "xdm.network.http.http_header.value",
    "xdm.network.http.method", "xdm.network.http.referrer",
    "xdm.network.http.response_code", "xdm.network.http.url",
    "xdm.network.http.url_category", "xdm.network.icmp.code",
    "xdm.network.icmp.type", "xdm.network.ip_protocol", "xdm.network.rule",
    "xdm.network.session_id", "xdm.network.tls.cipher",
    "xdm.network.tls.client_certificate.issuer",
    "xdm.network.tls.protocol_version",
    "xdm.network.tls.server_certificate.issuer",
    "xdm.network.tls.server_name", "xdm.network.vpn.allocated_ipv4",
    "xdm.network.vpn.allocated_ipv6", "xdm.observer.action", "xdm.observer.name",
    "xdm.observer.type", "xdm.observer.unique_identifier",
    "xdm.observer.version", "xdm.session_context_id",
    "xdm.source.host.device_category", "xdm.source.host.device_id",
    "xdm.source.host.fqdn", "xdm.source.host.hostname",
    "xdm.source.host.ipv4_addresses", "xdm.source.host.ipv4_public_addresses",
    "xdm.source.host.ipv6_addresses", "xdm.source.host.mac_addresses",
    "xdm.source.host.manufacturer", "xdm.source.host.os",
    "xdm.source.host.os_family", "xdm.source.interface", "xdm.source.ipv4",
    "xdm.source.ipv6", "xdm.source.location.city", "xdm.source.location.country",
    "xdm.source.location.region", "xdm.source.port",
    "xdm.source.process.executable.filename", "xdm.source.process.name",
    "xdm.source.sent_bytes", "xdm.source.sent_packets", "xdm.source.user.domain",
    "xdm.source.user.groups", "xdm.source.user.identifier",
    "xdm.source.user.username", "xdm.source.user_agent",
    "xdm.target.application.name", "xdm.target.file.file_type",
    "xdm.target.file.filename", "xdm.target.file.md5", "xdm.target.file.sha256",
    "xdm.target.file.size", "xdm.target.host.device_category",
    "xdm.target.host.device_model", "xdm.target.host.fqdn",
    "xdm.target.host.hardware_uuid", "xdm.target.host.hostname",
    "xdm.target.host.ipv4_addresses", "xdm.target.host.ipv4_public_addresses",
    "xdm.target.host.ipv6_addresses", "xdm.target.host.mac_addresses",
    "xdm.target.host.manufacturer", "xdm.target.host.os",
    "xdm.target.host.os_family", "xdm.target.interface", "xdm.target.ipv4",
    "xdm.target.ipv6", "xdm.target.location.city", "xdm.target.location.country",
    "xdm.target.location.region", "xdm.target.port",
    "xdm.target.process.command_line", "xdm.target.resource.name",
    "xdm.target.resource.type", "xdm.target.resource.value",
    "xdm.target.resource_before.value", "xdm.target.sent_bytes",
    "xdm.target.sent_packets", "xdm.target.url", "xdm.target.user.username",
]
print(f"Querying for {len(XDM_FIELDS)} XDM targets")

# First: raw landing check
q_raw = f'dataset = fortinet_fortigate_raw | filter msg contains "{MARKER}" | limit 1'
r = xql(sid, q_raw)
reply = r.get("reply", {})
raw_n = reply.get("number_of_results", 0)
print(f"\n=== RAW landing ===")
if reply.get("status") == "SUCCESS" and raw_n > 0:
    row = reply["results"]["data"][0]
    non_null = {k: v for k, v in row.items()
                if v not in (None, "", "null") and not k.startswith("_")}
    print(f"  ✅ RAW: 1 row, {len(non_null)} populated columns")
    print(f"     _vendor={row.get('_vendor')!r}  _product={row.get('_product')!r}")
else:
    print(f"  ❌ status={reply.get('status')}  rows={raw_n}  err={reply.get('error', {})}")
    # Hunt across other datasets
    for hunt_ds in ("unknown_unknown_raw", "phantom_logs_raw"):
        q = f'dataset = {hunt_ds} | filter _raw_log contains "{MARKER}" | limit 1'
        try:
            rh = xql(sid, q)
            if rh.get("reply", {}).get("number_of_results", 0) > 0:
                row = rh["reply"]["results"]["data"][0]
                print(f"  ↳ FOUND in {hunt_ds} instead — _vendor={row.get('_vendor')!r}  _product={row.get('_product')!r}")
                break
        except Exception:
            pass

# DM query with full XDM fields list
fields_clause = ", ".join(XDM_FIELDS)
q_dm = (f'datamodel dataset = fortinet_fortigate_raw '
        f'| filter xdm.event.description contains "{MARKER}" '
        f'| fields {fields_clause} | limit 1')
rdm = xql(sid, q_dm)
rep_dm = rdm.get("reply", {})
print(f"\n=== DM saturation ===")
if rep_dm.get("status") != "SUCCESS":
    print(f"  ❌ DM query failed: {rep_dm.get('error', {})}")
    # Try without marker filter — get latest
    q_fb = (f'datamodel dataset = fortinet_fortigate_raw '
            f'| sort desc _insert_time | fields {fields_clause}, xdm.event.description '
            f'| limit 10')
    rdm = xql(sid, q_fb)
    rep_dm = rdm.get("reply", {})
    if rep_dm.get("status") == "SUCCESS":
        rows = rep_dm.get("results", {}).get("data", [])
        matched = next((r for r in rows
                        if MARKER in (str(r.get("xdm.event.description", "")) or "")), None)
        if matched:
            print(f"  ✅ Found in latest 10 (fallback)")
            rep_dm = {"status": "SUCCESS", "number_of_results": 1,
                      "results": {"data": [matched]}}

if rep_dm.get("status") == "SUCCESS" and rep_dm.get("number_of_results", 0) > 0:
    dm_row = rep_dm["results"]["data"][0]
    populated = {f: dm_row.get(f) for f in XDM_FIELDS
                 if dm_row.get(f) not in (None, "", "null")}
    n_pop = len(populated)
    pct = 100 * n_pop // len(XDM_FIELDS)
    print(f"  ✅ DM: {n_pop}/{len(XDM_FIELDS)} XDM fields populated ({pct}%)")
    print(f"\n  Populated XDM fields:")
    for k in sorted(populated.keys()):
        v = populated[k]
        s = str(v)[:80]
        print(f"    [+] {k} = {s}")
    print(f"\n  Missing ({len(XDM_FIELDS) - n_pop}):")
    missing = [f for f in XDM_FIELDS if f not in populated]
    for m in missing:
        print(f"    [-] {m}")
else:
    print(f"  ⚠️ DM: no matching row (status={rep_dm.get('status')}, n={rep_dm.get('number_of_results', 0)})")
