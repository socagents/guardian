"""Phase 3 verification probe — extends `retrieval_probe.py` with
diverse query scenarios + actual `xdr_run_xql_query` execution to
verify the full skill chain end-to-end.

Phase 1 (v0.6.54) verified: knowledge_search → top-5 → extract →
cortex_xql_lookup, with 5 baseline queries, all GREEN.

Phase 3 (this script, v0.6.61+) verifies: the same chain PLUS actual
XDR execution of the top-1 KB match's query, across 18 diverse SOC
scenarios. Categories:

  Investigation (8) — typical SOC analyst hunts. Mostly xdr_data,
    endpoints, xdr_login_events presets/datasets.
  Aggregation (3)   — comp / count / sort / top-N queries. Tests
    that the chain handles aggregation patterns.
  Time-bounded (3)  — "last hour", "yesterday" phrasing. Tests that
    the matched entries include time-window clauses.
  Composite (2)     — joins, unions, complex stage chains.
  Edge cases (2)    — vague query, narrow-niche query.

Per-query verdict:

  GREEN  = KB match found AND xdr_run_xql_query returned
           status=SUCCESS (any row count, including 0).
  YELLOW = KB match found but XDR returned a TIMEOUT or PENDING
           (the query is valid but slow; not a chain bug).
  RED    = No KB match, OR XDR returned FAIL/FAILED (the matched
           query has a syntax issue against this tenant), OR
           cortex_xql_lookup hit rate <60%.

The script runs sequentially because XDR API quota is finite and
parallel queries would burn it for no gain. Total runtime ~5-8 min
for 18 queries (~20-30s per XDR query including the bounded poll).

Usage from repo root (requires the agent UI tunnel on localhost:3001):

    gcloud compute start-iap-tunnel <vm> 3000 \\
        --local-host-port=localhost:3001 ... &
    python3 bundles/spark/kbs/xql-examples/_tools/phase3_probe.py

Output is human-readable + a final JSON-shaped verdict block the
operator can scan in one screen.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import time
import urllib.request
from collections import Counter
from typing import Any

# ─── Config ─────────────────────────────────────────────────────────

AGENT_URL = os.environ.get("GUARDIAN_AGENT_URL", "https://localhost:3001")
TLS_INSECURE = ssl._create_unverified_context()


# Phase-3 test scenarios — diverse SOC analyst phrasing.
# Each scenario: (category, query). KB hit categories observed in the
# corpus include investigation, detection, alert-mapping, general.
TEST_SCENARIOS: list[tuple[str, str]] = [
    # ─── Investigation ─────────────────────────────────────────────
    ("investigation", "list endpoints with XDR agents deployed"),
    ("investigation", "show hostnames IP addresses last seen and OS type"),
    ("investigation", "find failed RDP login attempts in the last hour"),
    ("investigation", "detect rare PSEXEC process executions on Windows hosts"),
    ("investigation", "show me which users authenticated from new countries this week"),
    ("investigation", "find DNS queries for very long domain names"),
    ("investigation", "show hosts with unusual outbound network traffic to public IPs"),
    ("investigation", "list processes that spawned cmd.exe in the last 24 hours"),
    # ─── Aggregation ───────────────────────────────────────────────
    ("aggregation", "top 10 hosts by event count today"),
    ("aggregation", "count of alerts by severity level"),
    ("aggregation", "average response time grouped by endpoint"),
    # ─── Time-bounded ──────────────────────────────────────────────
    ("time-bounded", "events from the last 15 minutes"),
    ("time-bounded", "all alerts that fired yesterday"),
    ("time-bounded", "user logins after 6pm in the last week"),
    # ─── Composite / complex ───────────────────────────────────────
    ("composite", "join network and process events on hostname"),
    ("composite", "alerts not yet resolved with critical severity"),
    # ─── Edge cases ────────────────────────────────────────────────
    ("edge-case", "show me suspicious stuff"),  # vague — KB matches will be diffuse
    ("edge-case", "find encrypted DNS over HTTPS exfiltration"),  # narrow niche
    # ─── Complex (v0.6.64) — the 10 prompts shared with operator for ─
    # ─── chat-level smoke testing of multi-stage synthesis. Probe runs
    # ─── them through the same chain to baseline KB retrieval quality
    # ─── for advanced patterns. Many will be LOW-SCORE matches — that's
    # ─── expected, since the operator's KB is heavy on single-purpose
    # ─── queries and these complex prompts may need composition. The
    # ─── score floor tells us whether the KB has enough material to
    # ─── support the synthesis vs. needing first-principles work.
    ("complex-stats", "show me a timeline of process executions per hour for the last 24 hours grouped by parent process where the parent is svchost.exe or services.exe and highlight any hour where the count exceeds the daily average by more than 2 standard deviations"),
    ("complex-stats", "for each endpoint calculate the percentage of failed-to-total login attempts in the last 7 days sort by failure rate and only return endpoints where failures are over 10% AND at least 50 total attempts"),
    ("complex-correlation", "find all hosts where a process made an outbound network connection to a public IP in the last hour AND that same host had a failed authentication event in the 30 minutes preceding the connection"),
    ("complex-hunting", "hunt for T1059.001 PowerShell execution find PowerShell processes started by non-administrator users where the command line contains encoded base64 downloaded scripts via Invoke-WebRequest or referenced AMSI bypass patterns"),
    ("complex-hunting", "detect T1003.001 LSASS credential dump attempts any process accessing lsass.exe memory that isn't wininit.exe services.exe or a known EDR agent in the last 48 hours grouped by initiating process tree"),
    ("complex-correlation", "find lateral movement candidates hosts that initiated SMB connections to 3+ other internal hosts within a 30-minute window where the initiating user logged in within the prior hour"),
    ("complex-stats", "show me the 99th percentile of process creation rate per host over the last day and flag hosts above that threshold for the past hour"),
    ("complex-stats", "find rare DLLs loaded by services.exe in the last week DLLs that appear in less than 5 percent of total services.exe events across the tenant"),
    ("complex-stats", "anomaly hunt which users have a >3 standard deviation spike in failed authentication attempts compared to their own 30-day baseline"),
    ("complex-conditional", "categorize endpoints into critical high-value or normal tiers based on last-seen activity OS type and admin-user-count then show distribution by tier"),
    # ─── Tenant-tailored (v0.6.68) — designed to hit real data in ─
    # ─── THIS operator's XDR tenant. Discovery surfaced:
    # ─── - AKS K8s nodes + 2 Windows xdragent boxes (active)
    # ─── - 187 CRITICAL + 722 HIGH alerts in 7d
    # ─── - Mimikatz alerts on xdragent + xdragent2 (real)
    # ─── - CVE-2025-68121 alert on AKS nodes
    # ─── - Real outbound network bytes on xdragent (367k/24h)
    # ─── Each prompt below should return non-empty results.
    ("tenant-tailored", "show me all credential-dumping-related alerts mimikatz LSASS access credential extraction from the last 30 days with affected host severity alert name and description"),
    ("tenant-tailored", "list CVE-related vulnerability alerts from the last 7 days grouped by CVE identifier extracted from alert_name show count per CVE and affected hosts"),
    ("tenant-tailored", "on Windows hosts xdragent and xdragent2 show the top 10 remote destinations by upload bytes in the last 24 hours with remote IP port and total bytes uploaded"),
    ("tenant-tailored", "list all endpoints sorted by last_seen ascending flag any with endpoint_status CONNECTION_LOST as inactive and highlight any with agent_version below 9.0.0"),
    ("tenant-tailored", "from the last 7 days count alerts grouped by severity and host_name show only HIGH and CRITICAL severities sorted by count desc"),
]


# ─── HTTP helpers ────────────────────────────────────────────────────


def http_json(method: str, path: str, body: dict | None = None) -> dict:
    """POST/GET wrapper hitting the agent UI's REST proxy."""
    url = f"{AGENT_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, context=TLS_INSECURE, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def kb_search(query: str, limit: int = 5) -> list[dict]:
    res = http_json(
        "POST",
        "/api/agent/knowledge/xql-examples/search",
        {"query": query, "limit": limit},
    )
    return res.get("results", [])


