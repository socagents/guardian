"""SP-4 deployed smoke — data-source edit + versioning overlay.

Runs INSIDE phantom_agent: `docker exec -i phantom_agent python3 < _sp4_smoke.py`
Hits the embedded MCP REST surface at https://localhost:8080 (bearer MCP_TOKEN,
self-signed TLS) and reads data_source_versions.db directly to prove the
v1-baseline rule. Restores the original how_to_use at the end so the dev
install's visible content is left unchanged (version history is the durable
proof). Prints a PASS/FAIL line per check.
"""
from __future__ import annotations

import json
import os
import ssl
import sqlite3
import urllib.request

BASE = "https://localhost:8080"
TOKEN = os.environ["MCP_TOKEN"]
PACK, RULE, DS = "ServiceNow", "ServiceNow", "servicenow_servicenow_raw"
COMPOSITE = f"{PACK}/{RULE}/{DS}"
DB = os.path.join(os.environ.get("PHANTOM_DATA_DIR", "/app/data"), "data_source_versions.db")

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


# 0. Capture the original how_to_use.
st, schema = _req("GET", f"/api/v1/data-sources/{PACK}/{RULE}/{DS}/schema")
orig = (schema.get("data_source") or {}).get("how_to_use") or ""
check(st == 200 and bool(orig), f"GET schema baseline (status {st}, how_to_use {len(orig)} chars)")

MARK = "<!-- SP-4 smoke marker -->"

# 1. First edit → version 2 (v1 baseline auto-created).
st, out = _req("PUT", f"/api/v1/data-sources/{PACK}/{RULE}/{DS}/edit",
               {"how_to_use": orig + "\n\n" + MARK, "note": "sp4 smoke edit 1"})
check(st == 200 and out.get("ok") and out.get("version") == 2,
      f"PUT edit #1 → ok + version==2 (got status {st}, {out})")

# 2. Overlay live: GET schema reflects the edit.
st, schema = _req("GET", f"/api/v1/data-sources/{PACK}/{RULE}/{DS}/schema")
htu = (schema.get("data_source") or {}).get("how_to_use") or ""
check(st == 200 and MARK in htu, "GET schema reflects edit (overlay live)")

# 3. Catalog not broken by the overlay.
st, cat = _req("GET", "/api/v1/data-sources/catalog")
rows = cat.get("rows") or cat.get("data_sources") or []
sn = [r for r in rows if r.get("pack_name") == PACK]
check(st == 200 and len(sn) >= 1, f"GET catalog OK, ServiceNow present ({len(sn)} row(s))")

# 4. Re-edit → version 3 (increment + baseline preserved).
st, out = _req("PUT", f"/api/v1/data-sources/{PACK}/{RULE}/{DS}/edit",
               {"how_to_use": orig + "\n\n" + MARK + " (edit 2)", "note": "sp4 smoke edit 2"})
check(st == 200 and out.get("version") == 3, f"PUT edit #2 → version==3 (got {out})")

# 5. v1-baseline rule: read the version store directly.
try:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    vrows = con.execute(
        "SELECT version, author, is_current FROM data_source_versions "
        "WHERE data_source_id=? ORDER BY version", (COMPOSITE,)).fetchall()
    con.close()
    authors = [(r["version"], r["author"]) for r in vrows]
    currents = [r["version"] for r in vrows if r["is_current"]]
    v1_baseline = any(r["version"] == 1 and r["author"] == "bundle-baseline" for r in vrows)
    check(v1_baseline, f"version store: v1 == bundle-baseline (authors {authors})")
    check(len(currents) == 1 and currents[0] == 3,
          f"version store: exactly one current == v3 (currents {currents})")
except Exception as e:  # noqa: BLE001
    check(False, f"version store read failed: {e}")

# 6. Restore the original (leaves visible content clean; history kept → v4).
st, out = _req("PUT", f"/api/v1/data-sources/{PACK}/{RULE}/{DS}/edit",
               {"how_to_use": orig, "note": "sp4 smoke restore original"})
st2, schema = _req("GET", f"/api/v1/data-sources/{PACK}/{RULE}/{DS}/schema")
restored = (schema.get("data_source") or {}).get("how_to_use") or ""
check(st == 200 and out.get("version") == 4 and restored.strip() == orig.strip(),
      f"restore → v4 + content == original (version {out.get('version')}, match {restored.strip()==orig.strip()})")

passed = sum(1 for ok, _ in results if ok)
print(f"\n=== SP-4 smoke: {passed}/{len(results)} checks passed ===")
