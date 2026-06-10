#!/usr/bin/env python3
"""End-to-end agent test driven through the SAME chat-session API the UI uses
(`POST /api/chat`), authenticated with the operator's PHANTOM_API_KEY bearer.

Unlike e2e_all_vendors_via_agent_mcp.py (which calls MCP `tools/call` directly,
bypassing the model), this exercises the FULL agent loop: the model reads the
natural-language prompt, picks tools/skills from its catalog, runs them, and
composes an answer. That is what a UI chat user gets.

Run from the operator laptop through an IAP service tunnel to phantom-vm:3000.

  AGENT_BASE   default https://localhost:3001  (the live phantom-vm tunnel)
  PHANTOM_API_KEY  bearer (scope '*')           from .env.vm

Usage:
  python3 agent_chat_e2e.py --single "list installed data sources"
  python3 agent_chat_e2e.py --battery            # the full 5-aspect E2E run
"""
from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.request
from datetime import datetime, timezone

BASE = os.environ.get("AGENT_BASE", "https://localhost:3001").rstrip("/")
KEY = os.environ.get("PHANTOM_API_KEY")
if not KEY:
    print("FATAL: PHANTOM_API_KEY not set (source .env.vm)", file=sys.stderr)
    sys.exit(1)

# TLS verification off ON PURPOSE: this connects to localhost over a Google
# IAP tunnel (itself authenticated + encrypted) terminating at phantom-vm's
# self-signed dev cert. No MITM surface on the local tunnel. Matches every
# sibling e2e_*.py harness + the repo-wide `curl -sk` convention. Maintainer-
# only test script — never runs on a customer install.
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def chat(message: str, session_id: str | None = None, timeout: int = 300) -> dict:
    """Send one prompt, retrying on a urllib-only HTTP-400 quirk.

    NOTE: this 400 is a TEST-CLIENT artifact, not a Phantom bug. curl and the
    browser's fetch reuse the same chat session cleanly (verified 6/6 200);
    only urllib's chunked-SSE keep-alive handling intermittently emits a
    pre-stream 400 on alternating reuse calls. The immediate retry always
    succeeds. The product (UI) is unaffected — do NOT "fix" this server-side."""
    last = {}
    for _ in range(3):
        res = _chat_once(message, session_id=session_id, timeout=timeout)
        if res.get("http_status") != 400:
            return res
        last = res
        time.sleep(1.5)
    return last


def _chat_once(message: str, session_id: str | None = None, timeout: int = 300) -> dict:
    """POST one prompt to /api/chat, stream the SSE response, return a structured
    summary of everything that happened in the turn."""
    body = {"message": message}
    if session_id:
        body["session_id"] = session_id
    req = urllib.request.Request(
        f"{BASE}/api/chat",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    out = {
        "session_id": session_id,
        "text": "",
        "thinking_chars": 0,
        "tool_calls": [],      # [{name, args}]
        "tool_results": [],    # [{name, status}]
        "approvals": [],       # [{tool}]
        "errors": [],
        "events": {},          # event-type -> count
        "done_reason": None,
        "http_status": None,
    }
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            out["http_status"] = r.status
            cur_event = None
            for raw in r:
                line = raw.decode("utf-8", "replace").rstrip("\n")
                if line.startswith("event:"):
                    cur_event = line[6:].strip()
                    out["events"][cur_event] = out["events"].get(cur_event, 0) + 1
                elif line.startswith("data:"):
                    payload = line[5:].strip()
                    try:
                        data = json.loads(payload)
                    except json.JSONDecodeError:
                        data = {"_raw": payload}
                    _absorb(out, cur_event, data)
                # blank line = frame boundary; nothing to do
    except urllib.error.HTTPError as e:
        out["http_status"] = e.code
        out["errors"].append(f"HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}")
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"{type(e).__name__}: {e}")
    return out


def _absorb(out: dict, event: str | None, data: dict) -> None:
    # session_id rides on the `meta` event (and most `done` variants); grab it
    # from whichever event carries it so session continuity holds across turns.
    if isinstance(data, dict) and isinstance(data.get("session_id"), str):
        out["session_id"] = data["session_id"]
    if event == "text_delta":
        out["text"] += data.get("text", "") if isinstance(data, dict) else ""
    elif event == "thinking":
        out["thinking_chars"] += len(data.get("text", "")) if isinstance(data, dict) else 0
    elif event == "tool_call":
        name = data.get("tool") or data.get("name") or "?"
        out["tool_calls"].append({"name": name, "args": data.get("args", {})})
    elif event == "tool_result":
        out["tool_results"].append(
            {"name": data.get("name") or data.get("tool") or "?",
             "status": data.get("status", "?")}
        )
    elif event == "approval_pending":
        out["approvals"].append({"tool": data.get("tool", "?")})
    elif event == "error":
        out["errors"].append(str(data.get("error", data)))
    elif event == "done":
        out["session_id"] = data.get("session_id", out["session_id"])
        out["done_reason"] = data.get("status_reason")


