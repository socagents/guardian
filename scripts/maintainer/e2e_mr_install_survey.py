#!/usr/bin/env python3
"""Survey: for each direct_mapped_cef dataset, check if MR is installed
(DM count vs raw count). Helps pick packs likely to saturate."""
import json, os, urllib.request
TOKEN = os.environ["MCP_TOKEN"]
XSIAM_MCP = "http://phantom-connector-xsiam-Cortex_XSIAM:9000/mcp"

def post(b, sid=None):
    h={"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json",
       "Accept":"application/json, text/event-stream"}
    if sid: h["mcp-session-id"]=sid
    r=urllib.request.Request(XSIAM_MCP, data=json.dumps(b).encode(),
                             headers=h, method="POST")
    with urllib.request.urlopen(r, timeout=180) as resp:
        return resp.read().decode(), resp.headers

def sse(s):
    for ln in s.split("\n"):
        ln=ln.strip()
        if ln.startswith("data:"):
            try:
                f=json.loads(ln[5:].strip())
                if "result" in f:
                    c=f["result"].get("content", [])
                    if c: return json.loads(c[0].get("text", "{}"))
            except: pass
    return {}

_, h = post({"jsonrpc":"2.0","id":1,"method":"initialize",
             "params":{"protocolVersion":"2024-11-05","capabilities":{},
                       "clientInfo":{"name":"p","version":"1.0"}}})
sid = h.get("mcp-session-id") or h.get("Mcp-Session-Id")
post({"jsonrpc":"2.0","method":"notifications/initialized","params":{}}, sid)

def xql(q):
    body, _ = post({"jsonrpc":"2.0","id":99,"method":"tools/call",
                    "params":{"name":"run_xql_query",
                              "arguments":{"request":{"query":q}}}}, sid)
    return sse(body)

# Top 25 by CEF dict hits from the manifest
CANDIDATES = [
    "check_point_vpn_1_firewall_1_raw",
    "check_point_url_filtering_raw",
    "check_point_smartdefense_raw",
    "check_point_application_control_raw",
    "check_point_identity_awareness_raw",
    "cisco_firepower_raw",
    "cisco_asa_raw",
    "cisco_ise_raw",
    "trend_micro_deep_security_agent_raw",
    "trend_micro_deep_security_manager_raw",
    "trend_micro_vision_one_raw",
    "manageengine_adauditplus_raw",
    "manageengine_adssp_raw",
    "fortinet_fortiweb_raw",
    "fortinet_fortigate_raw",
    "mcafee_nsm_raw",
    "citrix_adc_raw",
    "nginx_nginx_raw",
    "okta_okta_raw",
    "okta_sso_raw",
    "linux_linux_raw",
    "kubernetes_kubernetes_raw",
    "aws_waf_raw",
    "aws_security_hub_raw",
    "vmware_carbon_black_cloud_raw",
]

print(f"{'dataset':<48}{'raw':<10}{'DM':<10}{'verdict':<25}")
print("-" * 95)
results = {}
for ds in CANDIDATES:
    # Raw count
    r = xql(f"dataset = {ds} | comp count() as n")
    rep = r.get("reply", {})
    if rep.get("status") != "SUCCESS":
        print(f"{ds:<48}{'NX':<10}{'NX':<10}{'dataset does not exist':<25}")
        results[ds] = "dataset_missing"
        continue
    raw_n = (rep.get("results", {}).get("data") or [{"n": 0}])[0].get("n", 0)
    # DM count
    r2 = xql(f"datamodel dataset = {ds} | comp count() as n")
    rep2 = r2.get("reply", {})
    if rep2.get("status") != "SUCCESS":
        print(f"{ds:<48}{raw_n:<10}{'ERR':<10}{'DM query err':<25}")
        results[ds] = "dm_error"
        continue
    dm_n = (rep2.get("results", {}).get("data") or [{"n": 0}])[0].get("n", 0)

    if raw_n == 0 and dm_n == 0:
        verdict = "empty (no events sent)"
        results[ds] = "empty"
    elif raw_n > 0 and dm_n == raw_n:
        verdict = "✅ MR installed + firing"
        results[ds] = "mr_installed"
    elif raw_n > 0 and dm_n > 0:
        verdict = f"⚠️ partial ({dm_n}/{raw_n})"
        results[ds] = "partial"
    elif raw_n > 0 and dm_n == 0:
        verdict = "❌ MR not installed"
        results[ds] = "no_mr"
    else:
        verdict = "?"
        results[ds] = "?"
    print(f"{ds:<48}{raw_n:<10}{dm_n:<10}{verdict:<25}")

# Save for next step
with open("/tmp/mr_install_survey.json", "w") as f:
    json.dump(results, f, indent=2)
print("\nSaved /tmp/mr_install_survey.json")
