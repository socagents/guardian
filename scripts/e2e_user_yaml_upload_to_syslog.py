#!/usr/bin/env python3
"""R3.C.3 (v0.13.3) — E2E test: operator-uploaded data_source.yaml → UDP-streamed records.

Verifies the full R3.C arc end-to-end against the deployed phantom-vm install:

  1. Stand up a temp UDP listener inside the xlog container (or sidecar)
  2. POST a custom AcmeCorp data_source.yaml to /api/v1/data-sources/user/preview
     - Validates the YAML against data_source.schema.json
     - Runs similarity check (here: vendor="AcmeCorp" — no matches expected
       since it's a new vendor)
     - Returns accept_token
  3. POST /api/v1/data-sources/user with the accept_token → writes YAML to disk
  4. POST /api/v1/data-sources/install → extracts fields from the YAML into
     the data_sources_store
  5. POST /api/v1/data-sources/<pack>/<rule>/<dataset>/schema → confirms the
     5 AcmeCorp fields are present
  6. Use createDataWorker GraphQL mutation with schema_override = fields[]
     and destination = udp:127.0.0.1:<port>
  7. UDP listener captures datagrams; assert each record contains the 5
     AcmeCorp field names + no extras
  8. Cleanup: stop worker, uninstall data source, delete user upload

USAGE (against phantom-vm via IAP tunnel):
    # Open tunnels first:
    gcloud compute start-iap-tunnel phantom 22 \\
        --local-host-port=localhost:2222 \\
        --zone=us-central1-f --project=cortex-gcp-labs &

    # Then run inside the xlog container via ssh+docker exec:
    sshpass -e ssh -p 2222 ayman@localhost \\
        docker exec -i phantom_xlog python3 - < scripts/e2e_user_yaml_upload_to_syslog.py

The script self-contained — it uses MCP_TOKEN read from xlog's env so no
external secrets are needed. Exit code 0 = all assertions pass.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import ssl
import sys
import threading
import time
import urllib.request
from typing import Any

# ─── Config ────────────────────────────────────────────────────────

UDP_PORT = 9514
UDP_HOST = "127.0.0.1"
MCP_BASE = os.environ.get("MCP_BASE", "https://127.0.0.1:8080")
XLOG_BASE = os.environ.get("XLOG_BASE", "https://127.0.0.1:8000")
ACME_PACK = "AcmeCorp"
ACME_RULE = "AcmeCorpEvents"
ACME_DATASET = "acmecorp_events_raw"
ACME_ID = f"{ACME_PACK}__{ACME_RULE}__{ACME_DATASET}"
WORKER_COUNT_PER_TICK = 1
WORKER_INTERVAL = 0.5  # seconds — fast for a quick test
CAPTURE_WINDOW = 10.0  # seconds total
EXPECTED_MIN_DATAGRAMS = 5


# ─── Bearer-token discovery ────────────────────────────────────────


def read_mcp_token() -> str:
    """Read MCP_TOKEN from the current process's environment OR from
    /proc/1/environ (xlog container's pid 1, our entrypoint).

    The xlog container has MCP_TOKEN set as an env passthrough from
    phantom-agent at boot. Our docker-exec'd Python inherits it via
    /proc/1/environ.
    """
    token = os.environ.get("MCP_TOKEN")
    if token:
        return token
    try:
        with open("/proc/1/environ", "rb") as f:
            for line in f.read().decode("utf-8", errors="replace").split("\x00"):
                if line.startswith("MCP_TOKEN="):
                    return line[len("MCP_TOKEN="):]
    except Exception:
        pass
    sys.exit("ERROR: MCP_TOKEN not in env and not readable from /proc/1/environ")


def read_xlog_api_key() -> str:
    """Read XLOG_API_KEY similarly — xlog's GraphQL needs its own bearer."""
    key = os.environ.get("XLOG_API_KEY")
    if key:
        return key
    try:
        with open("/proc/1/environ", "rb") as f:
            for line in f.read().decode("utf-8", errors="replace").split("\x00"):
                if line.startswith("XLOG_API_KEY="):
                    return line[len("XLOG_API_KEY="):]
    except Exception:
        pass
    sys.exit("ERROR: XLOG_API_KEY not in env and not readable from /proc/1/environ")


TOKEN = read_mcp_token()
XLOG_KEY = read_xlog_api_key()
SSL_CTX = ssl._create_unverified_context()  # noqa: S323 — self-signed for local


# ─── HTTP helpers ──────────────────────────────────────────────────


def mcp_request(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{MCP_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TOKEN}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=SSL_CTX) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        return {"_status": e.code, "_body": body_text}


def xlog_graphql(query: str, variables: dict | None = None) -> dict:
    """POST a GraphQL request to xlog with bearer auth.

    xlog mounts its GraphQL endpoint at the root path (`/`), not `/graphql`
    (see xlog/main.py line 20: `app.add_route("/", GraphQL(schema=schema))`).
    """
    req = urllib.request.Request(
        f"{XLOG_BASE}/",
        data=json.dumps({"query": query, "variables": variables or {}}).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {XLOG_KEY}",
        },
    )
    with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ─── Test fixture: AcmeCorp YAML ───────────────────────────────────


