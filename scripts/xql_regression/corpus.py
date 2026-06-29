"""
Canonical XQL regression corpus — live-verified idioms for Cortex XSIAM.

Each case asserts what we KNOW about XQL, positive and negative:
  - expect="ok"          → the query must run to SUCCESS (valid syntax + semantics)
  - expect="syntax_error"→ the query must FAIL to start (a name/stage that does NOT
                           exist in XQL; XSIAM returns a generic 500). These guard the
                           "use X instead of Y" authoring guidance: if XSIAM ever adds
                           the function, the negative case flips and we re-learn.

`columns` (optional, ok-cases) lists field names that MUST be present in the result.
`dataset` cases against `guardian_xql_lab` need that lookup table seeded (see README);
`xdr_data` cases assert query SHAPE (they may legitimately return 0 rows on a quiet
tenant — the runner treats SUCCESS-with-0-rows as a pass for shape-only cases).

Source of truth: live verification on a real XSIAM tenant (Advanced-auth PAPI),
mirrored by KB entries xql-examples/289-320 and the cortex_xql_query_authoring skill.
"""

LAB = "guardian_xql_lab"

CASES = [
    # ── aggregations: confirmed names ───────────────────────────────────
    {"id": "agg-count-distinct", "expect": "ok", "columns": ["hosts"],
     "query": f"dataset = {LAB} | comp count_distinct(host) as hosts",
     "note": "count_distinct is the valid distinct-count (NOT dcount)"},
    {"id": "agg-avg-min-max-sum", "expect": "ok", "columns": ["a", "mn", "mx", "s"],
     "query": f"dataset = {LAB} | comp avg(bytes_out) as a, min(bytes_out) as mn, max(bytes_out) as mx, sum(bytes_out) as s by dept"},
    {"id": "agg-var", "expect": "ok", "columns": ["v"],
     "query": f"dataset = {LAB} | comp var(bytes_out) as v"},
    {"id": "agg-stddev-via-sqrt-var", "expect": "ok", "columns": ["sd"],
     "query": f"dataset = {LAB} | comp var(bytes_out) as v | alter sd = sqrt(v) | fields sd",
     "note": "no stddev() exists — derive via sqrt(var(x))"},
    {"id": "agg-values", "expect": "ok", "columns": ["hosts"],
     "query": f"dataset = {LAB} | comp values(host) as hosts by dept"},

    # ── aggregations: names that DO NOT exist (must fail) ────────────────
    {"id": "neg-dcount", "expect": "syntax_error",
     "query": f"dataset = {LAB} | comp dcount(host) as h",
     "note": "dcount is Splunk/KQL — use count_distinct"},
    {"id": "neg-stddev", "expect": "syntax_error",
     "query": f"dataset = {LAB} | comp stddev(bytes_out) as sd",
     "note": "no stddev/stdev/std — use sqrt(var())"},
    {"id": "neg-percentile", "expect": "syntax_error",
     "query": f"dataset = {LAB} | comp percentile(bytes_out, 95) as p95",
     "note": "no percentile/approx_percentile aggregation"},

    # ── conditionals ────────────────────────────────────────────────────
    {"id": "cond-nested-if", "expect": "ok", "columns": ["t"],
     "query": f'dataset = {LAB} | alter t = if(bytes_out > 100000, "H", if(bytes_out > 20000, "M", "L")) | fields t',
     "note": "multi-branch = nested if (case is NOT supported)"},
    {"id": "neg-case", "expect": "syntax_error",
     "query": f'dataset = {LAB} | alter t = case(bytes_out > 100000, "H", "L") | fields t',
     "note": "case() does not exist — nest if()"},
    {"id": "cond-coalesce", "expect": "ok", "columns": ["rr"],
     "query": f'dataset = {LAB} | alter rr = coalesce(required_role, "none") | fields rr'},

    # ── windowcomp ──────────────────────────────────────────────────────
    {"id": "win-lag", "expect": "ok", "columns": ["prev_out"],
     "query": f"dataset = {LAB} | windowcomp lag(bytes_out) by dept sort asc event_epoch as prev_out | fields dept, prev_out",
     "note": "lag = prior row in partition; alias LAST"},
    {"id": "neg-lead", "expect": "syntax_error",
     "query": f"dataset = {LAB} | windowcomp lead(bytes_out) by dept sort asc event_epoch as nxt | fields nxt",
     "note": "lead is NOT supported — only lag"},
    {"id": "win-avg-by-group", "expect": "ok", "columns": ["dept_avg", "dev"],
     "query": f"dataset = {LAB} | windowcomp avg(bytes_out) by dept as dept_avg | alter dev = subtract(bytes_out, dept_avg) | fields dept, dept_avg, dev",
     "note": "per-group deviation baseline (stands in for z-score; no window stddev)"},
    {"id": "win-row-number-global", "expect": "ok", "columns": ["rnk"],
     "query": f"dataset = {LAB} | sort desc bytes_out | windowcomp row_number() as rnk | fields rnk, bytes_out"},

    # ── joins ───────────────────────────────────────────────────────────
    {"id": "join-left", "expect": "ok", "columns": ["dept_n"],
     "query": f"dataset = {LAB} | join type = left (dataset = {LAB} | comp count() as dept_n by dept) as r r.dept = dept | fields dept, dept_n"},

    # ── strings + time ──────────────────────────────────────────────────
    {"id": "str-upper-lower", "expect": "ok", "columns": ["u", "l"],
     "query": f"dataset = {LAB} | alter u = uppercase(username), l = lowercase(host) | fields u, l"},
    {"id": "str-replace", "expect": "ok", "columns": ["h"],
     "query": f'dataset = {LAB} | alter h = replace(host, "web", "WEB") | fields h'},

    # ── arrays / composite (the live-found silent-wrong traps) ──────────
    {"id": "arr-array-any-scalar", "expect": "ok", "columns": ["shared"],
     "query": f'dataset = {LAB} | alter roles = json_extract_array(roles_json, "$") | alter peers = json_extract_array(peer_roles_json, "$") | arrayexpand roles | filter array_any(peers, "@element" = roles) | comp values(roles) as shared by username',
     "note": "two-array intersection: explode then array_any against the scalar"},

    # ── stages ──────────────────────────────────────────────────────────
    {"id": "stage-dedup", "expect": "ok", "columns": ["host"],
     "query": f"dataset = {LAB} | sort asc host | dedup host | fields host, username"},

    # ── xdr_data hunt shapes (0 rows is OK; shape must parse + run) ──────
    {"id": "hunt-process-freq", "expect": "ok", "dataset": "xdr_data",
     "query": "dataset = xdr_data | filter event_type = ENUM.PROCESS and actor_process_image_name != null | comp count() as execs by actor_process_image_name | sort desc execs"},
    {"id": "hunt-external-egress-incidr", "expect": "ok", "dataset": "xdr_data",
     "query": 'dataset = xdr_data | filter event_type = ENUM.NETWORK and action_remote_ip != null | filter not action_remote_ip incidr "10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16" | comp count() as conns by actor_process_image_name, action_remote_ip',
     "note": "multi-CIDR comma-OR works as a string LITERAL in a filter"},
    {"id": "hunt-beacon-bin-time", "expect": "ok", "dataset": "xdr_data",
     "query": "dataset = xdr_data | filter event_type = ENUM.NETWORK and action_remote_ip != null | bin _time span = 1m | comp count() as c by actor_process_image_name, action_remote_ip, _time"},
    {"id": "hunt-time-funcs", "expect": "ok", "dataset": "xdr_data",
     "query": 'dataset = xdr_data | filter event_type = ENUM.PROCESS | alter age_s = timestamp_diff(current_time(), _time, "SECOND"), when = format_timestamp("%Y-%m-%d %H:%M:%S", _time) | fields when, age_s'},
]
