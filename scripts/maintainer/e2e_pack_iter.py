#!/usr/bin/env python3
"""Per-pack iteration: send a syslog/CEF message via raw UDP, query
cisco_asa_raw/nginx_nginx_raw/etc, verify _raw_log + _json + XDM populated.

Usage: pack_iter.py <pack_key> [<smoke_id>] [<wait_s>]
       pack keys: asa, nginx, checkpoint, awswaf, okta
"""
import json, os, socket, sys, time, urllib.request
from datetime import datetime, timezone

BROKER_HOST = "10.10.0.8"
BROKER_PORT = 514
XSIAM_BASE = "http://phantom-connector-xsiam-Cortex_XSIAM:9000"
TOKEN = os.environ["MCP_TOKEN"]


def _ts_bsd():
    return datetime.now(timezone.utc).strftime("%b %d %H:%M:%S")


def _ts_nginx():
    """Format: 27/May/2026:10:15:30 +0000"""
    return datetime.now(timezone.utc).strftime("%d/%b/%Y:%H:%M:%S +0000")


def _ts_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


PACKS = {
    "asa": {
        "dataset": "cisco_asa_raw",
        "build_msg": lambda smk: (
            f'<134>{_ts_bsd()} asa-edge-01 %ASA-6-302013: '
            f'Built outbound TCP connection {smk[-8:]} for outside:198.51.100.7/443 '
            f'(198.51.100.7/443) [marker={smk}] to inside:192.0.2.45/5432 (192.0.2.45/5432)'
        ),
        "xdm_fields": [
            "xdm.event.type", "xdm.event.outcome", "xdm.observer.action",
            "xdm.source.ipv4", "xdm.target.ipv4", "xdm.network.ip_protocol",
        ],
    },
    "nginx": {
        "dataset": "nginx_nginx_raw",
        "build_msg": lambda smk: (
            # Standard NGINX combined log format wrapped in syslog header.
            # PR filter requires the [dd/MMM/yyyy:hh:mm:ss +nnnn] pattern.
            f'<134>{_ts_bsd()} web-server-01 nginx: '
            f'192.0.2.45 - jdoe [{_ts_nginx()}] '
            f'"GET /api/v1/test?marker={smk} HTTP/1.1" 200 4096 '
            f'"https://referrer.example.com/" '
            f'"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"'
        ),
        "xdm_fields": [
            "xdm.network.http.url", "xdm.network.http.method",
            "xdm.network.http.response_code", "xdm.target.sent_bytes",
            "xdm.source.ipv4", "xdm.source.user.username",
        ],
    },
    "checkpoint": {
        "dataset": "check_point_smartdefense_raw",
        "build_msg": lambda smk: (
            # CEF format expected by Checkpoint SmartDefense MR.
            # cefDeviceVendor=Check Point + cefDeviceProduct=VPN-1 & FireWall-1
            # CEF extension fields use CEF spec keys (rt, src, dst, etc.).
            f'<134>{_ts_bsd()} cpfw-01 CEF:0|Check Point|VPN-1 & FireWall-1|R80|'
            f'SmartDefense|Threat Prevention|3|'
            f'rt={int(time.time()*1000)} '
            f'loguid={{0x0,0x{smk[-6:]},0x0,0x0}} '
            f'cefDeviceEventClassId=SmartDefense '
            f'cs1Label=Threat Prevention Rule Name cs1=Default_Block '
            f'cs4Label=Protection Name cs4=Generic_Probe '
            f'flexString2Label=Attack Information flexString2=marker_{smk} '
            f'session_id=sess-{smk[-6:]} proto=tcp '
            f'cefSeverity=Medium cefDeviceVendor=Check Point '
            f'cefDeviceProduct=VPN-1 & FireWall-1 '
            f'act=Drop shost=client.example.com suser=jdoe '
            f'src=192.0.2.45 dst=198.51.100.7 spt=54321 '
            f'dhost=target.example.com duser=- dpt=443'
        ),
        "xdm_fields": [
            "xdm.event.id", "xdm.event.outcome", "xdm.event.type",
            "xdm.source.host.hostname", "xdm.target.host.hostname",
            "xdm.observer.action",
        ],
    },
    "awswaf": {
        "dataset": "aws_waf_raw",
        # AWS_WAF is HTTP-collector based — Cortex parsing rule expects
        # timestamp (epoch) + httpRequest (JSON column). The MR uses
        # json_extract(httpRequest, "$.clientIp") etc. Sending as CEF
        # over syslog will probably NOT populate httpRequest because the
        # broker won't construct a JSON column from CEF key=value pairs.
        # We'll see what happens.
        "build_msg": lambda smk: (
            f'<134>{_ts_bsd()} aws-waf-collector CEF:0|aws|waf|1.0|'
            f'BLOCK|WAF Action|4|'
            f'action=BLOCK '
            f'timestamp={int(time.time()*1000)} '
            f'httpsourceid=ABC123-{smk[-6:]} '
            f'httpsourcename=apigateway '
            f'terminatingruleid=RateLimit-{smk[-4:]} '
            f'httpRequest={{"clientIp":"192.0.2.45","country":"US","headers":[{{"name":"User-Agent","value":"Mozilla/5.0 marker={smk}"}}],"httpMethod":"POST","uri":"/api/login","requestId":"req-{smk[-8:]}"}}'
        ),
        "xdm_fields": [
            "xdm.network.http.method", "xdm.network.http.url",
            "xdm.source.ipv4", "xdm.source.location.country",
            "xdm.observer.action",
        ],
    },
    "okta": {
        "dataset": "okta_okta_raw",
        # Okta is HTTP-collector. The MR uses json_extract_scalar(actor, "$.alternateId")
        # etc. on JSON-typed columns. Same caveat as AWS_WAF.
        "build_msg": lambda smk: (
            f'<134>{_ts_bsd()} okta-collector CEF:0|okta|okta|2024.01|'
            f'user.authentication.auth_via_mfa|MFA Auth|3|'
            f'eventType=user.authentication.auth_via_mfa '
            f'uuid={smk} '
            f'published={_ts_iso()} '
            f'severity=INFO '
            f'displayMessage=Authenticate via MFA marker={smk} '
            f'actor={{"id":"00uid-{smk[-8:]}","type":"User","alternateId":"jdoe@example.com","displayName":"John Doe"}} '
            f'client={{"ipAddress":"192.0.2.45","userAgent":{{"rawUserAgent":"Mozilla/5.0"}}}} '
            f'outcome={{"result":"SUCCESS"}} '
            f'target=[{{"id":"00abc-{smk[-6:]}","type":"AppInstance","alternateId":"Okta Dashboard","displayName":"Okta Dashboard"}}]'
        ),
        "xdm_fields": [
            "xdm.event.id", "xdm.event.original_event_type", "xdm.event.outcome",
            "xdm.source.user.username", "xdm.source.ipv4",
        ],
    },
}


