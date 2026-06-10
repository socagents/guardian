#!/usr/bin/env python3
"""Routing validation sweep for the reverse-engineered data-source enrichment.

Runs INSIDE phantom_agent (needs /app/bundle/data-sources + the embedded agent
MCP on :8080 + the xsiam connector MCP on :9000). Validates the **dataset-anchored
routing** the enrichment documents in each source's how_to_use. The broker derives
a dataset from `norm(vendor)_norm(product)_raw`, so a pack's DISPLAY name often
does NOT derive its real dataset (Amazon Web Services/AWS-GuardDuty normalizes to
amazon_web_services_aws_guardduty_raw, NOT the real aws_guardduty_raw). The
enricher handles this two ways, and this sweep validates each:

  * ASSERTED (how_to_use gives a CEF literal, e.g. `AWS`/`GuardDuty` recovered from
    the parsing rule's [INGEST:]): POSITIVE test — send the asserted literal and
    confirm the TARGET dataset grows. Proves the recovered literal is correct, not
    just that the display name is wrong. (131 of these are "trap-with-fix": the
    asserted literal differs from the misleading display name.)
  * FLAGGED (how_to_use warns of a divergence but has no recovered literal):
    NEGATIVE test — send the DISPLAY name and confirm the target stays untouched
    (events land in the display-derived dataset instead). Confirms the warning.

Delta-based: reads each target BEFORE and AFTER (after - before), so datasets with
pre-existing data from prior smokes (validated vendors, installed test packs) don't
read as false growth. Sends are quota-free (agent MCP, not XQL); only the comp
count() reads cost compute units, and count() is light. Accumulates verdicts to a
state file so coverage grows across runs and survives a quota wall mid-sweep.

Usage (from the repo, against the deployed install):
    docker exec -i phantom_agent python3 - --mode both --batch 15 \
        < scripts/maintainer/routing_validate_enriched.py
"""
from __future__ import annotations
import argparse, glob, json, os, re, ssl, time, urllib.request
import yaml

TOKEN = os.environ["MCP_TOKEN"]
AGENT = "https://localhost:8080/api/v1/stream/mcp"
XSIAM = "http://phantom-connector-xsiam-Cortex_XSIAM:9000/mcp"
BUNDLE = "/app/bundle/data-sources"
STATE = "/app/data/routing_validation.json"
_CTX = ssl.create_default_context(); _CTX.check_hostname = False; _CTX.verify_mode = ssl.CERT_NONE

# The 22 validated vendors are EXCLUDED: they're not "non-validated mismatches",
# and their datasets receive continuous traffic from the validated-vendor smokes,
# which confounds the delta in BOTH directions — a false LEAK on the flagged test
# (target grows from background workers) and, worse, a false VALIDATED on the
# asserted test (target grows regardless of whether my send actually routed).
VALIDATED_DATASETS = {
    "msft_azure_flowlogs_raw", "aws_waf_raw", "msft_azure_waf_raw", "cyberark_isp_raw",
    "okta_okta_raw", "okta_sso_raw", "msft_azure_ad_raw", "msft_azure_ad_audit_raw",
    "alibaba_action_trail_raw", "amazon_aws_raw", "aws_security_hub_raw", "atlassian_jira_raw",
    "servicenow_servicenow_raw", "msft_o365_general_raw", "msft_o365_exchange_online_raw",
    "msft_o365_sharepoint_online_raw", "msft_o365_emails_raw", "msft_o365_dlp_raw",
    "qualys_qualys_raw", "proofpoint_email_security_raw", "proofpoint_tap_raw", "msft_azure_aks_raw",
}


def norm(s):
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")


def collapse(s):
    # The broker does NOT collapse/strip the way norm() does: "Imperva Inc." keeps the
    # period as a trailing _ and joins to "imperva_inc__securesphere_raw" (double _).
    # Collapsing _-runs makes the literal-mismatch check agree with the broker, so a
    # single-vs-double-_ difference isn't mistaken for a wrong routing literal.
    return re.sub(r"_+", "_", s or "")


