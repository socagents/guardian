# XQL regression harness

A canonical, **live-verified** corpus of Cortex XSIAM XQL idioms plus a sequential
runner that re-checks them against a real tenant. It guards Guardian's XQL-authoring
knowledge (the `cortex_xql_query_authoring` skill + the `xql-examples` KB entries
289–320) from silent drift.

## Why this exists

XQL fails *silently and generically*: an invalid function name returns a bare
HTTP 500 (`"An unexpected error occurred"`) with no hint, and one bad token poisons
the whole query. So the authoring knowledge is built from **value-checked live
testing**, and this harness keeps it honest over time. Every case asserts an
expectation:

- `expect="ok"` — a known-good idiom that must run to `SUCCESS` (optionally with
  named columns present).
- `expect="syntax_error"` — a name/stage that does **not** exist in XQL and must
  fail to start. These are the drift detectors: if Palo Alto ever ships `dcount`,
  `stddev`, `lead`, `case`, or `percentile`, that negative case flips to passing and
  the runner flags that our "use X instead of Y" guidance is now stale.

The corpus (`corpus.py`) is the executable form of the same facts encoded in the
KB and the skill — one source the self-learning loop can re-run on a schedule.

## Running it

The runner is zero-dependency (Python 3 stdlib only). Provide tenant credentials by
environment variable or `--env-file` (a `KEY=VALUE` file). Credentials are never
logged.

```bash
# via environment
CORTEX_URL='https://<tenant>.xdr.<region>.paloaltonetworks.com' \
CORTEX_KEY='<api-key>' \
CORTEX_AUTH_ID='<api-key-id>' \
python3 run_regression.py

# via a creds file, narrowing to a subset
python3 run_regression.py --env-file ./creds.env --only hunt-
```

Auth auto-detects standard vs Advanced (nonce + timestamp + SHA-256). Exit code is
`0` when every case matched its expectation, `1` if any drifted.

### Lab dataset cases

Cases against `dataset = guardian_xql_lab` need that lookup table seeded — a tiny
10-row table with composite/array/numeric columns used to verify function mechanics
against known values (cost ≈ 0, no `xdr_data` scan). `xdr_data` cases assert query
*shape* only and treat `SUCCESS` with 0 rows as a pass (a quiet tenant is fine).

## Cost

Each case is one bounded query. Lab-dataset cases scan essentially nothing;
`xdr_data` cases use a narrow `--lookback` (default 0.5 h) to stay cheap. The runner
is **sequential** by design — the tenant caps concurrent XQL queries and cost is
metered, so parallel fan-out is the wrong tool here.

## Adding a case

Append to `CASES` in `corpus.py`: `{"id", "query", "expect", ["columns"], ["note"]}`.
Run the harness; if it doesn't behave as you expect, you've either found a new XQL
gotcha (update the skill + KB) or a stale assumption (fix the case). Keep the corpus
and the `cortex_xql_query_authoring` skill in lockstep.
