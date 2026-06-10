#!/usr/bin/env python3
"""E2E smoke test that drives `phantom_create_data_worker` via MCP — does
NOT bypass to direct UDP. Goal: prove the MCP tool chain (xlog OverrideSender
→ broker → XSIAM ingest) works end-to-end for the 22 validated vendors.

The diagnostic axis is: how many XDM fields does the dataset receive after
the MCP-tool path emits, vs the direct-UDP shape we used in earlier batches?

Discrepancies surface where to fix the MCP/xLog tool — currently suspected:
- `_generate_value()` in xlog/app/dynamic_schema.py doesn't honor `type: json`
  so composite fields like Okta's `actor` get a random string instead of a
  JSON-string-shaped value.

Usage (from local dev machine with IAP tunnel already open):

  PYTHONPATH=$PWD python3 scripts/maintainer/e2e_smoke_via_mcp_tool.py \\
      --vendor-slug Okta__OktaModelingRules_2_0__okta_okta_raw

Resolves the vendor's data_source.yaml → builds schema_override from fields[]
→ calls phantom_create_data_worker via the agent's embedded MCP → waits 120s
→ runs `run_xql_query` via the same MCP path → reports XDM saturation.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_ROOT = REPO_ROOT / "bundles" / "spark" / "data-sources"

# The agent's embedded MCP is reachable through phantom-vm at TLS port 8081
# (proxied → loopback 8080). For the script we tunnel via IAP — relies on
# `gcloud compute start-iap-tunnel` running with localhost:8081 mapped to
# remote 8081.
AGENT_MCP = "https://localhost:8081/api/v1/stream/mcp"

# The XSIAM connector's per-instance MCP. Inside the phantom-vm network it's
# at `phantom-connector-xsiam-Cortex_XSIAM:9000`. We hit the agent's proxy
# at /api/agent/connectors/<id>/instances/<name>/tools/call instead.
XSIAM_CONNECTOR_MCP = "https://localhost:8081/api/v1/stream/mcp"  # agent dispatches


def post_jsonrpc(url: str, body: dict, headers: dict, ignore_ssl: bool = True) -> tuple[str, dict]:
    """POST a JSON-RPC body and return (body_text, response_headers)."""
    import ssl
    ctx = ssl.create_default_context()
    if ignore_ssl:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180, context=ctx) as r:
        return r.read().decode(), dict(r.headers)


def parse_sse_result(text: str) -> dict:
    """Pull the first `data:` JSON line out of an SSE stream + parse it."""
    for ln in text.split("\n"):
        if ln.startswith("data:"):
            try:
                frame = json.loads(ln[5:].strip())
                if "result" in frame:
                    content = frame["result"].get("content", [])
                    if content:
                        return json.loads(content[0].get("text", "{}"))
                if "error" in frame:
                    return {"_jsonrpc_error": frame["error"]}
            except Exception:
                pass
    return {}


def load_yaml(slug: str) -> dict:
    p = BUNDLE_ROOT / slug / "data_source.yaml"
    if not p.exists():
        raise SystemExit(f"data_source.yaml not found for slug: {slug}")
    return yaml.safe_load(p.read_text())


def build_schema_override(yaml_doc: dict) -> list[dict]:
    """Extract a phantom_create_data_worker-friendly schema_override list
    from the YAML's fields[] array.

    For nested-JSON vendors (Okta, AWS CT, Azure AD, etc.) the YAML carries
    BOTH the top-level composite (`actor` with type=json) AND the dotted-
    key leaves (`actor.alternateId`, `actor.id`, …). The MR reads the
    composite as a JSON-string and `json_extract_scalar` parses inside.
    Passing the leaves as flat CEF extensions would emit
    `actor.alternateId=foo` keys that don't match what the MR reads.

    So this filter drops any field whose name contains a dot AND whose
    parent name is already in the override set. Result: only top-level
    fields (and any leaves whose parent isn't present) get into the
    schema_override.
    """
    raw = [f for f in yaml_doc.get("fields", []) if isinstance(f, dict) and f.get("name")]
    top_level_names = {f["name"] for f in raw if "." not in f["name"]}

    out = []
    for f in raw:
        if f.get("is_meta"):
            continue
        name = f["name"]
        if "." in name:
            # Leaf — skip if its top-level parent is present (the MR reads
            # the parent composite, not the dotted key).
            parent = name.split(".")[0]
            if parent in top_level_names:
                continue
        out.append({
            "name": name,
            "type": f.get("type") or "string",
            "is_array": bool(f.get("is_array", False)),
        })
    return out


def open_mcp_session(token: str) -> str:
    """Open an MCP session via /initialize. Returns the session id."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    _, resp_headers = post_jsonrpc(
        AGENT_MCP,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "e2e-smoke-via-mcp", "version": "1.0"},
            },
        },
        headers,
    )
    sid = resp_headers.get("mcp-session-id") or resp_headers.get("Mcp-Session-Id")
    if not sid:
        raise SystemExit("MCP session id missing in /initialize response")
    # notifications/initialized handshake
    headers["mcp-session-id"] = sid
    post_jsonrpc(
        AGENT_MCP,
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        headers,
    )
    return sid


