"""SP-6 deployed smoke — data-source export-by-version.

Runs INSIDE phantom_agent: `docker exec -i phantom_agent python3 < _sp6_smoke.py`.
Verifies: an edit makes the default export return the current (edited) content;
?version=1 returns the pristine baseline with a versioned filename; an unknown
version → 404. Robust to pre-existing history (the store persists). Read-only
except for one marker edit (left as a new current version; harmless).
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.request

BASE = "https://localhost:8080"
TOKEN = os.environ["MCP_TOKEN"]
PACK, RULE, DS = "ServiceNow", "ServiceNow", "servicenow_servicenow_raw"
base = f"/api/v1/data-sources/{PACK}/{RULE}/{DS}"

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

results: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    results.append((ok, label))
    print(f"{'PASS' if ok else 'FAIL'}  {label}")


def _edit(payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{BASE}{base}/edit", data=data, method="PUT")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, context=_CTX, timeout=20) as r:
        return json.loads(r.read() or b"{}")


def _export(version: int | None) -> tuple[int, str, str]:
    """Return (status, body_text, content_disposition)."""
    url = f"{BASE}{base}/export" + (f"?version={version}" if version is not None else "")
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, context=_CTX, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "replace"), r.headers.get("content-disposition", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), ""


MARK = "<!-- SP-6 export smoke -->"

# Capture the pristine baseline (v1) content up front for comparison.
st_v1, v1_body, v1_cd = _export(1)
check(st_v1 == 200 and "vendor:" in v1_body and MARK not in v1_body,
      f"export?version=1 → pristine baseline YAML (status {st_v1})")
check("servicenow_servicenow_raw.v1.yaml" in v1_cd,
      f"version export filename is <dataset>.v1.yaml (cd: {v1_cd!r})")

# Edit → default export reflects the new current content.
out = _edit({"how_to_use": "EXPORT SMOKE " + MARK, "note": "sp6 export smoke"})
new_v = out.get("version")
check(out.get("ok") and isinstance(new_v, int), f"edit ok → v{new_v}")

st_cur, cur_body, cur_cd = _export(None)
check(st_cur == 200 and MARK in cur_body, "default export reflects current (edited) content")
check("servicenow_servicenow_raw.yaml" in cur_cd and ".v" not in cur_cd.split("filename=")[-1],
      f"default export filename is <dataset>.yaml (cd: {cur_cd!r})")

# Export the specific just-created version → contains the marker too.
st_nv, nv_body, nv_cd = _export(new_v)
check(st_nv == 200 and MARK in nv_body and f".v{new_v}.yaml" in nv_cd,
      f"export?version={new_v} → that version's YAML + versioned filename")

# v1 still pristine (export is read-only; the edit didn't touch v1).
st_v1b, v1b_body, _ = _export(1)
check(st_v1b == 200 and MARK not in v1b_body, "export?version=1 still pristine (no marker)")

# Unknown version → 404.
st_bad, _, _ = _export(99999)
check(st_bad == 404, f"export?version=99999 → 404 (got {st_bad})")

passed = sum(1 for ok, _ in results if ok)
print(f"\n=== SP-6 smoke: {passed}/{len(results)} checks passed ===")
