#!/usr/bin/env python3
"""Autonomous batch smoke for the 22 validated vendors, driven entirely
through the agent's MCP chat path (port 8080 inside phantom_agent).

Each call processes up to BATCH_SIZE pending vendors:

  1. Load /app/data/agent_smoke_state.json (creates the initial state
     from the hard-coded vendor list when missing).
  2. Pick the next BATCH_SIZE pending vendors.
  3. For each: open MCP session, load YAML from
     /app/bundle/data-sources/<slug>/data_source.yaml, call
     phantom_create_data_worker via the agent's MCP with vendor +
     product + schema_override.
  4. Wait WAIT_SECONDS for ingest.
  5. For each: query <dataset>_raw via the XSIAM connector's direct
     MCP (port 9000 — the xsiam Python signature still has the
     Pydantic-wrap gap from v0.17.78 follow-on backlog; direct
     access bypasses the agent's proxy).
  6. Kill the workers so they don't flood the broker after the
     batch returns.
  7. Update state, print a one-line per-vendor verdict.

Exit code 0 when at least one vendor was processed; 2 when nothing
pending (final report has been written). The /loop orchestration
above this checks the state file to know when to stop scheduling.
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import time
import urllib.request
from pathlib import Path

import yaml

# ── Hard inputs ───────────────────────────────────────────────────
BATCH_SIZE = 4
WAIT_SECONDS = 120
STATE_PATH = Path("/app/data/agent_smoke_state.json")
REPORT_PATH = Path("/app/data/agent_smoke_report.md")
TOKEN = os.environ["MCP_TOKEN"]

AGENT_MCP = "https://localhost:8080/api/v1/stream/mcp"
XSIAM_MCP = "http://phantom-connector-xsiam-Cortex_XSIAM:9000/mcp"

# 22 validated vendors from v0.17.75 — keep this list in sync with
# scripts/maintainer/enhance_validated_vendor_yamls.py's ENTRIES dict.
VENDORS = [
    "Okta__OktaModelingRules__okta_okta_raw",
    "Okta__OktaModelingRules__okta_sso_raw",
    "AlibabaActionTrail__AlibabaModelingRules__alibaba_action_trail_raw",
    "AWS-CloudTrail__AWSCloudTrail__amazon_aws_raw",
    "AWS-SecurityHub__AWSSecurityHubModelingRules__aws_security_hub_raw",
    "AWS_WAF__AWS_WAF__aws_waf_raw",
    "Jira__JiraEventCollector__atlassian_jira_raw",
    "ServiceNow__ServiceNow__servicenow_servicenow_raw",
    "CyberArkPAS__CyberArkISP__cyberark_isp_raw",
    "MicrosoftEntraID__MicrosoftEntraID__msft_azure_ad_audit_raw",
    "MicrosoftEntraID__MicrosoftEntraID__msft_azure_ad_raw",
    "Office365__Office365__msft_o365_general_raw",
    "Office365__Office365__msft_o365_exchange_online_raw",
    "Office365__Office365__msft_o365_sharepoint_online_raw",
    "Office365__Office365__msft_o365_emails_raw",
    "Office365__Office365__msft_o365_dlp_raw",
    "qualys__QualysModelingRules__qualys_qualys_raw",
    "ProofpointEmailSecurity__ProofpointEmailSecurity__proofpoint_email_security_raw",
    "ProofpointTAP__ProofpointTAPModelingRules__proofpoint_tap_raw",
    "AzureFlowLogs__AzureFlowLogs__msft_azure_flowlogs_raw",
    "AzureWAF__AzureWAF__msft_azure_waf_raw",
    "AzureKubernetesServices__AzureKubernetesServices__msft_azure_aks_raw",
]

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def post(url, body, sid=None, https=False):
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
         "Accept": "application/json, text/event-stream"}
    if sid:
        h["mcp-session-id"] = sid
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers=h, method="POST")
    ctx = _SSL_CTX if https else None
    with urllib.request.urlopen(req, timeout=180, context=ctx) as r:
        return r.read().decode(), r.headers


def sse_parse(text):
    for ln in text.split("\n"):
        if ln.startswith("data:"):
            try:
                f = json.loads(ln[5:].strip())
                if "result" in f:
                    c = f["result"].get("content", [])
                    if c:
                        txt = c[0].get("text", "{}")
                        try:
                            return json.loads(txt)
                        except json.JSONDecodeError:
                            # Tool returned a non-JSON string error
                            return {"_raw": txt, "_isError": f["result"].get("isError", False)}
                if "error" in f:
                    return {"_err": f["error"]}
            except Exception as e:
                pass
    return {}


def open_session(url, https):
    _, hdrs = post(url, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "agent-smoke-all", "version": "1"}}
    }, https=https)
    sid = hdrs.get("mcp-session-id") or hdrs.get("Mcp-Session-Id")
    post(url, {"jsonrpc": "2.0", "method": "notifications/initialized",
               "params": {}}, sid, https=https)
    return sid


def call(url, sid, name, args, rid=99, https=False):
    body, _ = post(url, {"jsonrpc": "2.0", "id": rid, "method": "tools/call",
                         "params": {"name": name, "arguments": args}}, sid, https=https)
    return sse_parse(body)


def build_schema_override(yaml_doc):
    """v2 (smoke campaign 2026-05-29): pass the FULL field list — flat fields,
    top-level composites (type:json), AND their dotted-leaf children. The
    xlog composite-JSON synthesis (post type:json fix) folds the leaves into
    their parent composite's JSON object, so KEEPING the leaves is what lets
    `json_extract_scalar` find real values + XDM saturate. (The old version
    dropped the leaves, which starved the synthesis.) Only meta is omitted."""
    out = []
    for f in yaml_doc.get("fields", []):
        if not (isinstance(f, dict) and f.get("name")):
            continue
        if f.get("is_meta"):
            continue
        out.append({
            "name": f["name"],
            "type": f.get("type") or "string",
            "is_array": bool(f.get("is_array", False)),
        })
    return out


# CEF routing literal parser + discriminator map (smoke campaign 2026-05-29).
# The harness MUST use the broker-routing CEF vendor/product from how_to_use,
# NOT the YAML's display vendor/product — display names broker-derive the
# wrong dataset (the baseline's 19/22 non-landings were all this bug).
import re as _re


def parse_cef_routing(how_to_use, fallback_vendor, fallback_product):
    """Extract the literal CEF vendor/product from the how_to_use's
    '**Required CEF header for XSIAM**' block. Falls back to the display
    values only if the block is missing."""
    v = p = None
    if how_to_use:
        mv = _re.search(r"\*\*vendor\*\*:\s*`([^`]+)`", how_to_use)
        mp = _re.search(r"\*\*product\*\*:\s*`([^`]+)`", how_to_use)
        if mv:
            v = mv.group(1).strip()
        if mp:
            p = mp.group(1).strip()
    return (v or fallback_vendor, p or fallback_product)


# Classifier / discriminator seeds, keyed by dataset_name. Sent via
# observables_dict so the modeling rule's `filter <field> in (...)` classifier
# matches (XDM stays 0 otherwise) and shared-CEF-header siblings route. Values
# discovered from each MR's `filter` line during the 2026-05-29 re-baseline.
# Requires v0.17.105 (streaming path now honors observables_dict).
DISCRIMINATORS = {
    # — Shared-CEF-header split: both Okta datasets are Okta->Okta; PR splits
    #   on eventType. okta_okta is the System Log; okta_sso the SSO stream.
    "okta_okta_raw": {"eventType": ["user.session.start"]},
    "okta_sso_raw": {"eventType": ["user.authentication.sso"]},
    # — MR classifier-enum gates (random value → MR drops row → XDM 0):
    "alibaba_action_trail_raw": {"event_eventtype": ["ApiCall"]},     # filter event_eventtype in ("ApiCall",...)
    "proofpoint_email_security_raw": {"event_type": ["message"]},     # filter event_type = "message"
    "qualys_qualys_raw": {"event_type": ["activity_log"]},            # filter event_type in ("activity_log")
    "msft_azure_flowlogs_raw": {"category": ["NetworkSecurityGroupFlowEvent"]},  # filter category in (...)
    "msft_azure_waf_raw": {"Category": ["FrontDoorAccessLog"]},       # filter Category = "FrontDoorAccessLog" (field missing from YAML → add)
    "cyberark_isp_raw": {"auditCode": ["IDP2005"]},                   # is_auth=true when auditCode in ("IDP2005",...)
    # — Multi-dataset packs with DISTINCT CEF product (route by header; the
    #   discriminator refines XDM mapping branch):
    "msft_azure_ad_audit_raw": {"category": ["AuditLogs"]},
    "msft_azure_ad_raw": {"category": ["SignInLogs"]},
    "msft_o365_exchange_online_raw": {"Workload": ["Exchange"]},
    "msft_o365_sharepoint_online_raw": {"Workload": ["SharePoint"]},
    "msft_o365_emails_raw": {"Operation": ["EmailEvent"]},
    "msft_o365_dlp_raw": {"Workload": ["DLP"]},
    "msft_azure_aks_raw": {"category": ["kube-apiserver"]},  # get_category=coalesce(category,Category); filter in ("kube-apiserver",...) — NOT kube-audit
    # — amazon_aws_raw (CloudTrail): MR gates on `_log_type = "Cloud Audit Log"`,
    #   an XSIAM-internal meta field CEF transport can't set. Residual ceiling
    #   (native-JSON ingestion would be needed). Left unset deliberately.
}


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    state = {
        "started_at": int(time.time()),
        "vendors": {slug: {"status": "pending"} for slug in VENDORS},
    }
    save_state(state)
    return state


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2))


def write_final_report(state):
    started = state.get("started_at", 0)
    finished = int(time.time())
    elapsed_min = (finished - started) // 60 if started else 0

    lines = [
        "# Agent-chat MCP-path smoke matrix — 22 validated vendors",
        "",
        f"Started: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(started))}",
        f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(finished))}",
        f"Elapsed: ~{elapsed_min} min",
        "",
        "Path tested per vendor:",
        "  1. Agent MCP (port 8080, HTTPS): phantom_create_data_worker(",
        "     type=CEF, vendor=X, product=Y, schema_override=<fields[]>)",
        "  2. Worker → OverrideSender → CEF over UDP → broker 10.10.0.8:514",
        "  3. XSIAM connector MCP (direct, port 9000): run_xql_query against",
        "     `dataset = <vendor>_<product>_raw | sort desc _time | limit 1`",
        "",
        "| Vendor (slug) | Dataset | Worker created? | Events landed? | XDM rows | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for slug in VENDORS:
        v = state["vendors"][slug]
        wd = "✅" if v.get("worker_created") else "❌"
        ev = "—"
        if v.get("worker_created"):
            n = v.get("events_landed", 0)
            ev = f"✅ {n}" if n > 0 else "❌ 0"
        xdm = "—"
        if v.get("worker_created"):
            n = v.get("xdm_rows", 0)
            xdm = f"✅ {n}" if n > 0 else "0"
        notes = v.get("notes", "")[:60]
        dataset = v.get("dataset", "?")
        # Trim slug for the table column
        short = slug if len(slug) <= 60 else slug[:57] + "..."
        lines.append(f"| `{short}` | `{dataset}` | {wd} | {ev} | {xdm} | {notes} |")

    n_landed = sum(1 for v in state["vendors"].values()
                   if v.get("events_landed", 0) > 0)
    n_xdm = sum(1 for v in state["vendors"].values()
                if v.get("xdm_rows", 0) > 0)
    lines += [
        "",
        f"**Summary**: {n_landed}/22 vendors landed events in their dataset. "
        f"{n_xdm}/22 produced any XDM rows.",
        "",
        "**Fixes applied this campaign (v0.17.104):** "
        "(1) harness routing — fires the CEF vendor/product LITERALS parsed "
        "from `how_to_use` (not the display names) so the broker routes to "
        "the correct `<vendor>_<product>_raw` dataset; multi-dataset packs "
        "carry a PR discriminator via `observables_dict`. "
        "(2) `xlog/app/dynamic_schema.py` now synthesizes a real nested JSON "
        "object for `type: json` composites (Okta `actor`, AWS WAF "
        "`httpRequest`, Azure AD `targetResources`, ServiceNow `record`) by "
        "folding dotted-leaf children into the parent, so the MR's "
        "`json_extract_scalar` resolves and nested-JSON vendors saturate XDM "
        "instead of capping at 0.",
    ]
    REPORT_PATH.write_text("\n".join(lines))


def smoke_vendor(slug, agent_sid, xsiam_sid):
    """Run the full smoke for one vendor. Returns dict with the result
    fields that get merged into state[vendors][slug]."""
    result = {"slug": slug}
    yaml_path = Path(f"/app/bundle/data-sources/{slug}/data_source.yaml")
    if not yaml_path.exists():
        return {**result, "status": "missing_yaml", "notes": "YAML not found"}
    doc = yaml.safe_load(yaml_path.read_text())
    dataset = doc["dataset_name"]
    # Use the CEF ROUTING literals from how_to_use (NOT the display
    # vendor/product) — display names broker-derive the wrong dataset.
    vendor, product = parse_cef_routing(
        doc.get("how_to_use", ""), doc.get("vendor", ""), doc.get("product", "")
    )
    schema_override = build_schema_override(doc)
    result["dataset"] = dataset
    result["fields_count"] = len(schema_override)
    result["cef_vendor"] = vendor
    result["cef_product"] = product

    # Fire worker via agent's MCP (the path the chat session uses).
    args = {
        "type": "CEF",
        "destination": "udp:10.10.0.8:514",
        "count": 3,
        "interval": 2,
        "vendor": vendor,
        "product": product,
        "version": "1.0",
        "schema_override": schema_override,
    }
    # Multi-dataset PR discriminator (routes to the right sibling dataset).
    disc = DISCRIMINATORS.get(dataset)
    if disc:
        args["observables_dict"] = disc
        result["discriminator"] = disc
    res = call(AGENT_MCP, agent_sid, "phantom_create_data_worker", args,
               rid=100, https=True)

    # The tool returns a list-of-one-worker-info-dict on success
    worker_id = None
    if isinstance(res, list) and res and isinstance(res[0], dict):
        worker_id = res[0].get("worker")
        result["worker_created"] = True
        result["worker_id"] = worker_id
    else:
        result["worker_created"] = False
        result["notes"] = f"createWorker failed: {str(res)[:120]}"
    return result


def verify_vendor(slug, state, xsiam_sid, batch_started):
    """After the WAIT_SECONDS sleep, query XSIAM to see if events landed.
    Mutates state[vendors][slug] with the verification fields."""
    v = state["vendors"][slug]
    if not v.get("worker_created"):
        v["status"] = "worker_create_failed"
        return
    dataset = v.get("dataset")
    if not dataset:
        v["status"] = "no_dataset_known"
        return

    # Raw landing query. run_xql_query takes a SINGLE flat `query` string —
    # NOT a {"request": {...}} wrapper and NOT tenant_timeframe (both are
    # rejected by the tool's Pydantic model: "Unexpected keyword argument").
    # The lookback window is expressed INLINE via `config timeframe = …`.
    # (Fixes the campaign-wide false-0: the old wrapped shape failed
    # validation before reaching XSIAM, so verify never read any results
    # and every vendor was recorded as 0-landed despite events arriving.)
    raw_q = f"config timeframe = 1d | dataset = {dataset} | sort desc _time | limit 1"
    raw = call(XSIAM_MCP, xsiam_sid, "run_xql_query",
               {"query": raw_q}, rid=200)
    reply = (raw or {}).get("reply", {}) or {}
    n_raw = reply.get("number_of_results", 0)
    status = reply.get("status")
    most_recent = 0
    if n_raw > 0:
        row = reply["results"]["data"][0]
        most_recent = int(row.get("_time", 0)) // 1000  # ms → s
    # Only count events that arrived AFTER the batch started
    fresh = 1 if most_recent >= batch_started else 0
    v["raw_query_status"] = status
    v["events_landed"] = fresh
    v["most_recent_ts"] = most_recent

    # XDM query (only if events landed)
    if fresh:
        dm_q = f"config timeframe = 1d | datamodel dataset = {dataset} | sort desc _time | fields xdm.* | limit 1"
        dm = call(XSIAM_MCP, xsiam_sid, "run_xql_query",
                  {"query": dm_q}, rid=201)
        dr = (dm or {}).get("reply", {}) or {}
        n_dm = dr.get("number_of_results", 0)
        v["xdm_rows"] = n_dm
        if n_dm > 0:
            row = dr["results"]["data"][0]
            populated_xdm = [k for k, val in row.items()
                             if val not in (None, "", "null") and k.startswith("xdm.")]
            v["xdm_populated_count"] = len(populated_xdm)
            v["xdm_populated_sample"] = populated_xdm[:8]
    else:
        v["xdm_rows"] = 0

    v["status"] = "done"
    if fresh and v.get("xdm_rows", 0) > 0:
        v["notes"] = f"landed; XDM={v.get('xdm_populated_count', 0)}"
    elif fresh:
        v["notes"] = "landed; XDM 0 (likely composite-JSON synthesis gap)"
    else:
        v["notes"] = "dataset has no fresh events"


def kill_worker(slug, state, agent_sid):
    v = state["vendors"][slug]
    if v.get("worker_id"):
        call(AGENT_MCP, agent_sid, "phantom_kill_worker",
             {"worker_id": v["worker_id"]}, rid=300, https=True)


# ── Main ─────────────────────────────────────────────────────────
state = load_state()
pending = [s for s in VENDORS if state["vendors"][s].get("status") == "pending"]

if not pending:
    print(f"All {len(VENDORS)} vendors already processed.")
    write_final_report(state)
    print(f"Final report at {REPORT_PATH}")
    raise SystemExit(2)

batch = pending[:BATCH_SIZE]
print(f"Processing batch of {len(batch)} vendors:")
for s in batch:
    print(f"  - {s}")

agent_sid = open_session(AGENT_MCP, https=True)
xsiam_sid = open_session(XSIAM_MCP, https=False)
print(f"\nagent_sid={agent_sid}, xsiam_sid={xsiam_sid}")

batch_started = int(time.time())

# Phase 1: fire workers
print("\n=== Phase 1 — create workers ===")
for slug in batch:
    result = smoke_vendor(slug, agent_sid, xsiam_sid)
    state["vendors"][slug].update(result)
    wd = "✅" if result.get("worker_created") else "❌"
    print(f"  {wd} {slug[:60]:60s} {result.get('worker_id', result.get('notes', ''))[:60]}")

save_state(state)

# Phase 2: wait for ingest
print(f"\n=== Phase 2 — wait {WAIT_SECONDS}s for ingest ===")
for i in range(WAIT_SECONDS // 30):
    time.sleep(30)
    print(f"  +{(i + 1) * 30}s")

# Phase 3: verify
print("\n=== Phase 3 — verify ===")
for slug in batch:
    verify_vendor(slug, state, xsiam_sid, batch_started)
    v = state["vendors"][slug]
    ev = "✅" if v.get("events_landed") else "❌"
    print(f"  {ev} {slug[:60]:60s} {v.get('notes', '')[:60]}")

# Phase 4: cleanup
print("\n=== Phase 4 — kill workers ===")
for slug in batch:
    kill_worker(slug, state, agent_sid)

save_state(state)

# Summary
remaining = sum(1 for s in VENDORS if state["vendors"][s].get("status") == "pending")
print(f"\nDone with batch. {remaining} vendors remaining.")
if remaining == 0:
    write_final_report(state)
    print(f"All done; final report written to {REPORT_PATH}")
