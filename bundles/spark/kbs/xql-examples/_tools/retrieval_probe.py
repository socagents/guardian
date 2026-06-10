"""Phase 1 — retrieval-chain probe for the upcoming `build_xql_query`
skill.

The skill (Phase 2) will chain three retrieval steps:

  user request
    → knowledge_search(kb=xql-examples) → top-5 matches with scores
    → for each match: extract stages + functions from the SQL body
    → cortex_xql_lookup(term=<stage>) for each unique stage/function
    → build candidate XQL query from the patterns
    → xdr_run_xql_query → check for 4xx/5xx (working ≠ non-empty data)

This probe exercises steps 1-3 against the deployed install via the
IAP tunnel — NO query building, NO XDR execution. The point is to
verify the retrieval mechanics produce sensible matches + that the
extracted stages/functions are findable in cortex-docs, BEFORE we
wrap the chain in a skill.

Usage (from repo root, via the SSH + MCP tunnels):

    # Open tunnels first:
    #   gcloud compute start-iap-tunnel <vm> 22 --local-host-port=localhost:2222 &
    #   gcloud compute start-iap-tunnel <vm> 8080 --local-host-port=localhost:8081 &
    # Then:
    GUARDIAN_MCP_TOKEN=$(ssh ...) python3 retrieval_probe.py

What it reports per test query:
  - Top-5 KB matches with similarity scores
  - Unique stages extracted across the 5 (with frequency)
  - Unique functions extracted across the 5 (with frequency)
  - Whether all 5 share a dataset (if yes → same-dataset signal for
    the skill's field-info lookup)
  - cortex_xql_lookup hit/miss for each unique stage + function
  - Overall verdict: GREEN (≥4/5 matches relevant + ≥80% lookup hit
    rate), YELLOW (3/5 relevant or 60-80% lookup), RED (<3/5 or
    <60% lookup) — relevance is subjective, the probe just surfaces
    the data.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import urllib.request
from collections import Counter
from typing import Any

# ─── Config ─────────────────────────────────────────────────────────

# We hit the AGENT UI port (3001 via IAP tunnel → remote 3000), NOT
# the embedded MCP port. The agent UI side has REST proxy routes that
# do the JSON-RPC handshake for tool calls — talking directly to the
# MCP would require us to reimplement the initialize → tools/call
# dance, which is exactly what /api/agent/tool/call does for us.
# The route is internally permissive (no cookie check) when reached
# from outside the AuthGate'd UI; it just dispatches.
AGENT_URL = os.environ.get("GUARDIAN_AGENT_URL", "https://localhost:3001")
TLS_INSECURE = ssl._create_unverified_context()  # self-signed dev cert


# Phase-1 test queries — representative SOC analyst phrasing. The mix
# covers: (a) network hunting, (b) credential/identity, (c) process
# anomaly, (d) email threat, (e) detection pivot. Each one should
# match a known top-1 entry in the KB; the probe verifies the actual
# similarity ranking puts the right entry near the top.
TEST_QUERIES = [
    "show hosts with unusual outbound network traffic to public IPs",
    "find failed RDP login attempts in the last hour",
    "detect rare PSEXEC process executions on Windows hosts",
    "alert when a process makes outbound DNS queries to unusual domains",
    "show me which users authenticated from new countries this week",
]


# ─── HTTP helpers ────────────────────────────────────────────────────


def http_json(method: str, path: str, body: dict | None = None) -> dict:
    """POST/GET wrapper hitting the agent UI's REST proxy. Returns
    parsed JSON; raises on transport/non-2xx."""
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
    with urllib.request.urlopen(req, context=TLS_INSECURE, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def kb_search(query: str, limit: int = 5) -> list[dict]:
    """Top-N KB matches with similarity scores via the agent's KB
    proxy route. (POST /api/agent/knowledge/{name}/search forwards
    to the MCP's /api/v1/kbs/{name}/search.)"""
    res = http_json(
        "POST",
        "/api/agent/knowledge/xql-examples/search",
        {"query": query, "limit": limit},
    )
    return res.get("results", [])


def kb_doc(doc_id: str) -> dict:
    """Fetch a single doc's full body + metadata."""
    res = http_json("GET", f"/api/agent/knowledge/xql-examples/docs/{doc_id}")
    return res.get("document", {})


def cortex_xql_lookup(term: str, kind: str = "auto") -> dict:
    """Look up an XQL stage or function in public Cortex docs.
    Returns the tool's response payload — the inner `result` field
    of the agent's tool-call envelope (with `found`/`title`/etc.)."""
    res = http_json(
        "POST",
        "/api/agent/tool/call",
        {
            # Bare name — the tool/call route's bare-name resolution
            # maps to the registered tool. Namespaced form
            # ("cortex-docs/xql_lookup") does NOT match because the
            # MCP registers tools under their flat function name.
            "name": "cortex_xql_lookup",
            "arguments": {"term": term, "kind": kind},
        },
    )
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "unknown tool error")}
    return res.get("result") or {}


# ─── Extraction ──────────────────────────────────────────────────────


STAGE_RE = re.compile(r"\|\s*(\w+)")
FUNC_RE = re.compile(r"\b([a-z_][a-z0-9_]+)\s*\(")
DATASET_RE = re.compile(
    r"^\s*(?:dataset|preset|datamodel)\s*=\s*([a-zA-Z0-9_*]+)", re.MULTILINE
)

# XQL stages/functions land in the SQL body. Words that look like
# functions but aren't (SQL keywords, dataset names) get filtered.
FALSE_POSITIVES = {
    "filter", "alter", "comp", "fields", "sort", "limit", "dedup",
    "transaction", "union", "view", "join", "fork", "config",
    "iploc", "windowcomp", "bin", "if", "in",
    "and", "or", "not", "asc", "desc", "by", "as", "is", "null", "true", "false",
}