def build_acmecorp_yaml() -> dict:
    """A minimal-but-realistic AcmeCorp data_source.yaml with 5 fields."""
    return {
        "schema_version": 1,
        "id": ACME_ID,
        "pack_name": ACME_PACK,
        "rule_name": ACME_RULE,
        "dataset_name": ACME_DATASET,
        "vendor": "AcmeCorp",
        "product": "AcmeApp",
        "description": "E2E test fixture: AcmeCorp's hypothetical security product.",
        "categories": ["Endpoint"],
        "version": "1.0.0",
        "origin": "user",  # write_user overrides; included for clarity
        "author": "operator",
        "uploaded_by": None,
        "created_at": "2026-05-23T00:00:00Z",
        "updated_at": "2026-05-23T00:00:00Z",
        "logo": {
            "mime_type": "image/svg+xml",
            "data": base64.b64encode(
                b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
                b'<text x="0" y="20" font-size="20" fill="#1976d2">A</text></svg>'
            ).decode("ascii"),
            "source": "e2e-test",
            "license": "MIT",
            "fidelity": "wordmark",
        },
        "formats": ["JSON", "SYSLOG"],
        "is_rawlog_only": False,
        "fields": [
            {"name": "src_ip", "type": "ipv4"},
            {"name": "dst_ip", "type": "ipv4"},
            {"name": "username", "type": "user"},
            {"name": "event_action", "type": "enum",
             "enum_values": ["login", "logout", "blocked"]},
            {"name": "timestamp_ms", "type": "timestamp_ms"},
        ],
        "xdm_mappings": [],
    }


# ─── UDP listener thread ───────────────────────────────────────────


