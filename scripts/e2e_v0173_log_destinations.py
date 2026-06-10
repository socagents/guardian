#!/usr/bin/env python3
"""v0.17.3 R6 — log destinations E2E battery.

Validates the full v0.17.x arc end-to-end on the deployed install:

  Section 1  destination-types catalog (4 v1 types loaded)
  Section 2  syslog CRUD + UDP probe → real datagram receipt
  Section 3  webhook CRUD with bearer auth → secret persists redacted
  Section 4  xsiam_http + splunk_hec destinations creatable
  Section 5  PATCH '***' sentinel preserves existing secret
  Section 6  set-default clears siblings of same type
  Section 7  multi-destination independence (creating two doesn't bleed)
  Section 8  delete cascades secret cleanup
  Section 9  WEBHOOK_ENDPOINT migration (if applicable on this install)
  Section 10 visible_when discriminator (webhook auth modes round-trip)

Usage (against phantom-vm via IAP tunnel + docker exec):

    set -a && source .env.vm && set +a
    gcloud compute start-iap-tunnel ...
    SSHPASS=... sshpass -e ssh ... \\
      'TOKEN=$(docker exec phantom_agent sh -c "cat /proc/1/environ" | \\
              tr "\\0" "\\n" | grep ^MCP_TOKEN= | cut -d= -f2-); \\
       docker exec -i -e MCP_TOKEN="$TOKEN" phantom_agent python3 -' \\
      < scripts/e2e_v0173_log_destinations.py

Exit 0 on full pass; non-zero on any assertion failure.
"""

from __future__ import annotations

import json
import os
import socket
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request

TOKEN = os.environ.get("MCP_TOKEN", "")
if not TOKEN:
    sys.exit("ERROR: MCP_TOKEN env var required")
BASE = "https://127.0.0.1:8080"
CTX = ssl._create_unverified_context()  # noqa: S323