def _print_turn(label: str, prompt: str, res: dict) -> None:
    tools = ", ".join(sorted({t["name"] for t in res["tool_calls"]})) or "(none)"
    errs = "; ".join(res["errors"])[:300]
    print(f"\n{'='*78}\n### {label}\nPROMPT: {prompt}")
    print(f"  http={res['http_status']} done={res['done_reason']} "
          f"events={res['events']}")
    print(f"  tools_called: {tools}")
    if res["tool_results"]:
        rs = ", ".join(f"{r['name']}:{r['status']}" for r in res["tool_results"])
        print(f"  tool_results: {rs}")
    if res["approvals"]:
        print(f"  ⚠ APPROVAL_PENDING for: {[a['tool'] for a in res['approvals']]}")
    if errs:
        print(f"  ⚠ errors: {errs}")
    txt = res["text"].strip().replace("\n", " ")
    print(f"  answer ({len(res['text'])} chars): {txt[:600]}")


BATTERY = [
    # NOTE: no /approval-bypass turn needed — approval is self-mod-only
    # (manifest humanRequired). Data generation, XQL, and skills tools are
    # NOT gated, so headless turns never stall on an approval card.
    # T1 — TOOLS + DATA SOURCES
    {"label": "T1 — tools + data sources",
     "prompt": "List the data sources currently installed in Phantom, then show "
               "me the field schema (field names + a few example values) for the "
               "Okta SSO data source (dataset okta_sso_raw).",
     "wait_after": 0, "aspect": "tools+data_sources"},
    # T2 — SKILLS
    {"label": "T2 — skills",
     "prompt": "What skills do you have available for simulating security "
               "telemetry into Cortex XSIAM? Name the single most relevant skill "
               "and summarize the steps it tells you to follow.",
     "wait_after": 0, "aspect": "skills"},
    # T3 — CREATE DATA
    {"label": "T3 — create + send data",
     "prompt": "Using the Okta SSO data source, generate and send 5 realistic "
               "Okta SSO sign-in log events to Cortex XSIAM right now (CEF over "
               "the broker). Confirm the worker was created and tell me the "
               "vendor/product and dataset they will land in.",
     "wait_after": 120, "aspect": "create_data"},
    # T4 — XQL VERIFY (landing + XDM mapping)
    {"label": "T4 — XQL verify landing + XDM",
     "prompt": "Run an XQL query against the okta_sso_raw dataset to confirm the "
               "events I just sent landed in the last 15 minutes (show the count). "
               "Then run a datamodel query on the same dataset and tell me which "
               "XDM fields are populated.",
     "wait_after": 0, "aspect": "xql_verify"},
]


def run_battery() -> None:
    started = datetime.now(timezone.utc).isoformat()
    print(f"Agent /api/chat E2E battery — base={BASE} — {started}")
    sid = None
    transcript = []
    for step in BATTERY:
        res = chat(step["prompt"], session_id=sid, timeout=300)
        sid = res["session_id"] or sid
        _print_turn(step["label"], step["prompt"], res)
        transcript.append({"step": step["label"], "aspect": step["aspect"],
                           "prompt": step["prompt"], "result": res})
        if step["wait_after"]:
            print(f"\n  …sleeping {step['wait_after']}s for XSIAM ingest…")
            time.sleep(step["wait_after"])
    out_path = "/tmp/agent_chat_e2e_transcript.json"
    with open(out_path, "w") as f:
        json.dump({"started": started, "base": BASE, "session_id": sid,
                   "transcript": transcript}, f, indent=2)
    print(f"\n{'='*78}\nFull transcript → {out_path}\nsession_id = {sid}")