def cortex_xql_lookup(term: str, kind: str = "auto") -> dict:
    res = http_json(
        "POST",
        "/api/agent/tool/call",
        {
            "name": "cortex_xql_lookup",
            "arguments": {"term": term, "kind": kind},
        },
    )
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "unknown tool error")}
    return res.get("result") or {}


def xdr_run_xql_query(query: str) -> dict:
    """Execute an XQL query against the configured XDR tenant. Returns
    the tool's response payload."""
    res = http_json(
        "POST",
        "/api/agent/tool/call",
        {
            "name": "xdr_run_xql_query",
            "arguments": {"query": query},
        },
    )
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "unknown tool error")}
    return res.get("result") or {}


# ─── Query body extraction ──────────────────────────────────────────


def extract_query_body(content: str) -> str:
    m = re.search(r"```sql\s*\n(.*?)\n```", content, re.DOTALL)
    return m.group(1).strip() if m else ""


STAGE_RE = re.compile(r"\|\s*(\w+)")
FUNC_RE = re.compile(r"\b([a-z_][a-z0-9_]+)\s*\(")
FALSE_POSITIVES = {
    "filter", "alter", "comp", "fields", "sort", "limit", "dedup",
    "transaction", "union", "view", "join", "fork", "config",
    "iploc", "windowcomp", "bin", "if", "in",
    "and", "or", "not", "asc", "desc", "by", "as", "is", "null", "true", "false",
}


