#!/usr/bin/env python3
"""Batch 9 — Microsoft Azure sub-vendors via CEF wrapping.

VENDORS THIS BATCH (all use the same Azure resource log envelope)
==================
  1. msft_azure_firewall_raw    (AZFW network/application rules — filter category = "AZFW*")
  2. msft_azure_app_service_raw (App Service HTTP logs — filter category in("AppServiceHTTPLogs"))
  3. msft_azure_aks_raw         (AKS audit logs — filter category in("kube-audit"))
  4. msft_azure_flowlogs_raw    (NSG flow logs — filter category = "NetworkSecurityGroupFlowEvent")
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
ts_iso_offset = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")


# ============================================================
# (1) Azure Firewall — msft_azure_firewall_raw (AZFWNetworkRule)
# ============================================================
AZFW_MARKER = f"azfw-{BATCH}"
azfw_properties = json.dumps({
    "SourceIp": "10.5.5.50", "SourcePort": "54321",
    "DestinationIp": "203.0.113.200", "DestinationPort": "443",
    "Protocol": "TCP", "Action": "Allow", "ActionReason": "RuleMatch",
    "Policy": "corp-firewall-policy",
    "RuleCollectionGroup": "DefaultRuleCollectionGroup",
    "RuleCollection": "AllowOutboundHTTPS",
    "Rule": f"AllowHTTPS-{AZFW_MARKER}",
}).replace(" ", "")
azfw_ext = {
    "time": ts_iso,
    "category": "AZFWNetworkRule",
    "resourceId": f"/subscriptions/sub-001/resourceGroups/rg-fw/providers/Microsoft.Network/azureFirewalls/azfw-{AZFW_MARKER}",
    "operationName": "AzureFirewallNetworkRuleLog",
    "properties": azfw_properties,
}
azfw_cef = f"<134>{ts_bsd} smoke-host CEF:0|msft|azure_firewall|1.0|AZFW_RULE|NetworkRuleHit|3|" + " ".join(f"{k}={v}" for k, v in azfw_ext.items())


# ============================================================
# (2) Azure App Service — msft_azure_app_service_raw
# ============================================================
APP_MARKER = f"appsvc-{BATCH}"
app_properties = json.dumps({
    "CIp": "203.0.113.155:443", "CsHost": f"webapp-{APP_MARKER}.azurewebsites.net",
    "CsMethod": "POST", "ScStatus": "200", "Result": "Success",
    "TimeTaken": "120", "UserAgent": "Mozilla/5.0 AppSvc CEF",
    "CsBytes": "1024", "ScBytes": "2048", "ComputerName": "RD0003FFB1234",
    "Referer": "https://corp.example.com",
    "CsUsername": f"alice-{APP_MARKER}@corp.example.com",
    "SPort": "443",
}).replace(" ", "")
app_ext = {
    "time": ts_iso,
    "category": "AppServiceHTTPLogs",
    "resourceId": f"/subscriptions/sub-001/resourceGroups/rg-web/providers/Microsoft.Web/sites/webapp-{APP_MARKER}",
    "properties": app_properties,
    "operationName": "Microsoft.Web/sites/log",
    "Level": "INFO",
}
app_cef = f"<134>{ts_bsd} smoke-host CEF:0|msft|azure_appservice|1.0|APPSVC_HTTP|Request|3|" + " ".join(f"{k}={v}" for k, v in app_ext.items())


# ============================================================
# (3) Azure AKS — msft_azure_aks_raw (kube-audit branch)
# ============================================================
# MR is complex — uses properties.log JSON with auditID, user, verb, etc.
AKS_MARKER = f"aks-{BATCH}"
aks_log = json.dumps({
    "auditID": AKS_MARKER,
    "kind": "Event",
    "level": "RequestResponse",
    "stage": "ResponseComplete",
    "verb": "create",
    "RequestUri": "/api/v1/namespaces/default/pods",
    "user": {"username": f"alice-{AKS_MARKER}", "uid": f"uid-{BATCH}", "groups": ["system:authenticated"]},
    "sourceIPs": ["10.5.5.250"],
    "userAgent": "kubectl/v1.28",
    "objectRef": {"resource": "pods", "namespace": "default", "name": f"pod-{AKS_MARKER}", "apiVersion": "v1"},
    "responseStatus": {"code": 201, "status": "Success", "details": {"name": f"pod-{AKS_MARKER}", "kind": "Pod"}},
}).replace(" ", "")
aks_properties = json.dumps({"log": json.loads(aks_log)}).replace(" ", "")
aks_ext = {
    "time": ts_iso,
    "category": "kube-audit",
    "resourceId": f"/subscriptions/sub-001/resourceGroups/rg-k8s/providers/Microsoft.ContainerService/managedClusters/aks-{AKS_MARKER}",
    "properties": aks_properties,
    "operationName": "Microsoft.ContainerService/managedClusters/audit",
    "Level": "Info",
}
aks_cef = f"<134>{ts_bsd} smoke-host CEF:0|msft|azure_aks|1.0|AKS_AUDIT|PodCreate|3|" + " ".join(f"{k}={v}" for k, v in aks_ext.items())


# ============================================================
# (4) Azure Flow Logs — msft_azure_flowlogs_raw (NSGFlow)
# ============================================================
FLOW_MARKER = f"flow-{BATCH}"
flow_ext = {
    "time": ts_iso,
    "category": "NetworkSecurityGroupFlowEvent",
    "operationName": "NetworkSecurityGroupFlowEvents",
    "resourceId": f"/subscriptions/sub-001/resourceGroups/rg-net/providers/Microsoft.Network/networkSecurityGroups/nsg-{FLOW_MARKER}",
    "sourceAddress": "10.5.5.100",
    "destinationAddress": "203.0.113.250",
    "sourcePort": "54322",
    "destinationPort": "443",
    "transportProtocol": "T",                    # → TCP
    "deviceAction": "A",                          # Allow
    "flowState": "B",                             # Begin
    "deviceDirection": "O",                       # Outbound
    "nsgRuleName": f"Allow-HTTPS-{FLOW_MARKER}",
    "mac": "001122334455",
    "packetsStoD": "10", "bytesStoD": "1500",
    "packetsDtoS": "8", "bytesDtoS": "2400",
}
flow_cef = f"<134>{ts_bsd} smoke-host CEF:0|msft|azure_flowlogs|1.0|NSGFLOW|FlowAllow|3|" + " ".join(f"{k}={v}" for k, v in flow_ext.items())


SMOKES = [
    {"name": "Azure Firewall",       "dataset": "msft_azure_firewall_raw",     "event": azfw_cef, "marker": AZFW_MARKER, "raw_field": "_raw_log", "xdm_field": "xdm.network.rule"},
    {"name": "Azure App Service",     "dataset": "msft_azure_app_service_raw",  "event": app_cef,  "marker": APP_MARKER,  "raw_field": "_raw_log", "xdm_field": "xdm.target.host.hostname"},
    {"name": "Azure AKS",             "dataset": "msft_azure_aks_raw",          "event": aks_cef,  "marker": AKS_MARKER,  "raw_field": "_raw_log", "xdm_field": "xdm.event.id"},
    {"name": "Azure Flow Logs",       "dataset": "msft_azure_flowlogs_raw",     "event": flow_cef, "marker": FLOW_MARKER, "raw_field": "nsgRuleName", "xdm_field": "xdm.network.rule"},
]


print("=" * 70)
print(f"BATCH 9 — Microsoft Azure sub-vendors  ({BATCH})")
print("=" * 70)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for s in SMOKES:
    e = s["event"]
    print(f"\n[{s['name']}]  → {BROKER[0]}:{BROKER[1]}  ({len(e)} bytes)")
    print(f"  marker={s['marker']}")
    if len(e) >= 1500:
        print(f"  ⚠ OVER UDP MTU 1500 ({len(e)} bytes)")
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
             "params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"b9","version":"1"}}})
sid = h.get("mcp-session-id") or h.get("Mcp-Session-Id")
post({"jsonrpc":"2.0","method":"notifications/initialized","params":{}}, sid)

def xql(q):
    body, _ = post({"jsonrpc":"2.0","id":99,"method":"tools/call",
                    "params":{"name":"run_xql_query","arguments":{"request":{"query":q, "tenant_timeframe":{"relativeTime":1800000}}}}}, sid)
    return sse(body)


print("\n" + "=" * 70)
print("VERIFICATION")
print("=" * 70)

results = []
for s in SMOKES:
    name, dataset, marker = s["name"], s["dataset"], s["marker"]
    rfield, xfield = s["raw_field"], s["xdm_field"]
    print(f"\n[{name}] dataset={dataset}")

    q1 = f'dataset = {dataset} | filter {rfield} contains "{marker}" or _raw_log contains "{marker}" | limit 1'
    r1 = xql(q1)
    rep1 = r1.get("reply", {})
    s1, n1 = rep1.get("status"), rep1.get("number_of_results", 0)
    raw_cols = 0
    if s1 == "SUCCESS" and n1 > 0:
        row = rep1["results"]["data"][0]
        raw_cols = sum(1 for k,v in row.items() if v not in (None,"","null"))
        print(f"  ✅ raw LANDED ({raw_cols} cols)")
    elif s1 == "FAIL":
        print(f"  ✗ dataset doesn't exist")
        results.append({"name": name, "result": "DATASET_MISSING", "raw_cols": 0, "xdm_cols": 0})
        continue
    elif s1 == "SUCCESS":
        print(f"  ⊘ dataset exists, n=0 (PR may have rejected)")
    else:
        print(f"  ⚠ status={s1}")

    q2 = f'datamodel dataset = {dataset} | filter {xfield} contains "{marker}" | limit 1'
    r2 = xql(q2)
    rep2 = r2.get("reply", {})
    s2, n2 = rep2.get("status"), rep2.get("number_of_results", 0)
    xdm_cols = 0
    if s2 == "SUCCESS" and n2 > 0:
        row = rep2["results"]["data"][0]
        populated = {k:v for k,v in row.items() if v not in (None,"","null") and k.startswith("xdm.")}
        xdm_cols = len(populated)
        print(f"  ✅ XDM populated ({xdm_cols} fields)")
        for k in sorted(populated)[:10]:
            print(f"    {k:42} = {str(populated[k])[:70]}")
    else:
        print(f"  ⊘ XDM: status={s2}, n={n2}")

    result = "LANDED" if raw_cols > 0 else "RAW_GAP"
    results.append({"name": name, "result": result, "raw_cols": raw_cols, "xdm_cols": xdm_cols})


print("\n" + "=" * 70)
print("BATCH 9 SUMMARY")
print("=" * 70)
for r in results:
    icon = "✅" if r["result"] == "LANDED" and r["xdm_cols"] > 0 else "⚠" if r["result"] == "LANDED" else "✗"
    print(f"  {icon} {r['name']:<24}  {r['result']:<14}  raw={r['raw_cols']:>3}  xdm={r['xdm_cols']:>3}")

landed = sum(1 for r in results if r["result"] == "LANDED")
xdm_fired = sum(1 for r in results if r["xdm_cols"] > 0)
print(f"\n  {landed}/{len(results)} landed raw, {xdm_fired}/{len(results)} fired MR")