def send_udp(msg: str, count: int = 3) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for _ in range(count):
        sock.sendto(msg.encode("utf-8"), (BROKER_HOST, BROKER_PORT))
    sock.close()


def _xs_post(body: dict, sid: str = None) -> tuple[str, dict]:
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
         "Accept": "application/json, text/event-stream"}
    if sid: h["mcp-session-id"] = sid
    r = urllib.request.Request(f"{XSIAM_BASE}/mcp", data=json.dumps(body).encode(),
        headers=h, method="POST")
    with urllib.request.urlopen(r, timeout=180) as resp:
        return resp.read().decode(), resp.headers


def open_xsiam():
    body, h = _xs_post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "iter", "version": "1.0"}}})
    sid = h.get("mcp-session-id") or h.get("Mcp-Session-Id")
    _xs_post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, sid)
    return sid


def xql(sid, query):
    body, _ = _xs_post({"jsonrpc": "2.0", "id": 99, "method": "tools/call",
        "params": {"name": "run_xql_query",
                   "arguments": {"request": {"query": query}}}}, sid)
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("data:"):
            try:
                f = json.loads(line[5:].strip())
                if "result" in f:
                    c = f["result"].get("content", [])
                    if c:
                        return json.loads(c[0].get("text", "{}"))
            except Exception:
                pass
    return {}