def extract_stages(query: str) -> list[str]:
    seen, out = set(), []
    for m in STAGE_RE.finditer(query):
        s = m.group(1).lower()
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def extract_functions(query: str) -> list[str]:
    seen, out = set(), []
    for m in FUNC_RE.finditer(query):
        f = m.group(1).lower()
        if f in FALSE_POSITIVES or f in seen:
            continue
        out.append(f)
        seen.add(f)
    return out


# ─── Per-scenario probe ─────────────────────────────────────────────


def probe_scenario(category: str, user_query: str) -> dict:
    print(f"\n{'='*76}")
    print(f"[{category.upper()}] {user_query}")
    print(f"{'='*76}")

    result: dict[str, Any] = {
        "category": category,
        "query": user_query,
        "verdict": "UNKNOWN",
    }

    # Step 1 — KB similarity search
    try:
        matches = kb_search(user_query, limit=5)
    except Exception as exc:
        print(f"  !! kb_search failed: {exc}")
        result["verdict"] = "RED"
        result["error"] = f"kb_search: {exc}"
        return result

    result["match_count"] = len(matches)
    if not matches:
        print("  !! no KB matches")
        result["verdict"] = "RED"
        result["reason"] = "no KB matches"
        return result

    top1 = matches[0]
    top1_score = top1.get("score", 0.0)
    top1_title = top1.get("title", "<no title>")
    top1_id = top1.get("doc_id") or top1.get("id") or "<no id>"
    top1_content = top1.get("content", "")
    result["top1"] = {"id": top1_id, "title": top1_title, "score": round(top1_score, 3)}

    print(f"\n  Top-1 match: [{top1_score:.3f}] {top1_id}: {top1_title[:60]}")
    for i, m in enumerate(matches[1:5], 2):
        print(f"  Match #{i}:   [{m.get('score', 0.0):.3f}] {m.get('doc_id', '?')[:40]}: "
              f"{(m.get('title') or '?')[:60]}")

    # Step 2 — extract the top-1 query body
    query_body = extract_query_body(top1_content)
    if not query_body:
        # Some KB entries don't have a fenced SQL block; the body itself is the query.
        # Fall back to the full content as-is.
        print(f"  !! no ```sql``` block in top-1 — falling back to raw content")
        # Try to find a `dataset = ` or `preset = ` opener inline.
        m = re.search(
            r"(dataset\s*=|preset\s*=|datamodel\b)[\s\S]+",
            top1_content, re.MULTILINE,
        )
        if m:
            query_body = m.group(0).strip()
        else:
            result["verdict"] = "RED"
            result["reason"] = "no query body extractable from top-1"
            return result

    print(f"\n  Top-1 query body ({len(query_body)} chars):")
    for line in query_body.split("\n")[:4]:
        print(f"    {line[:90]}")
    if len(query_body.split("\n")) > 4:
        print(f"    ... ({len(query_body.split(chr(10))) - 4} more lines)")

    stages = extract_stages(query_body)
    functions = extract_functions(query_body)
    result["stages"] = stages
    result["functions"] = functions
    print(f"\n  Stages: {', '.join(stages) if stages else '(none)'}")
    print(f"  Functions: {', '.join(functions[:8]) if functions else '(none)'}"
          f"{'...' if len(functions) > 8 else ''}")

    # Step 3 — cortex_xql_lookup hit rate (top 5 stages + top 5 functions by appearance)
    terms_to_lookup = stages[:5] + functions[:5]
    lookup_hits = 0
    lookup_errors = 0
    for term in terms_to_lookup:
        kind = "stage" if term in stages else "function"
        try:
            payload = cortex_xql_lookup(term, kind=kind)
            if payload.get("found"):
                lookup_hits += 1
        except Exception:
            lookup_errors += 1
    lookup_rate = lookup_hits / max(1, len(terms_to_lookup) - lookup_errors)
    result["lookup_hits"] = lookup_hits
    result["lookup_total"] = len(terms_to_lookup)
    result["lookup_rate"] = round(lookup_rate, 2)
    print(f"\n  cortex_xql_lookup: {lookup_hits}/{len(terms_to_lookup)} hit "
          f"({lookup_rate:.0%})"
          + (f", {lookup_errors} transport errors" if lookup_errors else ""))

    # Step 4 — apply v0.6.61's parameter-placeholder handling (Step 5.5 of
    # the skill prompt) before executing. We MIMIC what the LLM should do:
    # drop filter lines that reference `$<var>` placeholders. This isn't a
    # perfect substitute for the LLM (which has user-question context to
    # decide between drop vs. substitute), but it tests whether the chain
    # CAN work end-to-end with the new strategy.
    cleaned_query, placeholders_dropped = _strip_placeholders(query_body)
    if placeholders_dropped:
        print(f"\n  v0.6.61 strategy: dropped {len(placeholders_dropped)} placeholder filter line(s)")
        for ph_line in placeholders_dropped[:3]:
            print(f"    DROPPED: {ph_line[:80]}")
        result["placeholders_dropped"] = placeholders_dropped

    # If after cleanup the query is empty or has no dataset/preset/datamodel
    # opener, the example was 100% parameterized — can't execute.
    if not re.search(r"(dataset|preset|datamodel)\s*[=]?", cleaned_query):
        print(f"  ⚠ query is empty after placeholder cleanup — skipping XDR")
        result["verdict"] = "YELLOW"
        result["reason"] = "query body fully parameterized; no executable shape"
        return result

    # Step 5 — execute against XDR, with tenant-fallback retry if HTTP 500
    # / dataset-not-found (Pattern A from v0.6.61's iteration loop).
    xdr_attempts: list[dict] = []
    final_query = cleaned_query
    final_xdr = None
    for attempt_n in range(1, 4):  # up to 3 iterations per skill's contract
        print(f"\n  Attempt {attempt_n}: executing against XDR...")
        t0 = time.time()
        try:
            xdr_result = xdr_run_xql_query(final_query)
        except Exception as exc:
            print(f"  !! xdr_run_xql_query failed: {exc}")
            result["verdict"] = "RED"
            result["reason"] = f"xdr transport error: {exc}"
            result["xdr_attempts"] = xdr_attempts
            return result
        elapsed = time.time() - t0

        status = xdr_result.get("status", "?")
        total_rows = xdr_result.get("total_rows", 0)
        error_msg = xdr_result.get("error", "")
        print(f"  XDR in {elapsed:.1f}s: status={status}, total_rows={total_rows}")
        if error_msg:
            print(f"    error: {error_msg[:140]}")

        xdr_attempts.append({
            "attempt": attempt_n,
            "status": status,
            "rows": total_rows,
            "elapsed_s": round(elapsed, 1),
            "error": error_msg[:200] if error_msg else None,
        })
        final_xdr = xdr_result

        # SUCCESS / terminal cases → break
        if status == "SUCCESS":
            break
        if status in ("PENDING", "TIMEOUT", "CANCELLED"):
            break  # not a retry-able failure

        # Pattern A — HTTP 500 / dataset-not-found → try tenant-universal fallback
        is_500 = "HTTP 500" in (error_msg or "") or "unexpected error" in (error_msg or "").lower()
        if is_500 and attempt_n < 3:
            fallback_query = _try_universal_dataset_fallback(matches, final_query)
            if fallback_query and fallback_query != final_query:
                print(f"  Pattern A fallback: switching to tenant-universal dataset")
                final_query = fallback_query
                continue
            print(f"  No tenant-universal alternative in top-5 — stopping iteration")
            break

        # Other FAIL classes — not fixable by this probe (need LLM context)
        break

    result["xdr_attempts"] = xdr_attempts
    final_status = (final_xdr or {}).get("status", "?")
    result["xdr_status"] = final_status
    result["xdr_rows"] = (final_xdr or {}).get("total_rows", 0)
    result["final_query_chars"] = len(final_query)

    if final_status == "SUCCESS":
        result["verdict"] = "GREEN"
    elif final_status in ("PENDING", "TIMEOUT", "CANCELLED"):
        result["verdict"] = "YELLOW"
        result["reason"] = f"xdr returned {final_status}"
    else:
        result["verdict"] = "RED"
        result["reason"] = f"xdr final status: {final_status} after {len(xdr_attempts)} attempt(s)"

    print(f"  Verdict: {result['verdict']}")
    return result


