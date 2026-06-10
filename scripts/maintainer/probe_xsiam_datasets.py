#!/usr/bin/env python3
"""Enumerate XSIAM datasets that received fresh events in the last 30 min.

Uses `xsiam_get_datasets` to list all datasets in the tenant, then
queries each one for `count() filter _time > <30min ago>`. Surfaces
which datasets our v0.17.78 smoke run actually populated — including
the broker-auto-derived names (`amazon_web_services_*`) that diverge
from the YAML `dataset_name` field.

The output is two tables:

  1. **All populated datasets** (sorted by row count). The full picture
     of what's in the tenant right now.
  2. **Datasets our worker created** — cross-referenced against the
     22 validated-vendor YAMLs. Three columns:
       - YAML dataset_name (what the operator expects)
       - Broker-derived name (what `<cefDeviceVendor>_<cefDeviceProduct>_raw`
         normalizes to)
       - Got fresh events? Y/N
     Plus a recommended `broker_vendor` + `broker_product` pair to add
     to each YAML so the broker auto-routes to the YAML's expected
     dataset.

Runs INSIDE phantom_agent via:

    docker exec -i phantom_agent python3 < probe_xsiam_datasets.py

Hits the XSIAM connector's MCP directly at port 9000 (proven path).
"""

from __future__ import annotations

import json
import os
import time
import urllib.request

XSIAM_MCP = "http://phantom-connector-xsiam-Cortex_XSIAM:9000/mcp"
TOKEN = os.environ["MCP_TOKEN"]

# Same 22 vendors as the v0.17.78 smoke
VENDOR_YAMLS = [
    ("Okta__OktaModelingRules_2_0__okta_okta_raw", "Okta", "Okta", "okta_okta_raw"),
    ("Okta__OktaModelingRules_2_0__okta_sso_raw", "Okta", "Okta", "okta_sso_raw"),
    ("AlibabaActionTrail__AlibabaModelingRules__alibaba_action_trail_raw", "Alibaba ActionTrail", "Alibaba ActionTrail", "alibaba_action_trail_raw"),
    ("AWS-CloudTrail__AWSCloudTrail__amazon_aws_raw", "Amazon Web Services", "AWS-CloudTrail", "amazon_aws_raw"),
    ("AWS-SecurityHub__AWSSecurityHubModelingRules__aws_security_hub_raw", "Amazon Web Services", "AWS-SecurityHub", "aws_security_hub_raw"),
    ("AWS_WAF__AWS_WAF__aws_waf_raw", "Amazon Web Services", "AWS_WAF", "aws_waf_raw"),
    ("Jira__JiraEventCollector__atlassian_jira_raw", "Atlassian", "Jira", "atlassian_jira_raw"),
    ("ServiceNow__ServiceNow__servicenow_servicenow_raw", "ServiceNow", "ServiceNow", "servicenow_servicenow_raw"),
    ("CyberArkPAS__CyberArkISP__cyberark_isp_raw", "CyberArk", "ISP", "cyberark_isp_raw"),
    ("MicrosoftEntraID__MicrosoftEntraID__msft_azure_ad_audit_raw", "Microsoft", "Entra ID", "msft_azure_ad_audit_raw"),
    ("MicrosoftEntraID__MicrosoftEntraID__msft_azure_ad_raw", "Microsoft", "Entra ID", "msft_azure_ad_raw"),
    ("Office365__Office365__msft_o365_general_raw", "Microsoft", "Office365", "msft_o365_general_raw"),
    ("Office365__Office365__msft_o365_exchange_online_raw", "Microsoft", "Office365", "msft_o365_exchange_online_raw"),
    ("Office365__Office365__msft_o365_sharepoint_online_raw", "Microsoft", "Office365", "msft_o365_sharepoint_online_raw"),
    ("Office365__Office365__msft_o365_emails_raw", "Microsoft", "Office365", "msft_o365_emails_raw"),
    ("Office365__Office365__msft_o365_dlp_raw", "Microsoft", "Office365", "msft_o365_dlp_raw"),
    ("qualys__QualysModelingRules__qualys_qualys_raw", "Qualys", "Qualys", "qualys_qualys_raw"),
    ("ProofpointEmailSecurity__ProofpointEmailSecurity__proofpoint_email_security_raw", "Proofpoint", "Email Security", "proofpoint_email_security_raw"),
    ("ProofpointTAP__ProofpointTAPModelingRules__proofpoint_tap_raw", "Proofpoint", "TAP", "proofpoint_tap_raw"),
    ("AzureFlowLogs__AzureFlowLogs__msft_azure_flowlogs_raw", "Microsoft", "Azure", "msft_azure_flowlogs_raw"),
    ("AzureWAF__AzureWAF__msft_azure_waf_raw", "Microsoft", "Azure WAF", "msft_azure_waf_raw"),
    ("AzureKubernetesServices__AzureKubernetesServices__msft_azure_aks_raw", "Microsoft", "Azure Kubernetes Services", "msft_azure_aks_raw"),
]


def post(body, sid=None):
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
         "Accept": "application/json, text/event-stream"}
    if sid:
        h["mcp-session-id"] = sid
    req = urllib.request.Request(XSIAM_MCP, data=json.dumps(body).encode(),
                                 headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read().decode(), r.headers


def sse(t):
    for ln in t.split("\n"):
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


def normalize(s):
    """Mirror the broker's CEF-header normalization: lowercase, non-alphanumerics → '_'."""
    out = []
    for ch in s.lower():
        out.append(ch if ch.isalnum() else "_")
    return "".join(out)


# Init MCP session
_, hdrs = post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                           "clientInfo": {"name": "probe", "version": "1"}}})
sid = hdrs.get("mcp-session-id") or hdrs.get("Mcp-Session-Id")
post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, sid)