def call_tool(sid: str, token: str, name: str, arguments: dict, rpc_id: int = 99) -> dict:
    """Call an MCP tool and return the parsed SSE result."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "mcp-session-id": sid,
    }
    body_text, _ = post_jsonrpc(
        AGENT_MCP,
        {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        headers,
    )
    return parse_sse_result(body_text)


def run_xql_query(sid: str, token: str, query: str) -> dict:
    """Wraps run_xql_query. Returns reply.status + reply.number_of_results + reply.results."""
    res = call_tool(
        sid,
        token,
        "run_xql_query",
        {
            "request": {
                "query": query,
                "tenant_timeframe": {"relativeTime": 1800000},  # last 30 min
            }
        },
        rpc_id=2001,
    )
    return res


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--vendor-slug",
        required=True,
        help="Directory name under bundles/spark/data-sources/ (e.g. "
        "'Okta__OktaModelingRules_2_0__okta_okta_raw')",
    )
    parser.add_argument(
        "--broker",
        default="udp:10.10.0.8:514",
        help="Destination for createDataWorker (default udp:10.10.0.8:514)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=3,
        help="How many CEF events to send (default 3)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=2,
        help="Seconds between sends (default 2)",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=120,
        help="How long to wait for XSIAM ingestion before querying (default 120)",
    )
    args = parser.parse_args()

    token = os.environ.get("MCP_TOKEN") or os.environ.get("PHANTOM_BEARER")
    if not token:
        print("ERROR: set MCP_TOKEN or PHANTOM_BEARER env", file=sys.stderr)
        return 1

    yaml_doc = load_yaml(args.vendor_slug)
    vendor = yaml_doc["vendor"]
    product = yaml_doc["product"]
    dataset = yaml_doc["dataset_name"]
    schema_override = build_schema_override(yaml_doc)

    marker = f"mcp-smoke-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    worker_name = f"smoke-{args.vendor_slug[:24]}-{int(time.time())}"

    print(f"slug={args.vendor_slug}")
    print(f"vendor={vendor} product={product}")
    print(f"dataset={dataset}")
    print(f"fields_in_override={len(schema_override)}")
    print(f"marker={marker}")
    print(f"worker_name={worker_name}")
    print()

    sid = open_mcp_session(token)
    print(f"MCP session opened: {sid}")

    # Fire phantom_create_data_worker via MCP.
    # We pass `observable_overrides` with the marker baked into a unique
    # field that won't collide with vendor schema. Most MR queries can
    # filter via `xdm.event.id contains "<marker>"` if the MR populates
    # event.id from any of our extension keys.
    create_args = {
        "request": {
            "name": worker_name,
            "type": "CEF",
            "destination": args.broker,
            "count": args.count,
            "interval": args.interval,
            "vendor": vendor,
            "product": product,
            "version": "1.0",
            "fields": schema_override,
            "schema_override": schema_override,
            # Force a vendor-neutral marker field — uuid for Okta, _id for
            # AWS CT, etc. Most MRs hoist this into xdm.event.id.
            "observables_dict": {
                "marker": [marker],
                "uuid": [marker],  # Okta routes via uuid
                "_id": [marker],   # AWS CT
                "Id": [marker],    # AWS Security Hub
                "messageID": [marker],  # ProofPoint
            },
        }
    }
    res = call_tool(sid, token, "phantom_create_data_worker", create_args, rpc_id=10)
    print(f"createDataWorker result: {json.dumps(res, default=str)[:400]}")

    if res.get("_jsonrpc_error"):
        print(f"\nERROR — JSON-RPC error in createDataWorker: {res['_jsonrpc_error']}")
        return 2

    # Wait for the worker to fire several ticks + XSIAM ingest.
    print(f"\nWaiting {args.wait_seconds}s for ingestion...")
    for i in range(args.wait_seconds // 30):
        time.sleep(30)
        print(f"  +{(i + 1) * 30}s")

    # Raw landing check.
    raw_q = f"dataset = {dataset} | filter _raw_log contains \"{marker}\" | limit 5"
    raw = run_xql_query(sid, token, raw_q)
    raw_reply = (raw or {}).get("reply", {}) or {}
    raw_n = raw_reply.get("number_of_results", 0)
    raw_status = raw_reply.get("status")
    print(f"\nRAW LANDING: status={raw_status}, n={raw_n}")

    # XDM materialization check.
    dm_q = f"datamodel dataset = {dataset} | filter xdm.event.id contains \"{marker}\" | fields xdm.* | limit 1"
    dm = run_xql_query(sid, token, dm_q)
    dm_reply = (dm or {}).get("reply", {}) or {}
    dm_n = dm_reply.get("number_of_results", 0)
    dm_status = dm_reply.get("status")
    print(f"XDM MATERIALIZATION: status={dm_status}, n={dm_n}")
    if dm_status == "SUCCESS" and dm_n > 0:
        row = dm_reply["results"]["data"][0]
        populated = {k: v for k, v in row.items() if v not in (None, "", "null") and k.startswith("xdm.")}
        print(f"\n✅ XDM populated: {len(populated)} fields")
        for k in sorted(populated):
            print(f"  {k:42} = {str(populated[k])[:75]}")
    else:
        # Fallback: try filtering by marker substring on any raw column
        # (the MR's PR-extracted columns), not xdm.event.id specifically.
        fallback_q = (
            f"datamodel dataset = {dataset} | comp count() as n | limit 1"
        )
        fb = run_xql_query(sid, token, fallback_q)
        fb_n = (fb or {}).get("reply", {}).get("results", {}).get("data", [{}])
        print(f"\n❌ no XDM by marker — falling back to dataset-presence: {fb_n}")

    # Cleanup: stop the worker so it doesn't keep emitting. phantom_kill_worker
    # takes worker_id (UUID) not name — list_workers gives us that UUID.
    print(f"\nListing workers to find {worker_name}...")
    lw = call_tool(sid, token, "phantom_list_workers", {}, rpc_id=15)
    worker_uuid = None
    for w in (lw or []) if isinstance(lw, list) else []:
        if isinstance(w, dict) and w.get("name") == worker_name:
            worker_uuid = w.get("worker")
            break
    if worker_uuid:
        print(f"Killing worker {worker_uuid} ({worker_name})...")
        stop_res = call_tool(
            sid, token, "phantom_kill_worker",
            {"request": {"worker_id": worker_uuid}}, rpc_id=20,
        )
        print(f"kill result: {json.dumps(stop_res, default=str)[:200]}")
    else:
        print(f"Worker {worker_name} not found in list — already stopped?")

    return 0 if dm_status == "SUCCESS" and dm_n > 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
