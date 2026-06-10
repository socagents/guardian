#!/usr/bin/env python3
"""Batch 11 — SATURATION pass for 4 high-XDM-potential vendors.

Re-targets the same vendors with FULL field coverage to maximize xdm.* population.

  1. Okta (okta_okta_raw)          — MR has 40+ xdm mappings; prior batch hit 8
  2. AWS CloudTrail (amazon_aws_raw)— MR has 25+ xdm mappings; prior batch hit 11
  3. Azure WAF (msft_azure_waf_raw)  — MR has 20+ xdm mappings; prior batch hit 13
  4. CyberArk ISP (cyberark_isp_raw)— MR has 25+ xdm mappings; prior batch hit 10

Goal: cross 20+ xdm.* per vendor.
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
MCP = "http://phantom-connector-xsiam-Cortex_XSIAM:9000/mcp"

BATCH = int(time.time())
ts_bsd = datetime.now(timezone.utc).strftime("%b %d %H:%M:%S")
ts_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


# ============================================================
# (1) Okta saturation
# ============================================================
# MR populates (from the okta_okta_raw MODEL block in the operator's paste):
#   xdm.logon.type, xdm.alert.risks, xdm.event.duration, xdm.source.host.ipv4_addresses,
#   xdm.event.outcome (from outcome.result), xdm.event.id (uuid), xdm.source.user.username,
#   xdm.source.user.upn, xdm.source.user.identifier, xdm.source.application.name,
#   xdm.event.operation_sub_type, xdm.source.user_agent, xdm.session_context_id,
#   xdm.auth.service, xdm.auth.auth_method, xdm.alert.name, xdm.alert.severity,
#   xdm.observer.action, xdm.target.resource.name, xdm.target.resource.id,
#   xdm.source.cloud.project_id, xdm.source.host.device_id, xdm.source.host.hostname,
#   xdm.auth.mfa.method, xdm.auth.mfa.client_details, xdm.auth.is_mfa_needed,
#   xdm.event.original_event_type, xdm.auth.privilege_level, xdm.source.asn.as_number,
#   xdm.source.host.os, xdm.source.host.os_family, xdm.event.outcome_reason,
#   xdm.alert.description, xdm.source.location.city, xdm.source.location.country,
#   xdm.network.http.browser, xdm.network.rule, xdm.event.description,
#   xdm.source.host.fqdn (from extra fields), xdm.event.type,
#   xdm.event.tags = ["authentication"], xdm.intermediate.is_proxy

OKTA_MARKER = f"okta-sat-{BATCH}"
okta_actor = json.dumps({
    "id": f"00u-{BATCH}", "type": "User", "displayName": "Alice Saturation",
    "alternateId": f"alice-{OKTA_MARKER}@corp.example.com"
}).replace(" ", "")
okta_client = json.dumps({
    "ipAddress": "203.0.113.55", "userAgent": {
        "rawUserAgent": "Mozilla/5.0 (Macintosh) Chrome/120 Saturation",
        "os": "Mac OS X", "browser": "CHROME"
    },
    "device": "Computer",
    "geographicalContext": {
        "city": "San Francisco", "country": "United States", "state": "California",
        "geolocation": {"lat": 37.7, "lon": -122.4}
    },
    "id": "client-device-001", "zone": "OffNetwork"
}).replace(" ", "")
okta_outcome = json.dumps({"result": "SUCCESS", "reason": "User authenticated successfully"}).replace(" ", "")
okta_target = json.dumps([{
    "id": "appinst-001", "type": "AppInstance",
    "alternateId": "Salesforce", "displayName": "Salesforce.com"
}, {
    "id": f"user-target-{BATCH}", "type": "User",
    "alternateId": f"target-{OKTA_MARKER}@corp.example.com", "displayName": "Target User"
}]).replace(" ", "")
okta_auth_ctx = json.dumps({
    "authenticationProvider": {
        "credentialProvider": "OKTA_AUTHENTICATION_PROVIDER",
        "credentialType": "PASSWORD",
        "externalSessionId": f"sess-{BATCH}"
    }
}).replace(" ", "")
okta_transaction = json.dumps({"id": f"tx-{BATCH}", "type": "WEB"}).replace(" ", "")
okta_security_ctx = json.dumps({
    "asNumber": 15169, "asOrg": "Google LLC", "isp": "google",
    "domain": "google.com", "isProxy": "false"
}).replace(" ", "")
okta_request = json.dumps({
    "ipChain": [
        {"ip": "203.0.113.55", "geographicalContext": {}},
        {"ip": "10.5.5.50", "geographicalContext": {}}
    ]
}).replace(" ", "")
okta_debug_ctx = json.dumps({
    "debugData": {
        "deviceFingerprint": f"fp-{BATCH}",
        "risk": {"level": "LOW", "reasons": []},
        "behaviors": "Normal Login",
        "threatSuspected": "false",
        "originalPrincipal": {"type": "User"},
        "proxyType": "None",
        "origin": f"https://corp-okta.example.com/login?marker={OKTA_MARKER}",
        "threatDetections": "None",
        "url": f"https://corp-okta.example.com/?marker={OKTA_MARKER}"
    }
}).replace(" ", "")
okta_ext = {
    "uuid": OKTA_MARKER,
    "published": ts_iso,
    "eventType": "user.authentication.sso",
    "legacyEventType": "core.user.session.start",
    "severity": "INFO",
    "displayMessage": f"User SSO marker={OKTA_MARKER}",
    "actor": okta_actor,
    "client": okta_client,
    "outcome": okta_outcome,
    "target": okta_target,
    "authenticationContext": okta_auth_ctx,
    "transaction": okta_transaction,
    "securityContext": okta_security_ctx,
    "request": okta_request,
    "debugContext": okta_debug_ctx,
}
okta_cef = f"<134>{ts_bsd} smoke-host CEF:0|okta|okta|1.0|OKTA_SSO|user.authentication.sso|3|" + " ".join(f"{k}={v}" for k, v in okta_ext.items())


# ============================================================
# (2) AWS CloudTrail saturation
# ============================================================
# MR fields targeted:
#   xdm.event.description (requestParameters + additionalEventData + responseElements),
#   xdm.event.id, xdm.event.operation_sub_type, xdm.event.original_event_type,
#   xdm.event.outcome (errorCode null vs not), xdm.event.outcome_reason (errorMessage),
#   xdm.event.type, xdm.network.session_id, xdm.network.tls.cipher,
#   xdm.network.tls.protocol_version, xdm.observer.content_version, xdm.observer.name,
#   xdm.observer.type, xdm.session_context_id, xdm.source.cloud.project_id,
#   xdm.source.cloud.provider (constant AWS), xdm.source.host.device_id (vpcEndpointId),
#   xdm.source.host.ipv4_public_addresses, xdm.source.host.fqdn (if AWS internal),
#   xdm.source.ipv4, xdm.source.ipv6, xdm.source.user_agent, xdm.source.user.groups,
#   xdm.source.user.identifier, xdm.source.user.username, xdm.source.user.user_type,
#   xdm.target.cloud.project_id, xdm.target.cloud.provider, xdm.target.cloud.region,
#   xdm.target.host.fqdn (from requestParameters.Host or tlsDetails.clientProvidedHostHeader),
#   xdm.target.host.hostname, xdm.target.resource.id (ARN), xdm.target.resource.name,
#   xdm.target.resource.type
AWS_MARKER = f"aws-sat-{BATCH}"
aws_user_identity = json.dumps({
    "type": "AssumedRole", "principalId": "AROAEXAMPLE12345:alice",
    "userName": "alice", "arn": "arn:aws:sts::123456789012:assumed-role/AdminRole/alice",
    "accountId": "123456789012",
    "sessionContext": {
        "sessionIssuer": {
            "userName": "AdminRole",
            "type": "Role",
            "arn": "arn:aws:iam::123456789012:role/AdminRole"
        }
    },
    "onBehalfOf": {"userId": "user-onbehalf-001"}
}).replace(" ", "")
aws_resources = json.dumps([{
    "ARN": f"arn:aws:s3:::saturation-bucket-{AWS_MARKER}",
    "type": "AWS::S3::Bucket",
    "accountId": "123456789012"
}]).replace(" ", "")
aws_tls = json.dumps({
    "tlsVersion": "TLSv1.2", "cipherSuite": "ECDHE-RSA-AES128-GCM-SHA256",
    "clientProvidedHostHeader": "s3.us-east-1.amazonaws.com"
}).replace(" ", "")
aws_request_params = json.dumps({
    "bucketName": f"saturation-bucket-{AWS_MARKER}", "Host": "s3.us-east-1.amazonaws.com",
    "key": "test-object.txt", "encryption-context": "true"
}).replace(" ", "")
aws_response_elements = json.dumps({
    "x-amz-version-id": f"ver-{BATCH}", "ETag": f'"{BATCH}"'
}).replace(" ", "")
aws_additional = json.dumps({
    "SignatureVersion": "SigV4", "AuthenticationMethod": "AuthHeader"
}).replace(" ", "")
aws_ext = {
    "_log_type": "Cloud Audit Log",
    "eventTime": ts_iso.replace(".000Z", "Z"),  # PR expects RFC3339 with Z
    "eventId": AWS_MARKER,
    "eventName": "GetObject",
    "eventType": "AwsApiCall",
    "eventVersion": "1.11",
    "eventCategory": "Data",
    "eventSource": "s3.amazonaws.com",
    "awsRegion": "us-east-1",
    "requestID": f"REQ-{BATCH}",
    "sourceIPAddress": "203.0.113.45",
    "userAgent": "aws-cli/2.0.0 Python/3.9 saturation",
    "userIdentity": aws_user_identity,
    "resources": aws_resources,
    "tlsDetails": aws_tls,
    "recipientAccountId": "123456789012",
    "sharedEventID": f"shared-{BATCH}",
    "vpcEndpointId": "vpce-abc12345",
    "vpcEndpointAccountId": "123456789012",
    "requestParameters": aws_request_params,
    "responseElements": aws_response_elements,
    "additionalEventData": aws_additional,
    "errorCode": "",  # empty for SUCCESS path
    "errorMessage": "",
}
aws_cef = f"<134>{ts_bsd} smoke-host CEF:0|amazon|aws|1.11|CloudTrail|GetObject|3|" + " ".join(f"{k}={v}" for k, v in aws_ext.items())


# ============================================================
# (3) Azure WAF saturation
# ============================================================
# Already 13 XDM; pushing to 20+ with additional FrontDoor fields
WAF_MARKER = f"azwaf-sat-{BATCH}"
waf_ext = {
    "time": ts_iso,
    "Category": "FrontDoorAccessLog",
    "Resource": f"corp-frontdoor-{WAF_MARKER}",
    "ResourceGroup": "rg-frontdoor",
    "ResourceType": "FRONTDOORS",
    "operationName": "Microsoft.Cdn/frontdoor/access",
    "resourceId": "/subscriptions/sub-001/resourceGroups/rg-frontdoor/providers/Microsoft.Cdn/profiles/corp-fd",
    "trackingReference_s": WAF_MARKER,
    "clientIP_s": "203.0.113.99",
    "clientPort_d": "54322",
    "socketIP_s": "203.0.113.99",
    "httpMethod_s": "POST",
    "httpStatusCode_s": "200",
    "requestUri_s": f"/api/login?marker={WAF_MARKER}",
    "domain_s": f"app-{WAF_MARKER}.azurefd.net",
    "userAgent_s": "Mozilla/5.0AzureWAFSAT",
    "originUrl_s": "https://backend.corp.example.com/api/login",
    "originIp_s": "10.5.5.250",
    "originName_s": "backend-origin-001",
    "timeTaken_s": "0.045",
    "requestBytes_s": "1024",
    "responseBytes_s": "512",
    "errorInfo_s": "NoError",
    "routingRuleName_s": "default-rule",
    "endpoint_s": "corp-endpoint",
    "sni_s": f"app-{WAF_MARKER}.azurefd.net",
    "securityCipher_s": "ECDHE-RSA-AES256-GCM-SHA384",
    "originCryptProtocol_s": "TLSv1.2",
    "securityProtocol_s": "TLSv1.2",
    "referer_s": "https://corp.example.com",
    "clientCountry_s": "United States",
    "requestProtocol_s": "HTTPS/1.1",
    "tenantId": "tenant-001",
}
waf_cef = f"<134>{ts_bsd} smoke-host CEF:0|msft|azure_waf|1.0|AZWAF_FD|FrontDoorAccess|3|" + " ".join(f"{k}={v}" for k, v in waf_ext.items())


# ============================================================
# (4) CyberArk ISP saturation
# ============================================================
# Already 10 XDM; pushing higher by enriching customData + adding identity fields
CARK_MARKER = f"cark-sat-{BATCH}"
cark_custom_data = json.dumps({
    "client_ip_address": "203.0.113.55",
    "success": "True",
    "factors": "password,mfa-push,otp",
    "mechanism": "OTP",
    "authentication_method": "Federation",
    "roles": "User,SysAdmin,Audit",
    "mobile_device": "False",
    "internal_session_id": f"sess-{BATCH}",
    "session_guid": f"guid-{BATCH}",
    "browser_name": "Chrome",
    "browser_version": "120.0.6099.71",
    "entity_name": "Salesforce App",
    "device_os": "macOS",
    "user_agent": "Mozilla/5.0CyberArkSaturation",
    "geoip_country_name": "United States",
    "geoip_city_name": "San Francisco",
    "geoip_latitude": "37.7",
    "geoip_longitude": "-122.4",
    "cookie_session": f"cookie-{BATCH}",
    "endpoint_device_name": "alice-laptop",
    "host_name": "alice-laptop.corp.example.com",
    "denied_by_user": "False",
    "failure_reason": "",
    "device_id": "device-mac-001",
}).replace(" ", "")
cark_ext = {
    "uuid": CARK_MARKER,
    "message": "Cloud.Core.Login",
    "auditCode": "IDP2005",
    "action": "User login successful via SAML federation with MFA",
    "source": "203.0.113.55",
    "username": f"alice-{CARK_MARKER}@corp.example.com",
    "userId": "user-12345",
    "identityType": "HUMAN",
    "tenantId": "tenant-001",
    "customData": cark_custom_data,
}
cark_cef = f"<134>{ts_bsd} smoke-host CEF:0|cyberark|isp|1.0|CARK_LOGIN|LoginSuccess|3|" + " ".join(f"{k}={v}" for k, v in cark_ext.items())


SMOKES = [
    {"name": "Okta SAT",        "dataset": "okta_okta_raw",    "event": okta_cef, "marker": OKTA_MARKER, "raw_field": "uuid",    "xdm_field": "xdm.event.id"},
    {"name": "AWS CloudTrail SAT", "dataset": "amazon_aws_raw",   "event": aws_cef,  "marker": AWS_MARKER,  "raw_field": "eventId", "xdm_field": "xdm.event.id"},
    {"name": "Azure WAF SAT",   "dataset": "msft_azure_waf_raw","event": waf_cef,  "marker": WAF_MARKER,  "raw_field": "trackingReference_s", "xdm_field": "xdm.event.id"},
    {"name": "CyberArk ISP SAT","dataset": "cyberark_isp_raw", "event": cark_cef, "marker": CARK_MARKER, "raw_field": "uuid",    "xdm_field": "xdm.event.id"},
]

print("=" * 70)
print(f"BATCH 11 — SATURATION pass (target 20+ XDM per vendor)  ({BATCH})")
print("=" * 70)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for s in SMOKES:
    e = s["event"]
    print(f"\n[{s['name']}]  → {BROKER[0]}:{BROKER[1]}  ({len(e)} bytes)")
    print(f"  marker={s['marker']}")
    if len(e) >= 1500:
        print(f"  ⚠ OVER UDP MTU 1500 ({len(e)} bytes) — splitting strategy may be needed for follow-up")
    for _ in range(3):
        sock.sendto(e.encode(), BROKER)
sock.close()
print(f"\nAll events sent. Waiting 120s...")
for i in range(4):
    time.sleep(30)
    print(f"  +{(i+1)*30}s")


def post(body, sid=None):
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
         "Accept": "application/json, text/event-stream"}
    if sid: h["mcp-session-id"] = sid
    req = urllib.request.Request(MCP, data=json.dumps(body).encode(), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read().decode(), r.headers


def sse(s):
    for ln in s.split("\n"):
        if ln.startswith("data:"):
            try:
                f = json.loads(ln[5:].strip())
                if "result" in f:
                    c = f["result"].get("content", [])
                    if c: return json.loads(c[0].get("text", "{}"))
            except: pass
    return {}


_, h = post({"jsonrpc":"2.0","id":1,"method":"initialize",
             "params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"b11","version":"1"}}})
sid = h.get("mcp-session-id") or h.get("Mcp-Session-Id")
post({"jsonrpc":"2.0","method":"notifications/initialized","params":{}}, sid)


def xql(q):
    body, _ = post({"jsonrpc":"2.0","id":99,"method":"tools/call",
                    "params":{"name":"run_xql_query","arguments":{"request":{"query":q, "tenant_timeframe":{"relativeTime":1800000}}}}}, sid)
    return sse(body)


print("\n" + "=" * 70)
print("SATURATION VERIFICATION (xdm.* field counts)")
print("=" * 70)

results = []
for s in SMOKES:
    name, dataset, marker, xfield = s["name"], s["dataset"], s["marker"], s["xdm_field"]
    print(f"\n[{name}] dataset={dataset}")
    q = f'datamodel dataset = {dataset} | filter {xfield} contains "{marker}" | limit 1'
    r = xql(q)
    reply = r.get("reply", {})
    s_ = reply.get("status")
    n = reply.get("number_of_results", 0)
    if s_ == "SUCCESS" and n > 0:
        row = reply["results"]["data"][0]
        populated = {k:v for k,v in row.items() if v not in (None,"","null") and k.startswith("xdm.")}
        xdm_cols = len(populated)
        print(f"  ✅ {xdm_cols} xdm.* fields populated")
        for k in sorted(populated):
            print(f"    {k:42} = {str(populated[k])[:70]}")
        results.append({"name": name, "xdm": xdm_cols})
    else:
        print(f"  ⊘ status={s_}, n={n}")
        results.append({"name": name, "xdm": 0})


print("\n" + "=" * 70)
print("BATCH 11 SATURATION SUMMARY")
print("=" * 70)
print(f"  {'vendor':<24}  prior  saturated  delta")
print(f"  {'-'*24}  -----  ---------  -----")
priors = {"Okta SAT": 8, "AWS CloudTrail SAT": 11, "Azure WAF SAT": 13, "CyberArk ISP SAT": 10}
for r in results:
    prior = priors.get(r["name"], "?")
    sat = r["xdm"]
    delta = (f"+{sat-prior}" if isinstance(prior, int) and sat > prior else f"-{prior-sat}" if isinstance(prior, int) else "?")
    icon = "🚀" if isinstance(prior, int) and sat >= prior * 2 else "✅" if isinstance(prior, int) and sat > prior else "="
    print(f"  {icon} {r['name']:<22}  {str(prior):>5}  {str(sat):>9}  {delta}")