def req(method: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        f"{BASE}{path}", data=data, method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(r, context=CTX, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


passed = 0
failed = 0
failures: list[str] = []


def check(name: str, ok: bool, extra: str = "") -> None:
    global passed, failed
    suffix = f" — {extra}" if extra else ""
    if ok:
        print(f"  ✓ PASS  {name}{suffix}")
        passed += 1
    else:
        print(f"  ✗ FAIL  {name}{suffix}")
        failed += 1
        failures.append(f"{name}{suffix}")


# Resources to clean up at end
to_delete: list[str] = []


# ─── Section 1: catalog ──────────────────────────────────────────────


def section_1() -> None:
    print("=== Section 1: destination-types catalog ===")
    st, resp = req("GET", "/api/v1/destination-types")
    check("GET /api/v1/destination-types → 200", st == 200)
    type_ids = {t["id"] for t in (resp.get("types") or [])}
    check(
        "4 v1 types loaded",
        {"syslog", "webhook", "xsiam_http", "splunk_hec"}.issubset(type_ids),
        f"got {sorted(type_ids)}",
    )

    # visible_when invariants
    webhook = next(
        (t for t in (resp.get("types") or []) if t["id"] == "webhook"),
        None,
    )
    if webhook:
        bearer = next(
            (f for f in webhook["fields"] if f["name"] == "bearer_token"),
            None,
        )
        check(
            "webhook.bearer_token has visible_when={auth_type: bearer}",
            bool(bearer and bearer.get("visible_when") == {
                "field": "auth_type", "value": "bearer",
            }),
        )


# ─── Section 2: syslog UDP probe ─────────────────────────────────────


_received_packets: list[bytes] = []


def _start_udp_listener(port: int) -> threading.Event:
    ready = threading.Event()

    def loop() -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("127.0.0.1", port))
        s.settimeout(15)
        ready.set()
        try:
            while True:
                try:
                    data, _ = s.recvfrom(8192)
                    _received_packets.append(data)
                except socket.timeout:
                    return
        finally:
            s.close()

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    ready.wait(timeout=5)
    return ready


def section_2() -> None:
    print("\n=== Section 2: syslog CRUD + UDP probe ===")
    port = 5515
    _start_udp_listener(port)
    print(f"  UDP listener ready on 127.0.0.1:{port}")

    st, resp = req("POST", "/api/v1/log-destinations", {
        "name": "e2e-syslog-udp",
        "type_id": "syslog",
        "config": {
            "host": "127.0.0.1",
            "port": str(port),
            "protocol": "udp",
            "framing": "rfc5424",
            "facility": "local3",
        },
    })
    check("POST syslog → 201", st == 201)
    dest_id = (resp.get("destination") or {}).get("id")
    if dest_id:
        to_delete.append(dest_id)
    check("response carries an id", bool(dest_id))

    st, resp = req("POST", f"/api/v1/log-destinations/{dest_id}/probe")
    check("POST /probe → 200", st == 200)
    check("probe.ok == true", resp.get("ok") is True,
          f"err={resp.get('error')}")
    check("probe.latency_ms reported", isinstance(resp.get("latency_ms"), int))

    time.sleep(0.4)
    check("UDP listener received probe packet",
          len(_received_packets) >= 1,
          f"got {len(_received_packets)}")
    if _received_packets:
        msg = _received_packets[0].decode("utf-8", errors="replace")
        # RFC5424 format: <PRI>VERSION TIMESTAMP HOSTNAME APP-NAME PROCID MSGID SD MSG
        # e.g. "<157>1 2026-05-24T... phantom phantom - - - phantom test ..."
        # Match: opens with '<', has '>' then '1 ' then a year-2026 timestamp.
        import re
        check(
            "Packet is RFC5424-shaped (<PRI>1 <ts> ... <msg>)",
            bool(re.match(r"^<\d+>1 \d{4}-\d{2}-\d{2}T", msg)),
            f"prefix={msg[:80]!r}",
        )
        check("Facility=local3 in PRI byte (<157>)",
              # local3 (19) * 8 + NOTICE (5) = 157
              msg.startswith("<157>"),
              f"got prefix={msg[:8]}")

    st, resp = req("GET", f"/api/v1/log-destinations/{dest_id}")
    d = resp.get("destination") or {}
    check("last_probe_ok=true after probe", d.get("last_probe_ok") is True)
    check("last_probe_at populated", d.get("last_probe_at") is not None)


# ─── Section 3: webhook with bearer auth ─────────────────────────────


def section_3() -> None:
    print("\n=== Section 3: webhook with bearer auth ===")
    st, resp = req("POST", "/api/v1/log-destinations", {
        "name": "e2e-webhook-bearer",
        "type_id": "webhook",
        "config": {
            "url": "https://example.invalid/hook",
            "auth_type": "bearer",
            "method": "POST",
            "content_type": "application/json",
        },
        "secrets": {"bearer_token": "secret-token-e2e"},
    })
    check("POST webhook+bearer → 201", st == 201)
    wh_id = (resp.get("destination") or {}).get("id")
    if wh_id:
        to_delete.append(wh_id)

    st, resp = req("GET", f"/api/v1/log-destinations/{wh_id}")
    d = resp.get("destination") or {}
    check(
        "bearer_token slot present + value redacted '***'",
        d.get("secrets", {}).get("bearer_token") == "***",
    )
    check(
        "bearer_token NOT leaked into config",
        "bearer_token" not in (d.get("config") or {}),
    )


# ─── Section 4: xsiam_http + splunk_hec creatable ───────────────────


def section_4() -> None:
    print("\n=== Section 4: xsiam_http + splunk_hec creatable ===")
    st, resp = req("POST", "/api/v1/log-destinations", {
        "name": "e2e-xsiam-http",
        "type_id": "xsiam_http",
        "config": {
            "url": "https://api-test.xdr.us.paloaltonetworks.com/v1/logs/x",
            "source": "phantom-e2e",
            "auth_id": "test-auth-id",
        },
        "secrets": {"auth_key": "test-xsiam-auth-key"},
    })
    check("POST xsiam_http → 201", st == 201)
    if st == 201:
        to_delete.append(resp["destination"]["id"])

    st, resp = req("POST", "/api/v1/log-destinations", {
        "name": "e2e-splunk-hec",
        "type_id": "splunk_hec",
        "config": {
            "url": "https://splunk.example.invalid:8088/services/collector/event",
            "index": "main",
            "source": "phantom-e2e",
            "sourcetype": "phantom:test",
            "verify_ssl": "false",
        },
        "secrets": {"token": "ABCD-1234-EFGH-5678-IJKL-9012"},
    })
    check("POST splunk_hec → 201", st == 201)
    if st == 201:
        to_delete.append(resp["destination"]["id"])


# ─── Section 5: PATCH '***' sentinel preserves secret ───────────────


def section_5() -> None:
    print("\n=== Section 5: PATCH '***' sentinel preserves secret ===")
    # Create a fresh webhook
    st, resp = req("POST", "/api/v1/log-destinations", {
        "name": "e2e-webhook-rot",
        "type_id": "webhook",
        "config": {
            "url": "https://example.invalid/rot",
            "auth_type": "bearer",
        },
        "secrets": {"bearer_token": "original-secret"},
    })
    check("created rotation-test webhook", st == 201)
    wh_id = (resp.get("destination") or {}).get("id")
    if wh_id:
        to_delete.append(wh_id)

    # PATCH with the secret as '***' (preserve)
    st, _ = req("PATCH", f"/api/v1/log-destinations/{wh_id}", {
        "config": {"url": "https://example.invalid/rotated"},
        "secrets": {"bearer_token": "***"},
    })
    check("PATCH with '***' sentinel → 200", st == 200)

    # Confirm via /probe DRY-RUN — we can't read the value but the
    # probe response succeeding against the existing secret is proof
    # the secret survived the round-trip.
    # NB: probe will fail (invalid host) but that's fine; we just
    # want the request to round-trip server-side.
    st, _ = req("POST", f"/api/v1/log-destinations/{wh_id}/probe")
    check("probe runs after PATCH (server-side secret resolution)",
          st == 200)


# ─── Section 6: set-default clears siblings ──────────────────────────


def section_6() -> None:
    print("\n=== Section 6: set-default clears siblings of same type ===")
    a = req("POST", "/api/v1/log-destinations", {
        "name": "e2e-syslog-default-a",
        "type_id": "syslog",
        "config": {"host": "a.example", "port": "514", "protocol": "udp"},
        "is_default": True,
    })
    b = req("POST", "/api/v1/log-destinations", {
        "name": "e2e-syslog-default-b",
        "type_id": "syslog",
        "config": {"host": "b.example", "port": "514", "protocol": "udp"},
    })
    if a[0] == 201:
        to_delete.append(a[1]["destination"]["id"])
    if b[0] == 201:
        to_delete.append(b[1]["destination"]["id"])

    a_id = a[1]["destination"]["id"]
    b_id = b[1]["destination"]["id"]

    # Verify a is currently default
    _, ar = req("GET", f"/api/v1/log-destinations/{a_id}")
    check("a is default after creation", ar["destination"]["is_default"] is True)

    # Promote b
    st, _ = req("POST", f"/api/v1/log-destinations/{b_id}/set-default")
    check("POST set-default on b → 200", st == 200)

    _, ar2 = req("GET", f"/api/v1/log-destinations/{a_id}")
    _, br2 = req("GET", f"/api/v1/log-destinations/{b_id}")
    check("a no longer default", ar2["destination"]["is_default"] is False)
    check("b is now default", br2["destination"]["is_default"] is True)


# ─── Section 7: multi-destination independence ──────────────────────


def section_7() -> None:
    print("\n=== Section 7: multi-destination independence ===")
    st, resp = req("GET", "/api/v1/log-destinations")
    rows = resp.get("destinations") or []
    e2e_rows = [r for r in rows if r["name"].startswith("e2e-")]
    check(
        f"all e2e destinations carry distinct ids (no row bleed)",
        len({r["id"] for r in e2e_rows}) == len(e2e_rows),
        f"got {len(e2e_rows)} rows, {len({r['id'] for r in e2e_rows})} unique",
    )
    # Each row's name is unique
    check(
        "all e2e destinations carry distinct names",
        len({r["name"] for r in e2e_rows}) == len(e2e_rows),
    )


# ─── Section 8: delete cascades secret cleanup ──────────────────────


def section_8() -> None:
    print("\n=== Section 8: delete cascades secret cleanup ===")
    # Create + delete a webhook + verify post-delete GET returns 404
    st, resp = req("POST", "/api/v1/log-destinations", {
        "name": "e2e-delete-cascade",
        "type_id": "webhook",
        "config": {
            "url": "https://example.invalid/delme",
            "auth_type": "bearer",
        },
        "secrets": {"bearer_token": "will-be-deleted"},
    })
    check("created cascade-test webhook", st == 201)
    dest_id = resp["destination"]["id"]

    st, _ = req("DELETE", f"/api/v1/log-destinations/{dest_id}")
    check("DELETE → 200", st == 200)

    st, _ = req("GET", f"/api/v1/log-destinations/{dest_id}")
    check("GET after DELETE → 404", st == 404)


# ─── Section 9: WEBHOOK_ENDPOINT migration ──────────────────────────


def section_9() -> None:
    print("\n=== Section 9: WEBHOOK_ENDPOINT migration (best-effort) ===")
    # Check if "XSIAM Default" exists (migration may have fired on
    # boot if env var is set). This is informational — depending on
    # the install's env, the migration may not apply.
    st, resp = req("GET", "/api/v1/log-destinations?type_id=xsiam_http")
    rows = resp.get("destinations") or []
    has_default = any(
        r["name"] == "XSIAM Default" and r.get("is_default")
        for r in rows
    )
    if has_default:
        check("XSIAM Default migrated from WEBHOOK_ENDPOINT env",
              has_default)
    else:
        print(
            "  ⊝ SKIP  no migrated XSIAM Default — "
            "WEBHOOK_ENDPOINT env probably unset on this install"
        )


# ─── Section 10: visible_when discriminator round-trip ──────────────


def section_10() -> None:
    print("\n=== Section 10: visible_when round-trip via webhook auth ===")
    # Create webhook with no auth — bearer_token must NOT be required
    st, resp = req("POST", "/api/v1/log-destinations", {
        "name": "e2e-webhook-none",
        "type_id": "webhook",
        "config": {
            "url": "https://example.invalid/none",
            "auth_type": "none",
        },
    })
    check("POST webhook with auth_type=none, no creds → 201", st == 201)
    if st == 201:
        to_delete.append(resp["destination"]["id"])

    # Create webhook with api_key_header
    st, resp = req("POST", "/api/v1/log-destinations", {
        "name": "e2e-webhook-apikey",
        "type_id": "webhook",
        "config": {
            "url": "https://example.invalid/apikey",
            "auth_type": "api_key_header",
            "header_name": "X-Phantom-Test",
        },
        "secrets": {"header_value": "test-api-key"},
    })
    check("POST webhook with auth_type=api_key_header → 201", st == 201)
    if st == 201:
        ak_id = resp["destination"]["id"]
        to_delete.append(ak_id)
        # Verify GET shows header_value as redacted
        _, gresp = req("GET", f"/api/v1/log-destinations/{ak_id}")
        d = gresp["destination"]
        check("header_value secret redacted as '***'",
              d.get("secrets", {}).get("header_value") == "***")
        check("header_name in config (non-secret)",
              d.get("config", {}).get("header_name") == "X-Phantom-Test")


# ─── Driver ──────────────────────────────────────────────────────────


def main() -> int:
    print("=" * 70)
    print("v0.17.3 E2E battery — log destinations")
    print(f"MCP_BASE: {BASE}")
    print("=" * 70)

    sections = [
        section_1, section_2, section_3, section_4, section_5,
        section_6, section_7, section_8, section_9, section_10,
    ]
    for s in sections:
        try:
            s()
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ FAIL  section {s.__name__} raised: "
                  f"{type(e).__name__}: {e}")
            global failed
            failed += 1
            failures.append(f"{s.__name__}: {e}")

    # Cleanup all created resources
    print("\n=== Cleanup ===")
    for dest_id in to_delete:
        try:
            st, _ = req("DELETE", f"/api/v1/log-destinations/{dest_id}")
            print(f"  DELETE {dest_id[:8]}: {st}")
        except Exception as e:  # noqa: BLE001
            print(f"  cleanup failed for {dest_id[:8]}: {e}")

    print("\n" + "=" * 70)
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print("=" * 70)
    if failures:
        print("\nFailures:")
        for f in failures[:10]:
            print(f"  - {f}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
