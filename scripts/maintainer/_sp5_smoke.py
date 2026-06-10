"""SP-5 deployed smoke — data-source version history + rollback.

Runs INSIDE phantom_agent: `docker exec -i phantom_agent python3 < _sp5_smoke.py`.
Robust to PRE-EXISTING version history (the version store persists across
deploys and there is no delete) — assertions are RELATIVE to the current max
version, never hardcoded. Edits ServiceNow twice, lists/views history, rolls
back to v1 (the pristine baseline, which also restores original content),
verifies the overlay reflects the rollback, and confirms the two SP-5 agent
tools are advertised. Prints PASS/FAIL per check.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.request

BASE = "https://localhost:8080"
TOKEN = os.environ["MCP_TOKEN"]
PACK, RULE, DS = "ServiceNow", "ServiceNow", "servicenow_servicenow_raw"
MCP_URL = f"{BASE}/api/v1/stream/mcp"
base = f"/api/v1/data-sources/{PACK}/{RULE}/{DS}"

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

results: list[tuple[bool, str]] = []


def _req(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, context=_CTX, timeout=20) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def check(ok: bool, label: str) -> None:
    results.append((ok, label))
    print(f"{'PASS' if ok else 'FAIL'}  {label}")


def _mcp_post(payload: dict, session: str | None) -> tuple[dict, str | None]:
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


def _versions() -> list[dict]:
    _, vl = _req("GET", f"{base}/versions")
    return vl.get("versions") or []


MARK = "<!-- SP-5 smoke -->"

# 0. capture current state (robust to prior history)
st, schema = _req("GET", f"{base}/schema")
orig = (schema.get("data_source") or {}).get("how_to_use") or ""
start = _versions()
base_max = max((v["version"] for v in start), default=0)
check(st == 200 and bool(orig), f"GET schema baseline ({len(orig)} chars; {len(start)} pre-existing versions, max v{base_max})")

# 1. two edits → consecutive increments from base_max
_, o1 = _req("PUT", f"{base}/edit", {"how_to_use": orig + "\n" + MARK + " E1", "note": "sp5 e1"})
_, o2 = _req("PUT", f"{base}/edit", {"how_to_use": orig + "\n" + MARK + " E2", "note": "sp5 e2"})
v_e1, v_e2 = o1.get("version"), o2.get("version")
check(o1.get("ok") and o2.get("ok") and v_e2 == v_e1 + 1,
      f"two edits → consecutive versions (v{v_e1}, v{v_e2})")

# 2. GET versions → grew by 2; current == v_e2; v1 is bundle-baseline; metadata-only
vers = _versions()
nums = [v["version"] for v in vers]
current = [v["version"] for v in vers if v["is_current"]]
check(len(vers) == len(start) + 2, f"history grew by 2 ({len(start)}→{len(vers)})")
check(current == [v_e2], f"current == [v{v_e2}] (got {current})")
check(vers[0]["version"] == 1 and vers[0]["author"] == "bundle-baseline",
      f"v1 == bundle-baseline (v1 author {vers[0]['author']!r})")
check("yaml_snapshot" not in vers[0], "versions list is metadata-only (no yaml_snapshot)")

# 3. GET versions/{my edit} → full snapshot contains E1
st, ve = _req("GET", f"{base}/versions/{v_e1}")
snap = (ve.get("version") or {}).get("yaml_snapshot") or ""
check(st == 200 and "E1" in snap, f"GET versions/{v_e1} → contains E1 edit")

# 4. GET versions/1 → pristine original (no smoke markers)
st, v1 = _req("GET", f"{base}/versions/1")
v1snap = (v1.get("version") or {}).get("yaml_snapshot") or ""
check(st == 200 and MARK not in v1snap and "ServiceNow" in v1snap, "GET versions/1 → pristine original")

# 5. GET versions/99999 → 404
st, _ = _req("GET", f"{base}/versions/99999")
check(st == 404, f"GET versions/99999 → 404 (got {st})")

# 6. rollback to v1 → new version == v_e2 + 1 (non-destructive)
st, rb = _req("POST", f"{base}/rollback", {"version": 1})
v_rb = rb.get("version")
check(st == 200 and rb.get("ok") and v_rb == v_e2 + 1, f"POST rollback v1 → new v{v_rb} (expected v{v_e2 + 1})")

# 7. history preserved (grew by 1 more); current == v_rb; note references v1
vers = _versions()
current = [v["version"] for v in vers if v["is_current"]]
v_rb_note = next((v["note"] for v in vers if v["version"] == v_rb), "")
check(len(vers) == len(start) + 3 and current == [v_rb],
      f"history preserved + current == v{v_rb} ({len(vers)} versions, cur {current})")
check("v1" in (v_rb_note or ""), f"rollback note references v1 (note {v_rb_note!r})")

# 8. overlay reflects rollback: schema content has NO smoke markers (rolled back past edits)
st, schema = _req("GET", f"{base}/schema")
htu = (schema.get("data_source") or {}).get("how_to_use") or ""
check(st == 200 and MARK not in htu, "GET schema reflects rollback (smoke markers gone)")

# 9. rollback unknown version → 400
st, bad = _req("POST", f"{base}/rollback", {"version": 99999})
check(st == 400 and bad.get("ok") is False, f"rollback unknown version → 400 (got {st})")

# 10. agent tools advertised
try:
    _, sid = _mcp_post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                                   "clientInfo": {"name": "sp5", "version": "1.0"}}}, None)
    _mcp_post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, sid)
    resp, _ = _mcp_post({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, sid)
    names = {t["name"] for t in (resp.get("result") or {}).get("tools", [])}
    have = sorted(n for n in names if n in {"data_sources_list_versions", "data_sources_rollback"})
    check(have == ["data_sources_list_versions", "data_sources_rollback"],
          f"agent tools advertised ({have})")
except Exception as e:  # noqa: BLE001
    check(False, f"tools/list failed: {e}")

passed = sum(1 for ok, _ in results if ok)
print(f"\n=== SP-5 smoke: {passed}/{len(results)} checks passed ===")