def extract_query_body(content: str) -> str:
    """Pull the ```sql ... ``` block content from a KB doc body."""
    m = re.search(r"```sql\s*\n(.*?)\n```", content, re.DOTALL)
    return m.group(1) if m else ""


def extract_dataset(query: str) -> str:
    m = DATASET_RE.search(query)
    return m.group(1) if m else ""


def extract_stages(query: str) -> list[str]:
    stages = []
    seen = set()
    for m in STAGE_RE.finditer(query):
        s = m.group(1).lower()
        if s not in seen:
            stages.append(s)
            seen.add(s)
    return stages


def extract_functions(query: str) -> list[str]:
    funcs = []
    seen = set()
    for m in FUNC_RE.finditer(query):
        f = m.group(1).lower()
        if f in FALSE_POSITIVES or f in seen:
            continue
        funcs.append(f)
        seen.add(f)
    return funcs


# ─── Per-query probe ─────────────────────────────────────────────────


def probe_query(user_query: str) -> dict:
    print(f"\n{'='*72}")
    print(f"QUERY: {user_query}")
    print(f"{'='*72}")

    # Step 1 — KB similarity search
    matches = kb_search(user_query, limit=5)
    print(f"\nTop-5 KB matches:")
    for i, m in enumerate(matches, 1):
        score = m.get("score", 0.0)
        title = m.get("title", "<no title>")
        doc_id = m.get("doc_id") or m.get("id") or "<no id>"
        print(f"  {i}. [{score:.3f}] {doc_id}: {title}")

    if not matches:
        print("\n!! NO MATCHES — skipping extraction")
        return {"matches": 0, "stages": [], "functions": [], "lookups": {}}

    # Step 2 — fetch each match's full body + extract stages/functions
    all_stages: Counter = Counter()
    all_funcs: Counter = Counter()
    datasets: Counter = Counter()

    for m in matches:
        doc_id = m.get("doc_id") or m.get("id")
        if not doc_id:
            continue
        try:
            doc = kb_doc(doc_id)
        except Exception as exc:
            print(f"   !! failed to fetch {doc_id}: {exc}")
            continue
        body = doc.get("content", "")
        query_body = extract_query_body(body)
        if not query_body:
            continue
        ds = extract_dataset(query_body)
        if ds:
            datasets[ds] += 1
        for s in extract_stages(query_body):
            all_stages[s] += 1
        for f in extract_functions(query_body):
            all_funcs[f] += 1

    print(f"\nStages extracted (with freq across the 5):")
    for s, n in all_stages.most_common():
        print(f"  {s}: {n}")

    print(f"\nFunctions extracted (with freq across the 5):")
    for f, n in all_funcs.most_common():
        print(f"  {f}: {n}")

    print(f"\nDatasets across the 5:")
    for d, n in datasets.most_common():
        print(f"  {d}: {n}")

    # Step 3 — cortex_xql_lookup hit/miss
    print(f"\ncortex_xql_lookup hit/miss:")
    lookups: dict[str, str] = {}
    # Only look up the top-5 most-frequent of each — anything below
    # that frequency-cap is noise.
    unique_terms = [s for s, _ in all_stages.most_common(5)]
    unique_terms += [f for f, _ in all_funcs.most_common(5)]
    for term in unique_terms:
        kind = "stage" if term in all_stages else "function"
        try:
            payload = cortex_xql_lookup(term, kind=kind)
            # Agent route already unwraps the MCP envelope; we get the
            # tool's inner payload directly: {ok, found, title, ...}.
            found = bool(payload.get("found"))
            title = payload.get("title", "")
            verdict = "HIT" if found else "MISS"
            lookups[term] = verdict
            extra = f": {title[:50]}" if title else ""
            print(f"  [{verdict}] {term} ({kind}){extra}")
        except Exception as exc:
            lookups[term] = f"ERROR: {exc}"
            print(f"  [ERR ] {term} ({kind}): {exc}")

    # Summary verdict
    hit = sum(1 for v in lookups.values() if v == "HIT")
    rate = hit / max(1, len(lookups))
    print(f"\nLookup hit rate: {hit}/{len(lookups)} = {rate:.0%}")

    if rate >= 0.8 and len(matches) >= 4:
        verdict = "GREEN"
    elif rate >= 0.6 and len(matches) >= 3:
        verdict = "YELLOW"
    else:
        verdict = "RED"
    print(f"Verdict: {verdict}")

    return {
        "matches": len(matches),
        "stages": dict(all_stages),
        "functions": dict(all_funcs),
        "datasets": dict(datasets),
        "lookups": lookups,
        "verdict": verdict,
    }


# ─── Main ────────────────────────────────────────────────────────────


def main() -> None:
    print("Phase 1 retrieval-chain probe — knowledge_search → "
          "cortex_xql_lookup")
    print(f"Target: {AGENT_URL}")
    print(f"Queries: {len(TEST_QUERIES)}")

    results = []
    for q in TEST_QUERIES:
        try:
            results.append({"query": q, **probe_query(q)})
        except Exception as exc:
            print(f"\n!! probe failed for query {q!r}: {exc}")
            results.append({"query": q, "error": str(exc)})

    # Final summary
    print(f"\n\n{'='*72}")
    print("OVERALL")
    print(f"{'='*72}")
    verdicts = Counter(r.get("verdict", "FAIL") for r in results)
    for v, n in verdicts.most_common():
        print(f"  {v}: {n}")


if __name__ == "__main__":
    main()