# Step 1: enumerate all datasets in the tenant
print("=== Step 1: enumerate datasets ===")
body, _ = post({"jsonrpc": "2.0", "id": 10, "method": "tools/call",
                "params": {"name": "get_datasets", "arguments": {}}}, sid)
r = sse(body)
all_datasets = []
if isinstance(r, dict):
    # Response may wrap the list under various keys
    for key in ("datasets", "reply", "data"):
        v = r.get(key) if isinstance(r, dict) else None
        if isinstance(v, list) and v:
            all_datasets = v
            break
    else:
        # Could be the dict itself is the list (unlikely)
        pass
elif isinstance(r, list):
    all_datasets = r

print(f"Total datasets in tenant: {len(all_datasets)}")
if all_datasets and isinstance(all_datasets[0], dict):
    print(f"Sample dataset keys: {list(all_datasets[0].keys())}")
elif all_datasets:
    print(f"Sample (string): {all_datasets[0]}")

# Step 2: for each known vendor, check both YAML dataset and broker-derived dataset
print("\n=== Step 2: per-vendor landing check ===")
print(f"{'YAML dataset':40s} {'Broker-derived':50s} {'Match?':8s} {'Status':10s}")
print("-" * 110)

vendor_summary = []
for slug, vendor, product, dataset_name in VENDOR_YAMLS:
    broker_derived = f"{normalize(vendor)}_{normalize(product)}_raw"
    match = "YES" if broker_derived == dataset_name else "no"

    # Query the YAML's expected dataset
    yaml_q = f"dataset = {dataset_name} | sort desc _time | limit 1"
    body, _ = post({"jsonrpc": "2.0", "id": 20, "method": "tools/call",
                    "params": {"name": "run_xql_query",
                               "arguments": {"request": {"query": yaml_q,
                                                          "tenant_timeframe": {"relativeTime": 3600000}}}}}, sid)
    yaml_r = sse(body)
    yaml_n = (yaml_r.get("reply", {}) or {}).get("number_of_results", 0)

    # Query the broker-derived dataset
    if broker_derived != dataset_name:
        derived_q = f"dataset = {broker_derived} | sort desc _time | limit 1"
        body, _ = post({"jsonrpc": "2.0", "id": 21, "method": "tools/call",
                        "params": {"name": "run_xql_query",
                                   "arguments": {"request": {"query": derived_q,
                                                              "tenant_timeframe": {"relativeTime": 3600000}}}}}, sid)
        derived_r = sse(body)
        derived_n = (derived_r.get("reply", {}) or {}).get("number_of_results", 0)
    else:
        derived_n = yaml_n  # same dataset, don't re-query

    print(f"{dataset_name:40s} {broker_derived:50s} {match:8s} yaml={yaml_n} derived={derived_n}")
    vendor_summary.append({
        "slug": slug,
        "vendor": vendor,
        "product": product,
        "yaml_dataset": dataset_name,
        "broker_derived": broker_derived,
        "names_match": match == "YES",
        "yaml_has_events": yaml_n > 0,
        "derived_has_events": derived_n > 0 if broker_derived != dataset_name else yaml_n > 0,
    })

print("\n=== Step 3: recommended YAML override fields ===")
print(f"{'YAML dataset':40s} {'Need override?':16s} {'broker_vendor':25s} {'broker_product':20s}")
print("-" * 110)
overrides = []
for v in vendor_summary:
    if v["names_match"]:
        # Names align — no override needed
        print(f"{v['yaml_dataset']:40s} {'no':16s} {'-':25s} {'-':20s}")
        continue
    # Need to find what (vendor, product) would broker-derive to v['yaml_dataset']
    # Strip the trailing `_raw` and split on `_`
    target = v["yaml_dataset"]
    if not target.endswith("_raw"):
        print(f"{target:40s} {'? (no _raw)':16s} {'?':25s} {'?':20s}")
        continue
    stem = target[:-len("_raw")]
    # The challenge: stem like `amazon_aws` could be vendor=`amazon`, product=`aws` OR
    # vendor=`amazon_aws`, product=` ` etc. Heuristic: split at first underscore,
    # but if the YAML's actual `dataset_name` doesn't match, the operator likely needs
    # to pick the split themselves. For known patterns:
    if "_" in stem:
        parts = stem.split("_", 1)
        # First-token heuristic
        guess_vendor, guess_product = parts[0], parts[1]
    else:
        guess_vendor, guess_product = stem, stem
    print(f"{v['yaml_dataset']:40s} {'YES':16s} {guess_vendor:25s} {guess_product:20s}")
    overrides.append({
        "slug": v["slug"],
        "yaml_dataset": v["yaml_dataset"],
        "broker_vendor": guess_vendor,
        "broker_product": guess_product,
    })

# Write structured output for follow-on processing
output = {
    "total_datasets_in_tenant": len(all_datasets),
    "vendor_summary": vendor_summary,
    "recommended_overrides": overrides,
    "probed_at": int(time.time()),
}
with open("/app/data/probe_xsiam_datasets.json", "w") as f:
    json.dump(output, f, indent=2)
print(f"\nFull JSON output saved to /app/data/probe_xsiam_datasets.json")
print(f"Recommended overrides for {len(overrides)} vendors.")