def run(pack_key: str, smoke_id: str, wait_s: int = 90) -> dict:
    spec = PACKS[pack_key]
    dataset = spec["dataset"]
    msg = spec["build_msg"](smoke_id)

    print(f"\n────── {pack_key.upper()} | smoke_id={smoke_id} ──────")
    print(f"  dataset: {dataset}")
    print(f"  sending ({len(msg)} bytes):")
    print(f"    {msg[:200]}{'...' if len(msg) > 200 else ''}")
    send_udp(msg, count=3)
    print(f"  sent 3 UDP packets to {BROKER_HOST}:{BROKER_PORT}")

    print(f"  waiting {wait_s}s ...")
    for i in range(wait_s // 30):
        time.sleep(30)
        print(f"    ... {(i+1)*30}s")

    sid = open_xsiam()
    verdict = {"pack": pack_key, "smoke_id": smoke_id, "dataset": dataset}

    # Q1: raw dataset
    q1 = f'dataset = {dataset} | filter to_string(_raw_log) contains "{smoke_id}" | sort desc _insert_time | limit 3'
    r1 = xql(sid, q1)
    reply1 = r1.get("reply", {})
    n1 = reply1.get("number_of_results", 0)
    data1 = reply1.get("results", {}).get("data", [])
    verdict["raw_rows"] = n1
    if data1:
        row = data1[0]
        rl = row.get("_raw_log") or ""
        jv = row.get("_json")
        verdict["raw_log_sample"] = str(rl)[:200]
        verdict["json_sample"] = str(jv)[:300] if jv else None
        verdict["raw_log_found"] = bool(rl)
        verdict["json_populated"] = bool(jv) and str(jv) not in ("", "{}", "null", "None")
        print(f"  RAW _raw_log: {str(rl)[:140]}")
        print(f"  RAW _json   : {str(jv)[:180]}")
    else:
        print(f"  RAW: 0 rows")

    # Q2: datamodel
    fields_clause = ", ".join(spec["xdm_fields"])
    q2 = (
        f'datamodel dataset = {dataset} | '
        f'filter to_string(_raw_log) contains "{smoke_id}" | '
        f'fields {fields_clause} | limit 3'
    )
    r2 = xql(sid, q2)
    reply2 = r2.get("reply", {})
    if reply2.get("status") == "SUCCESS":
        data2 = reply2.get("results", {}).get("data", [])
        if data2:
            row = data2[0]
            non_null = {k: v for k, v in row.items()
                        if k != "_time" and v not in (None, "", "null")}
            verdict["xdm_non_null_count"] = len(non_null)
            verdict["xdm_fields_populated"] = non_null
            print(f"  DM: {len(non_null)} XDM fields populated: {non_null}")
        else:
            verdict["xdm_non_null_count"] = 0
            print(f"  DM: 0 rows")
    else:
        err = reply2.get("error", {})
        verdict["xdm_error"] = str(err)[:200]
        print(f"  DM FAIL: {err}")

    print(f"\n=== VERDICT ===\n{json.dumps(verdict, indent=2)}")
    with open("/tmp/pack_iter_log.jsonl", "a") as f:
        f.write(json.dumps(verdict) + "\n")
    return verdict


def main():
    pack = sys.argv[1] if len(sys.argv) > 1 else "asa"
    smk = sys.argv[2] if len(sys.argv) > 2 else f"smk-{pack}-{int(time.time())}"
    wait_s = int(sys.argv[3]) if len(sys.argv) > 3 else 90

    v = run(pack, smk, wait_s)
    # Exit 0 if XDM populated; 1 if raw landed but XDM didn't; 2 if nothing landed
    if v.get("xdm_non_null_count", 0) > 0:
        sys.exit(0)
    if v.get("raw_log_found"):
        sys.exit(1)
    sys.exit(2)


if __name__ == "__main__":
    main()