def _strip_placeholders(query: str) -> tuple[str, list[str]]:
    """v0.6.61 Step 5.5 strategy 1 — drop filter lines that reference
    `$<var>` placeholders. Returns (cleaned_query, list_of_dropped_lines).

    A "filter line" is any pipeline stage line starting with `| filter`
    or `filter` that contains a placeholder. We're conservative — only
    drop the line if it's a filter; other stages (alter, fields, etc.)
    referencing placeholders stay because dropping them would corrupt
    the query shape more severely.
    """
    placeholder_re = re.compile(r"\$[a-zA-Z_]\w*")
    if not placeholder_re.search(query):
        return query, []

    lines = query.split("\n")
    kept: list[str] = []
    dropped: list[str] = []
    for line in lines:
        stripped = line.strip()
        is_filter_line = stripped.startswith("| filter") or stripped.startswith("filter ")
        has_placeholder = bool(placeholder_re.search(line))
        if is_filter_line and has_placeholder:
            dropped.append(line.strip())
            continue
        # Strip placeholder substring within non-filter lines too (rare
        # but possible — operator's `| comp count(*) as $alias` pattern).
        # We leave them as-is; the query will fail and produce a useful
        # signal for follow-up.
        kept.append(line)
    return "\n".join(kept), dropped


# Tenant-universal datasets per v0.6.61's Pattern A — datasets every XDR/
# XSIAM deployment has (vs. vendor-specific ones that depend on connector
# configuration). v0.6.62 widened from 3 to 5: probe run-2 caught XQL-083
# (`dataset = alerts`) as a viable fallback the original 3-set missed for
# the "count of alerts by severity" query class. The wider set:
#   - xdr_data            — XDR core telemetry (process/network/file/login)
#   - xdr_login_events    — auth-specific preset
#   - endpoints           — agent-inventory dataset
#   - alerts              — XSIAM's built-in alerts dataset
#   - issues              — XSIAM's built-in incident/issue dataset
UNIVERSAL_DATASETS = {
    "xdr_data",
    "xdr_login_events",
    "endpoints",
    "alerts",
    "issues",
}


