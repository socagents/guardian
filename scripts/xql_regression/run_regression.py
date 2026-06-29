#!/usr/bin/env python3
"""
XQL regression runner — re-verifies the canonical corpus against a live XSIAM tenant.

Asserts both that the KNOWN-GOOD idioms still run AND that the KNOWN-BAD names still
fail (drift detection: if XSIAM adds a function we flagged as nonexistent, its negative
case flips and we re-learn). Runs queries SEQUENTIALLY — the tenant caps concurrent
XQL queries, and cost is metered, so this is deliberately not parallel.

Credentials (never logged): set env vars CORTEX_URL, CORTEX_KEY, CORTEX_AUTH_ID, or
pass --env-file PATH (KEY=VALUE lines). Auth auto-detects standard vs Advanced.

Usage:
  CORTEX_URL=... CORTEX_KEY=... CORTEX_AUTH_ID=... python3 run_regression.py
  python3 run_regression.py --env-file /path/to/creds.env --only hunt- --lookback 0.5
Exit code: 0 = all cases matched their expectation; 1 = at least one drifted.
"""
import argparse, hashlib, json, os, re, secrets, string, sys, time, urllib.error, urllib.request

from corpus import CASES


def load_creds(env_file):
    kv = dict(os.environ)
    if env_file:
        for ln in open(env_file):
            m = re.match(r'^([A-Z_][A-Z0-9_]*)=(.*)$', ln.rstrip("\n"))
            if m:
                kv[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    try:
        url, key, aid = kv["CORTEX_URL"], kv["CORTEX_KEY"], kv["CORTEX_AUTH_ID"]
    except KeyError as e:
        sys.exit(f"missing credential {e}; set CORTEX_URL/CORTEX_KEY/CORTEX_AUTH_ID or --env-file")
    base = url.rstrip("/")
    base = (base.split("/public_api")[0].rstrip("/") + "/public_api/v1") if "/public_api" in base else base + "/public_api/v1"
    return base, key, aid


class Client:
    def __init__(self, base, key, aid):
        self.base, self._key, self._aid = base, key, aid
        self.modes = ["standard", "advanced"]  # try standard first, remember the winner

    def _headers(self, mode):
        if mode == "standard":
            return {"Authorization": self._key, "x-xdr-auth-id": self._aid, "Content-Type": "application/json"}
        nonce = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(64))
        ts = str(int(time.time() * 1000))
        h = hashlib.sha256(f"{self._key}{nonce}{ts}".encode()).hexdigest()
        return {"x-xdr-timestamp": ts, "x-xdr-nonce": nonce, "x-xdr-auth-id": self._aid,
                "Authorization": h, "Content-Type": "application/json"}

    def call(self, path, body):
        url = self.base + "/" + path.lstrip("/")
        last = None
        for mode in list(self.modes):
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=self._headers(mode), method="POST")
            try:
                with urllib.request.urlopen(req, timeout=90) as r:
                    if self.modes[0] != mode:
                        self.modes = [mode] + [m for m in self.modes if m != mode]
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                last = {"_http": e.code, "_body": e.read().decode()[:400], "_mode": mode}
                if e.code != 401:
                    return last
        return last


def run_case(cli, query, lookback):
    """Return ('ok', rows) | ('syntax_error', msg) | ('infra', msg) | ('fail', msg)."""
    now = int(time.time() * 1000)
    tf = {"from": now - int(lookback * 3600 * 1000), "to": now}
    for attempt in (1, 2, 3):
        s = cli.call("/xql/start_xql_query/", {"request_data": {"query": query, "tenants": [], "timeframe": tf}})
        body = str(s.get("_body", "")) if isinstance(s, dict) else ""
        http = s.get("_http") if isinstance(s, dict) else None
        if http == 500 and "unexpected error" in body:
            if attempt < 3:
                time.sleep(3); continue
            return "syntax_error", "generic 500 x3"
        if http in (502, 503, 504):
            if attempt < 3:
                time.sleep(4); continue
            return "infra", f"{http} x3"
        if http == 500:  # specific parse error returned in-band
            return "syntax_error", body[:200]
        r0 = s.get("reply") if isinstance(s, dict) else None
        eid = r0 if isinstance(r0, str) else (r0 or {}).get("execution_id") if isinstance(r0, dict) else None
        if not eid:
            return "fail", f"no exec id: {json.dumps(s)[:200]}"
        for _ in range(40):
            time.sleep(1)
            p = cli.call("/xql/get_query_results/", {"request_data": {"query_id": eid, "limit": 200}})
            rep = p.get("reply") or {}
            st = rep.get("status")
            if st == "SUCCESS":
                return "ok", (rep.get("results") or {}).get("data", [])
            if st in ("FAIL", "FAILED", "ERROR", "CANCELLED"):
                return "fail", json.dumps(rep)[:200]
        return "fail", "timeout"
    return "fail", "exhausted"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file", help="KEY=VALUE creds file")
    ap.add_argument("--lookback", type=float, default=0.5, help="hours window for xdr_data cases")
    ap.add_argument("--only", default="", help="substring filter on case id")
    args = ap.parse_args()
    cli = Client(*load_creds(args.env_file))

    cases = [c for c in CASES if args.only in c["id"]]
    passed = failed = 0
    fails = []
    for c in cases:
        outcome, payload = run_case(cli, c["query"], args.lookback)
        exp = c["expect"]
        ok = False
        if exp == "syntax_error":
            ok = outcome == "syntax_error"
        elif exp == "ok":
            if outcome == "ok":
                cols = c.get("columns")
                rows = payload if isinstance(payload, list) else []
                if cols and rows:
                    present = {k for r in rows if isinstance(r, dict) for k in r}
                    ok = all(col in present for col in cols)
                else:
                    ok = True  # shape-only (xdr_data 0-rows allowed) or no column assertion
        if outcome == "infra":
            print(f"  SKIP  {c['id']:<32} (infra: {payload})")
            continue
        if ok:
            passed += 1
            print(f"  PASS  {c['id']:<32} [{outcome}]")
        else:
            failed += 1
            fails.append(c["id"])
            print(f"  FAIL  {c['id']:<32} expected={exp} got={outcome}  {str(payload)[:120]}")
    print(f"\n=== {passed} passed, {failed} failed, {len(cases)} total ===")
    if fails:
        print("FAILED:", ", ".join(fails))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