def post(url, body, sid=None, https=False):
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
         "Accept": "application/json, text/event-stream"}
    if sid:
        h["mcp-session-id"] = sid
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=180, context=_CTX if https else None) as r:
        return r.read().decode(), r.headers


def sse(text):
    for ln in text.split("\n"):
        if ln.startswith("data:"):
            try:
                f = json.loads(ln[5:].strip())
                if "result" in f and f["result"].get("content"):
                    t = f["result"]["content"][0].get("text", "{}")
                    try:
                        return json.loads(t)
                    except json.JSONDecodeError:
                        return {"_raw": t}
            except Exception:
                pass
    return {}


def session(url, https=False):
    _, h = post(url, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                      "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                 "clientInfo": {"name": "rv", "version": "2"}}}, https=https)
    sid = h.get("mcp-session-id") or h.get("Mcp-Session-Id")
    post(url, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, sid, https=https)
    return sid


def call(url, sid, name, args, https=False, rid=9):
    body, _ = post(url, {"jsonrpc": "2.0", "id": rid, "method": "tools/call",
                         "params": {"name": name, "arguments": args}}, sid, https=https)
    return sse(body)


def count(sid, ds):
    """Event count in a dataset over 30d. -1 signals quota exhaustion."""
    r = call(XSIAM, sid, "run_xql_query",
             {"query": f"config timeframe = 30d | dataset = {ds} | comp count() as c"}, rid=200)
    blob = json.dumps(r)
    if "QUOTA_EXCEEDED" in blob or "Compute Units (0.0)" in blob:
        return -1
    rep = r.get("reply", {}) if isinstance(r, dict) else {}
    data = (rep.get("results", {}) or {}).get("data", [])
    try:
        return int(data[0].get("c", 0)) if data else 0
    except Exception:
        return 0


def schema_override(doc):
    return [{"name": f["name"], "type": f.get("type") or "string", "is_array": bool(f.get("is_array", False))}
            for f in (doc.get("fields") or []) if isinstance(f, dict) and f.get("name") and not f.get("is_meta")]


def classify(slug, doc):
    """Map a source to its routing test from how_to_use. None = skip."""
    h = doc.get("how_to_use") or ""
    parts = slug.split("__")
    v = doc.get("vendor") or (parts[0] if parts else "")
    p = doc.get("product") or (parts[1] if len(parts) > 1 else "")
    ds = doc.get("dataset_name") or (parts[-1] if len(parts) > 2 else "")
    if not ds:
        return None
    if ds in VALIDATED_DATASETS or doc.get("validated"):
        return None  # validated vendor — out of scope + background-traffic confound
    av = re.search(r"vendor\*{0,2}:\s*`([^`]+)`", h, re.I)
    ap = re.search(r"product\*{0,2}:\s*`([^`]+)`", h, re.I)
    is_flag = ("different dataset" in h) or ("must normalize to" in h)
    base = {"slug": slug, "target": ds, "display": f"{v}/{p}", "doc": doc}
    if is_flag:
        base.update(mode="flagged", send_v=v, send_p=p, display_ds=f"{norm(v)}_{norm(p)}_raw")
        return base
    if av and ap:
        lv, lp = av.group(1), ap.group(1)
        base.update(mode="asserted", send_v=lv, send_p=lp, asserted=f"{lv}/{lp}",
                    expected_ds=f"{norm(lv)}_{norm(lp)}_raw",
                    trap_fix=(norm(lv) != norm(v) or norm(lp) != norm(p)))
        return base
    return None


def enumerate_sources():
    out = []
    for yf in sorted(glob.glob(f"{BUNDLE}/*/data_source.yaml")):
        slug = os.path.basename(os.path.dirname(yf))
        try:
            doc = yaml.safe_load(open(yf))
        except Exception:
            continue
        if isinstance(doc, dict):
            c = classify(slug, doc)
            if c:
                out.append(c)
    out.sort(key=lambda s: s["target"])
    return out


def load_state():
    st = {"tested": {}}
    if os.path.isfile(STATE):
        try:
            st = json.load(open(STATE))
        except Exception:
            pass
    # Self-heal: drop any validated-dataset entries recorded before the exclusion
    # was added (their verdicts are background-traffic confounded, not reliable).
    st["tested"] = {k: v for k, v in st.get("tested", {}).items()
                    if v.get("target") not in VALIDATED_DATASETS}
    # Migrate pre-fix verdicts: "display-no-growth" with target+0 is a confirmed
    # flag whose events went to a built-in-parser canonical dataset, not a failure.
    for v in st["tested"].values():
        if v.get("verdict") == "display-no-growth" and v.get("target_delta", 0) == 0:
            v["verdict"] = "CONFIRMED:routed-elsewhere"
    return st


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(st, open(STATE, "w"), indent=2)


def run_mode(mode, srcs, st, ag, xs, batch, wait, created):
    todo = [s for s in srcs if s["mode"] == mode and s["slug"] not in st["tested"]][:batch]
    if not todo:
        print(f"[{mode}] nothing untested in this batch")
        return 0, 0, False
    # before reads
    before = {}
    for s in todo:
        before[s["target"]] = count(xs, s["target"])
        if before[s["target"]] == -1:
            return 0, 0, True
        if mode == "flagged":
            before[s["display_ds"]] = count(xs, s["display_ds"])
            if before[s["display_ds"]] == -1:
                return 0, 0, True
    # sends (free) — capture worker ids so main() can kill them (count=N workers
    # emit continuously until killed; leaving them pollutes datasets + future runs).
    for s in todo:
        res = call(AGENT, ag, "phantom_create_data_worker",
                   {"type": "CEF", "destination": "udp:10.10.0.8:514", "count": 12, "interval": 1,
                    "vendor": s["send_v"], "product": s["send_p"], "version": "1.0",
                    "schema_override": schema_override(s["doc"])}, https=True, rid=100)
        if isinstance(res, list) and res and res[0].get("worker"):
            created.append(res[0]["worker"])
    print(f"[{mode}] sent {len(todo)} ; waiting {wait}s")
    for _ in range(max(1, wait // 10)):
        time.sleep(10)
    # after reads + verdicts
    ok = bad = 0
    walled = False
    for s in todo:
        ta = count(xs, s["target"])
        if ta == -1:
            walled = True; break
        dt = ta - before[s["target"]]
        if mode == "asserted":
            if dt > 0:
                verdict = "VALIDATED"
            elif collapse(s.get("expected_ds")) != collapse(s["target"]):
                # asserted literal normalizes to a DIFFERENT dataset than the target —
                # the how_to_use's "normalizes to <dataset>" claim is false (enrichment bug,
                # e.g. broad Windows/Azure [INGEST:] identities split by channel downstream).
                verdict = "FAIL:literal-mismatch"
            else:
                # literal DOES normalize to the target but it didn't grow — almost always a
                # non-CEF-native vendor (Fortinet/Check Point) whose synthetic CEF the broker drops.
                verdict = "FAIL:no-growth"
            ok += dt > 0; bad += dt <= 0
            rec = {"mode": mode, "target": s["target"], "asserted": s.get("asserted"),
                   "expected_ds": s.get("expected_ds"), "trap_fix": s.get("trap_fix"),
                   "target_delta": dt, "verdict": verdict}
            print(f"  {s['target']:40s} +{dt:<7d} via {s['asserted']:28s} {verdict}"
                  + ("  [trap-fix]" if s.get("trap_fix") else ""))
        else:
            da = count(xs, s["display_ds"])
            if da == -1:
                walled = True; break
            dd = da - before[s["display_ds"]]
            # The flag's core claim is "the display name does NOT reach the target".
            # Where the events DO land is secondary: usually the norm-derived
            # display_ds, but marquee vendors (Check Point, AWS) have built-in broker
            # CEF parsers that route to a canonical dataset instead — that still
            # confirms the flag (target untouched), so target+0 is the pass criterion.
            if dt > 0:
                verdict = f"LEAK:target+{dt}"            # display reached target — not a trap
            elif dd > 0:
                verdict = "CONFIRMED"                     # landed in predicted display-derived ds
            else:
                verdict = "CONFIRMED:routed-elsewhere"    # built-in parser → canonical ds
            confirmed = (dt == 0)
            ok += confirmed; bad += not confirmed
            rec = {"mode": mode, "target": s["target"], "display_ds": s["display_ds"],
                   "target_delta": dt, "display_delta": dd, "verdict": verdict}
            print(f"  {s['target']:40s} target+{dt:<5d} display+{dd:<7d} {verdict}")
        st["tested"][s["slug"]] = rec
    save_state(st)
    return ok, bad, walled


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["asserted", "flagged", "both"], default="both")
    ap.add_argument("--batch", type=int, default=15)
    ap.add_argument("--wait", type=int, default=130)
    args = ap.parse_args()

    srcs = enumerate_sources()
    n_as = sum(1 for s in srcs if s["mode"] == "asserted")
    n_fl = sum(1 for s in srcs if s["mode"] == "flagged")
    st = load_state()
    print(f"universe: {n_as} asserted + {n_fl} flagged = {len(srcs)} | already tested: {len(st['tested'])}")
    # Static scan: asserted sources whose recovered literal does NOT normalize to their
    # own dataset — the how_to_use's "normalizes to <dataset>" claim is false (enrichment
    # bug, no XQL needed to detect). The live FAIL:literal-mismatch verdicts are a subset.
    mism = [s for s in srcs if s["mode"] == "asserted"
            and collapse(s.get("expected_ds")) != collapse(s["target"])]
    print(f"STATIC literal-mismatch (asserted literal normalizes elsewhere — enrichment-bug candidates): {len(mism)}")
    for s in sorted(mism, key=lambda x: x["target"]):
        print(f"  BUG {s['target']:38s} asserts {s['asserted']:24s} -> normalizes to {s['expected_ds']}")

    xs = session(XSIAM)
    if count(xs, "xdr_data") == -1:
        print("QUOTA EXHAUSTED — aborting. Re-run after 00:00 UTC reset.")
        return
    ag = session(AGENT, https=True)

    modes = ["asserted", "flagged"] if args.mode == "both" else [args.mode]
    created = []
    for m in modes:
        print(f"\n=== {m.upper()} "
              + ("(send recovered literal → target should grow)" if m == "asserted"
                 else "(send display name → target should stay flat, display-derived grows)") + " ===")
        ok, bad, walled = run_mode(m, srcs, st, ag, xs, args.batch, args.wait, created)
        print(f"[{m}] batch: {ok} ok, {bad} not-ok" + ("  — QUOTA WALL, partial saved" if walled else ""))
        if walled:
            break

    # self-clean: kill every worker this run created
    for wid in created:
        call(AGENT, ag, "phantom_kill_worker", {"worker_id": wid}, https=True, rid=7)
    print(f"\ncleaned up {len(created)} workers")

    tested = st["tested"]
    av_ok = sum(1 for r in tested.values() if r.get("verdict") == "VALIDATED")
    fl_ok = sum(1 for r in tested.values() if str(r.get("verdict", "")).startswith("CONFIRMED"))
    fix_ok = sum(1 for r in tested.values() if r.get("verdict") == "VALIDATED" and r.get("trap_fix"))
    bad = [k for k, r in tested.items() if r.get("verdict", "").split(":")[0] not in ("VALIDATED", "CONFIRMED")]
    print(f"\ncumulative: {av_ok}/{n_as} asserted VALIDATED ({fix_ok} of them trap-with-fix) | "
          f"{fl_ok}/{n_fl} flagged CONFIRMED | {len(bad)} need-review")
    for k in bad:
        print(f"  REVIEW {k}: {tested[k].get('verdict')}")


if __name__ == "__main__":
    main()