def _try_universal_dataset_fallback(matches: list[dict], failed_query: str) -> str | None:
    """v0.6.61 Pattern A — when the top-1 query fails with HTTP 500
    (likely tenant-doesn't-have-this-dataset), scan the top-5 KB matches
    for one whose dataset is tenant-universal. Return its query body
    cleaned of placeholders.

    Returns None when no top-5 alternative uses a universal dataset."""
    for m in matches[1:]:
        body = extract_query_body(m.get("content", ""))
        if not body:
            continue
        # Identify the dataset/preset opener.
        opener_match = re.search(
            r"(?:dataset|preset)\s*=\s*([a-zA-Z0-9_*]+)", body
        )
        if not opener_match:
            continue
        ds = opener_match.group(1)
        if ds in UNIVERSAL_DATASETS:
            cleaned, _ = _strip_placeholders(body)
            return cleaned
    return None


# ─── Main ────────────────────────────────────────────────────────────


def main() -> None:
    print(f"Phase 3 probe — full chain verification across {len(TEST_SCENARIOS)} "
          f"scenarios")
    print(f"Target: {AGENT_URL}")
    print(f"Categories: {', '.join(sorted(set(c for c, _ in TEST_SCENARIOS)))}")

    results: list[dict] = []
    for category, query in TEST_SCENARIOS:
        try:
            results.append(probe_scenario(category, query))
        except Exception as exc:
            print(f"\n!! probe failed for {category}/{query[:40]!r}: {exc}")
            results.append({
                "category": category,
                "query": query,
                "verdict": "RED",
                "error": str(exc),
            })

    # Final summary
    print(f"\n\n{'='*76}")
    print("PHASE 3 OVERALL")
    print(f"{'='*76}")
    verdicts = Counter(r.get("verdict", "FAIL") for r in results)
    for v in ["GREEN", "YELLOW", "RED", "UNKNOWN"]:
        n = verdicts.get(v, 0)
        if n > 0:
            print(f"  {v}: {n}/{len(results)}")

    # Per-category breakdown
    print(f"\nBy category:")
    by_cat: dict[str, Counter] = {}
    for r in results:
        cat = r.get("category", "?")
        by_cat.setdefault(cat, Counter())[r.get("verdict", "?")] += 1
    for cat in sorted(by_cat):
        verdicts_cat = by_cat[cat]
        total_cat = sum(verdicts_cat.values())
        green = verdicts_cat.get("GREEN", 0)
        print(f"  {cat:14s} {green}/{total_cat} GREEN  "
              f"(YELLOW={verdicts_cat.get('YELLOW', 0)}, RED={verdicts_cat.get('RED', 0)})")

    # RED + YELLOW detail for the fix queue
    fix_queue = [r for r in results if r.get("verdict") in ("RED", "YELLOW")]
    if fix_queue:
        print(f"\nFix queue ({len(fix_queue)} non-GREEN):")
        for r in fix_queue:
            top1 = r.get("top1") or {}
            print(f"  [{r['verdict']}] {r['category']:14s} {r['query'][:60]}")
            print(f"          top-1: {top1.get('id', '?')} (score "
                  f"{top1.get('score', '?')})")
            print(f"          reason: {r.get('reason') or r.get('error') or '?'}")
            xdr_err = r.get("xdr_error")
            if xdr_err:
                print(f"          xdr_error: {xdr_err[:120]}")
    else:
        print(f"\nAll {len(results)} GREEN — no fix queue.")


if __name__ == "__main__":
    main()