# Second smoke round — DIFFERENT data sources than the Okta SSO battery.
# Explicit CEF routing literals (from the validated table in
# skills/workflows/stream_simulate_to_xsiam.md) so this tests the
# pipeline + connector tools + XDM mapping ACROSS vendors via the chat path,
# not the agent's routing-guessing (that gap is a separate skill-adherence fix).
# Spread: 3 single-dataset (clean landing) + Qualys classifier + O365 split.
VENDORS2 = [
    {"label": "ServiceNow", "dataset": "servicenow_servicenow_raw",
     "vendor": "ServiceNow", "product": "ServiceNow", "obs": None},
    {"label": "Jira", "dataset": "atlassian_jira_raw",
     "vendor": "Atlassian", "product": "Jira", "obs": None},
    {"label": "AWS WAF", "dataset": "aws_waf_raw",
     "vendor": "aws", "product": "waf", "obs": None},
    {"label": "Qualys", "dataset": "qualys_qualys_raw",
     "vendor": "Qualys", "product": "Qualys", "obs": {"event_type": ["activity_log"]}},
    {"label": "O365 Exchange", "dataset": "msft_o365_exchange_online_raw",
     "vendor": "msft", "product": "o365_exchange_online", "obs": {"Workload": ["Exchange"]}},
]


def _fire_prompt(v: dict) -> str:
    obs = f", observables_dict={json.dumps(v['obs'])}" if v["obs"] else ""
    return (
        "Do NOT ask me to confirm. First call data_sources_get_schema for dataset "
        f"{v['dataset']}, then IMMEDIATELY call phantom_create_data_worker with: "
        f"type='CEF', destination='udp:10.10.0.8:514', vendor='{v['vendor']}', "
        f"product='{v['product']}', count=8, interval=2, the full {v['dataset']} "
        f"fields as schema_override{obs}. Fire it now and report only the worker id."
    )


def _verify_prompt(v: dict) -> str:
    return (
        "Verify only, no new worker. Using xsiam_run_xql_query over the last 15 minutes, "
        f"one line each: (1) 'dataset = {v['dataset']} | comp count() as n' — the count; "
        f"(2) 'datamodel dataset = {v['dataset']} | fields xdm.* | limit 1' — how many "
        "xdm.* fields are non-null."
    )


def run_multi() -> None:
    """Second smoke round across different data sources: fire all → wait → verify all."""
    started = datetime.now(timezone.utc).isoformat()
    print(f"Multi-vendor smoke (DIFFERENT data sources) — base={BASE} — {started}")
    transcript = []
    print("\n=== Phase 1 — fire workers (one chat turn per vendor) ===")
    for v in VENDORS2:
        res = chat(_fire_prompt(v), timeout=300)
        v["_sid"] = res["session_id"]
        m = re.search(r"worker_\d+", res["text"])
        fired = any(t["name"] == "phantom_create_data_worker" for t in res["tool_calls"])
        tools = sorted({t["name"] for t in res["tool_calls"]})
        print(f"  {'OK ' if fired else 'XX '} {v['label']:14s} fired={fired} "
              f"wid={m.group(0) if m else '?'} tools={tools} errs={res['errors'][:1]}")
        transcript.append({"phase": "fire", "vendor": v["label"], "result": res})
    print("\n=== Phase 2 — wait 120s for XSIAM ingest ===")
    time.sleep(120)
    print("\n=== Phase 3 — verify landing + XDM (per vendor) ===")
    for v in VENDORS2:
        res = chat(_verify_prompt(v), session_id=v.get("_sid"), timeout=300)
        txt = res["text"].strip().replace("\n", " ")
        print(f"  {v['label']:14s} -> {txt[:260]}")
        transcript.append({"phase": "verify", "vendor": v["label"], "result": res})
    # Phase 4 — cleanup. The skill's Step 8 says ALWAYS kill workers after a
    # run; without this the workers loop and flood the broker.
    print("\n=== Phase 4 — cleanup (kill all workers) ===")
    res = chat(
        "Do not ask me to confirm. Call phantom_list_workers, then phantom_kill_worker "
        "on EVERY running worker. Report how many you killed and the remaining count.",
        timeout=300,
    )
    print(f"  {res['text'].strip()[:220]}")
    transcript.append({"phase": "cleanup", "result": res})
    out_path = "/tmp/agent_chat_multi_smoke.json"
    with open(out_path, "w") as f:
        json.dump({"started": started, "transcript": transcript}, f, indent=2)
    print(f"\n{'='*78}\nMulti-vendor transcript → {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--single", help="run one prompt and print the result")
    ap.add_argument("--battery", action="store_true", help="run the full E2E battery")
    ap.add_argument("--multi", action="store_true", help="second smoke round — different data sources")
    ap.add_argument("--session", help="reuse an existing session id (with --single)")
    args = ap.parse_args()
    if args.single:
        r = chat(args.single, session_id=args.session, timeout=300)
        _print_turn("single", args.single, r)
        print(f"\nsession_id = {r['session_id']}")
    elif args.battery:
        run_battery()
    elif args.multi:
        run_multi()
    else:
        ap.print_help()
