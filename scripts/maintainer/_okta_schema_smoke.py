"""#104 deployed smoke — schema drawer resolves YAML-only datasets.

Runs INSIDE phantom_agent: `docker exec -i phantom_agent python3 < _okta_schema_smoke.py`.
Reproduces the operator's bug: the UI schema route + the data_sources_get_schema
tool must open BOTH Okta/OktaModelingRules datasets — okta_okta_raw (in cortex)
AND okta_sso_raw (YAML-only, not enumerated by cortex). Pre-fix, okta_sso_raw
404'd. Read-only.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.request

BASE = "https://localhost:8080"
TOKEN = os.environ["MCP_TOKEN"]
MCP_URL = f"{BASE}/api/v1/stream/mcp"
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
results: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    results.append((ok, label))
    print(f"{'PASS' if ok else 'FAIL'}  {label}")


def _schema(pack: str, rule: str, dataset: str) -> tuple[int, dict]:
    url = f"{BASE}/api/v1/data-sources/{pack}/{rule}/{dataset}/schema"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, context=_CTX, timeout=20) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _mcp_post(payload, session):
    req = urllib.request.Request(MCP_URL, data=json.dumps(payload).encode(), method="POST")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    if session:
        req.add_header("mcp-session-id", session)
    with urllib.request.urlopen(req, context=_CTX, timeout=20) as r:
        sid = r.headers.get("mcp-session-id") or session
        raw = r.read().decode()
    body = None
    if raw.lstrip().startswith("{"):
        body = json.loads(raw)
    else:
        for line in raw.splitlines():
            if line.startswith("data:"):
                try:
                    body = json.loads(line[5:].strip())
                except Exception:  # noqa: BLE001
                    pass
    return (body or {}), sid


# 1. The bug: okta_sso_raw drawer schema (was a 404)
st, body = _schema("Okta", "OktaModelingRules", "okta_sso_raw")
ds = body.get("data_source") or {}
fields = ds.get("fields") or []
check(st == 200 and ds.get("dataset_name") == "okta_sso_raw" and len(fields) > 0,
      f"okta_sso_raw schema → 200 + {len(fields)} fields (status {st})")

# 2. No regression: okta_okta_raw still opens
st2, body2 = _schema("Okta", "OktaModelingRules", "okta_okta_raw")
ds2 = body2.get("data_source") or {}
check(st2 == 200 and len(ds2.get("fields") or []) > 0,
      f"okta_okta_raw schema → 200 + {len(ds2.get('fields') or [])} fields (status {st2})")

# 3. The two are distinct (different field counts)
check(len(fields) != len(ds2.get("fields") or []),
      f"distinct datasets: sso={len(fields)} flds vs okta={len(ds2.get('fields') or [])} flds")

# 4. Agent tool path: data_sources_get_schema on okta_sso_raw
try:
    _, sid = _mcp_post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                                   "clientInfo": {"name": "okta-smoke", "version": "1.0"}}}, None)
    _mcp_post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, sid)
    resp, _ = _mcp_post({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                        "params": {"name": "data_sources_get_schema",
                                   "arguments": {"data_source_id": "Okta/OktaModelingRules/okta_sso_raw"}}}, sid)
    # tools/call returns content; the tool's dict is in structuredContent or content[0].text
    res = resp.get("result") or {}
    txt = ""
    if res.get("structuredContent"):
        txt = json.dumps(res["structuredContent"])
    else:
        for c in res.get("content", []):
            txt += c.get("text", "")
    tool_ok = '"ok": true' in txt.lower() or '"ok":true' in txt.lower()
    check(tool_ok and "okta_sso_raw" in txt, "data_sources_get_schema(okta_sso_raw) tool → ok + fields")
except Exception as e:  # noqa: BLE001
    check(False, f"tool path failed: {e}")

passed = sum(1 for ok, _ in results if ok)
print(f"\n=== #104 Okta schema smoke: {passed}/{len(results)} checks passed ===")