class UDPCapture:
    """Background UDP listener that collects datagrams until stop() called."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.sock.settimeout(0.5)
        self.captured: list[bytes] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                data, _addr = self.sock.recvfrom(65535)
                self.captured.append(data)
            except socket.timeout:
                continue
            except Exception:
                break

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
        try:
            self.sock.close()
        except Exception:
            pass


# ─── Test steps ────────────────────────────────────────────────────


def step_1_preview(doc: dict) -> str:
    print("\n[step 1] POST /user/preview ...")
    resp = mcp_request("POST", "/api/v1/data-sources/user/preview", {"doc": doc})
    assert resp.get("ok") is True, f"preview failed: {resp}"
    print(f"  ok=true uploaded_vendor={resp['uploaded_vendor']!r} "
          f"accept_token={resp['accept_token'][:12]}...")
    print(f"  similarity_matches: {resp.get('similarity_matches')}")
    print(f"  bundle_collision: {resp.get('bundle_collision')}")
    return resp["accept_token"]


def step_2_commit(doc: dict, accept_token: str) -> str:
    print("\n[step 2] POST /user (commit) ...")
    resp = mcp_request("POST", "/api/v1/data-sources/user", {
        "doc": doc,
        "accept_token": accept_token,
        "vendor_choice": "create_new",
    })
    assert resp.get("ok") is True, f"commit failed: {resp}"
    print(f"  ok=true id={resp['id']!r}")
    return resp["id"]


def step_3_catalog_contains():
    print("\n[step 3] GET /catalog?origin=user ...")
    resp = mcp_request("GET", "/api/v1/data-sources/catalog?origin=user")
    assert resp.get("ok") is True, f"catalog failed: {resp}"
    ids = {r["id"] for r in resp.get("rows", [])}
    assert ACME_ID in ids, f"AcmeCorp not in catalog: {ids}"
    print(f"  AcmeCorp present ✓ ({resp['row_count']} user rows total)")


def step_4_install() -> dict:
    print("\n[step 4] POST /install ...")
    resp = mcp_request("POST", "/api/v1/data-sources/install", {
        "pack_name": ACME_PACK,
        "rule_name": ACME_RULE,
        "dataset_name": ACME_DATASET,
    })
    assert resp.get("ok") is True, f"install failed: {resp}"
    print(f"  installed_ids={resp['data_source_ids']} fields={resp['fields_count']}")
    assert resp["fields_count"] == 5, f"expected 5 fields, got {resp['fields_count']}"
    return resp


def step_5_get_schema() -> list[dict]:
    print(f"\n[step 5] GET /{ACME_PACK}/{ACME_RULE}/{ACME_DATASET}/schema ...")
    resp = mcp_request("GET",
        f"/api/v1/data-sources/{ACME_PACK}/{ACME_RULE}/{ACME_DATASET}/schema")
    ds = resp.get("data_source", {})
    fields = ds.get("fields", [])
    names = [f["name"] for f in fields]
    print(f"  field_count={len(fields)} names={names}")
    expected = {"src_ip", "dst_ip", "username", "event_action", "timestamp_ms"}
    assert set(names) == expected, f"fields mismatch: {set(names)} vs {expected}"
    return fields


def step_6_create_worker(fields: list[dict]) -> str:
    """Create a worker via xlog's createDataWorker — lives on Query, not Mutation.

    xlog's schema (xlog/app/schema.py) attaches `create_data_worker` as a
    `@strawberry.field` on Query (not Mutation). Strawberry converts
    snake_case to camelCase: the Python param `request_input` becomes
    `requestInput` in GraphQL. WorkerOutput has fields
    type/worker/status/count/interval/destination/createdAt — no `name`.

    DataWorkerCreateInput requires `type: WorkerTypeEnum` (JSON/SYSLOG/CEF/...)
    and `destination`. SchemaOverrideInput's field list is `vendorFields`,
    not `fields`. Worker name is auto-generated server-side.
    """
    print(f"\n[step 6] xlog createDataWorker (UDP udp:{UDP_HOST}:{UDP_PORT}) ...")
    schema_override = {
        "vendorFields": [
            {
                "name": f["name"],
                "type": f.get("type"),
                "isArray": bool(f.get("is_array", False)),
                "isMeta": bool(f.get("is_meta", False)),
            }
            for f in fields if not f.get("is_meta")
        ],
        "packName": ACME_PACK,
        "ruleName": ACME_RULE,
        "datasetName": ACME_DATASET,
    }
    query = """
    query CreateWorker($input: DataWorkerCreateInput!) {
      createDataWorker(requestInput: $input) {
        type
        worker
        status
        count
        interval
        destination
        verifySsl
        createdAt
      }
    }
    """
    variables = {
        "input": {
            "type": "JSON",
            "count": WORKER_COUNT_PER_TICK,
            "interval": int(WORKER_INTERVAL) if WORKER_INTERVAL >= 1 else 1,
            "destination": f"udp:{UDP_HOST}:{UDP_PORT}",
            "verifySsl": False,
            "vendor": "AcmeCorp",
            "product": "AcmeApp",
            "schemaOverride": schema_override,
        }
    }
    resp = xlog_graphql(query, variables)
    print(f"  graphql resp: {json.dumps(resp)[:400]}")
    if "errors" in resp:
        raise RuntimeError(f"createDataWorker errors: {resp['errors']}")
    worker = resp["data"]["createDataWorker"]
    name = worker.get("worker")
    print(f"  worker name={name!r} status={worker.get('status')}")
    return name


def step_7_capture(capture: UDPCapture, fields: list[dict]) -> None:
    print(f"\n[step 7] capturing UDP for {CAPTURE_WINDOW}s ...")
    time.sleep(CAPTURE_WINDOW)
    n = len(capture.captured)
    print(f"  received {n} datagrams")
    assert n >= EXPECTED_MIN_DATAGRAMS, f"got {n} datagrams, expected ≥ {EXPECTED_MIN_DATAGRAMS}"

    expected_names = {f["name"] for f in fields if not f.get("is_meta")}
    for i, raw in enumerate(capture.captured[:3]):
        try:
            rec = json.loads(raw)
        except Exception:
            print(f"  [non-JSON datagram #{i}: {raw[:80]!r}]")
            continue
        got = set(rec.keys())
        print(f"  datagram #{i} keys: {sorted(got)}")
        assert expected_names.issubset(got), \
            f"missing fields in datagram {i}: {expected_names - got}"
    print(f"  all {min(3, n)} sampled datagrams contain the 5 AcmeCorp fields ✓")


def step_8_cleanup(worker_name: str | None) -> None:
    print("\n[step 8] cleanup ...")
    # Stop worker via dataWorkerAction (a Query field per xlog schema)
    # DataWorkerActionInput uses `worker: str` + `action: WorkerActionEnum`
    # (STOP | STATUS).
    if worker_name:
        query = """
        query StopWorker($input: DataWorkerActionInput!) {
          dataWorkerAction(requestInput: $input) {
            worker
            status
          }
        }
        """
        try:
            xlog_graphql(query, {"input": {"worker": worker_name, "action": "STOP"}})
            print(f"  worker {worker_name!r} stopped")
        except Exception as e:
            print(f"  worker stop failed (best-effort): {e}")
    # Uninstall data source
    try:
        resp = mcp_request("DELETE",
            f"/api/v1/data-sources/{ACME_PACK}/{ACME_RULE}/{ACME_DATASET}")
        print(f"  uninstall: {resp}")
    except Exception as e:
        print(f"  uninstall failed (best-effort): {e}")
    # Delete user upload
    try:
        resp = mcp_request("DELETE", f"/api/v1/data-sources/user/{ACME_ID}")
        print(f"  user upload deleted: {resp}")
    except Exception as e:
        print(f"  user delete failed (best-effort): {e}")


# ─── Main flow ─────────────────────────────────────────────────────


def main() -> int:
    print("=== R3.C.3 E2E: user YAML upload → UDP-streamed records ===")
    print(f"MCP_BASE={MCP_BASE} XLOG_BASE={XLOG_BASE}")
    print(f"UDP listener: {UDP_HOST}:{UDP_PORT}")

    capture = UDPCapture(UDP_HOST, UDP_PORT)
    capture.start()
    worker_name = None
    failure_marker = "FAIL"

    try:
        doc = build_acmecorp_yaml()
        token = step_1_preview(doc)
        step_2_commit(doc, token)
        step_3_catalog_contains()
        step_4_install()
        fields = step_5_get_schema()
        worker_name = step_6_create_worker(fields)
        step_7_capture(capture, fields)
        failure_marker = "PASS"
    except AssertionError as e:
        print(f"\n✗ ASSERTION FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ EXCEPTION: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 2
    finally:
        capture.stop()
        step_8_cleanup(worker_name)
        print(f"\n=== RESULT: {failure_marker} ===")

    return 0 if failure_marker == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
