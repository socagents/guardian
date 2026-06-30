---
name: cortex_xql_query_authoring
displayName: Cortex XQL query authoring
category: foundation
description: 'Compose authoritative Cortex Query Language (XQL) queries by chaining the operator''s own example-query knowledge base with Palo Alto Networks''s public Cortex documentation. Workflow: (1) embedding-search the operator''s KB for ~5 similar example queries, (2) extract the XQL stages and functions used in those examples, (3) for each stage/function, hit cortex-docs/xql_lookup against the canonical Cortex docs, (4) assemble a focused doc-grounded context, (5) author the query. The cortex-docs connector wraps the Palo Alto Cortex public docs API (XDR / XSIAM / AgentiX / Cortex Cloud / XSOAR / Xpanse) with cortex_search, cortex_suggest, cortex_xql_lookup, cortex_fetch_topic, cortex_fetch_toc, and cortex_deep_research. Triggers when the operator wants to build, fix, or extend an XQL query and needs both an in-house example and authoritative syntax docs.'
icon: query_stats
source: platform
loadingMode: on-demand
locked: false
attack: []
---

# Skill: Cortex XQL query authoring

## Category

foundation

## Purpose

Bridge the operator's **internal query knowledge base** (past queries that worked, sometimes embedded for similarity search) with the **canonical Palo Alto Networks Cortex documentation** so the agent can author XQL queries that are both pattern-correct (matches what the org's queries already look like) and syntax-correct (matches what the docs say each stage and function actually does).

This skill exists because XQL query authoring failure modes split cleanly into two camps:

1. **Pattern drift** — the agent invents an idiom that doesn't match how the org's queries are usually written (wrong dataset names, wrong field aliases, missing org-specific lookups).
2. **Syntax drift** — the agent uses a stage/function that doesn't exist, has the wrong argument order, or has subtle behavioural differences across Cortex products (some functions on AgentiX behave differently than on XSIAM).

Embedding-search against the operator's KB fixes (1). The cortex-docs connector tools fix (2). The skill ties them together.

## Connector tools used

This skill drives the `cortex-docs` connector (added in v0.3.1). The relevant tools:

| Tool | When to call |
|---|---|
| `cortex-docs/xql_lookup` | Primary lookup. Per stage/function name, returns the canonical doc topic with summary content, source citation, and reader URL. Default `product: xql` searches all XQL-capable products. |
| `cortex-docs/search` | Free-text search across all Cortex docs. Use when `xql_lookup` returns `found: false` or when the operator's question isn't a single stage/function (e.g. "how do I bin data into 5-minute buckets?"). |
| `cortex-docs/suggest` | Autocomplete for ambiguous partial terms. Useful when the operator writes "comp" — could be `comp` stage or a typo of `complete`. |
| `cortex-docs/fetch_topic` | Pull full topic content given a `map_id` + `topic_id` from a prior search hit. Use when the lookup summary is too truncated. |
| `cortex-docs/fetch_toc` | Enumerate every topic in a publication. Rarely needed by this skill; useful when the operator wants to browse a topic family. |
| `cortex-docs/deep_research` | Heavyweight (1-3 min). Reserve for explicit multi-section deliverables ("write me a partner briefing on XSIAM alert triage"). DO NOT call from this skill's standard flow — too slow for query authoring. |

For full per-tool argument schema, see the cortex-docs connector page in `/connectors`.

## Standard authoring workflow

### Step 1 — Understand the operator's query intent

Before any tool call, restate the request to confirm scope:

- What's the dataset class? (`xdr_data`, `endpoint_data`, `incident_data`, `lookup table name`, etc.)
- What's the time window?
- What's the output shape — alert? table? aggregation? trend?
- What product context? (XDR? XSIAM? AgentiX? Cloud?)

If any of these is unclear, ask once, then proceed.

### Step 2 — Find ~5 similar examples in the operator's KB

Call **`xql_examples_search(intent="<the analyst intent>", top_k=5)`** — the built-in that searches the bundled `xql-examples` KB AND enriches each hit with `stage_docs` (XQL stage syntax) and `dataset_fields` (the columns you can `| filter` on for the datasets the examples use). That one call gives you the pattern prior *and* the syntax/field context, so you often don't need a per-stage lookup in step 4. (If you only want raw matches, `knowledge_search(query="...", kb_name="xql-examples", limit=5)` works too — but `xql_examples_search` is preferred here.) Aim for 5 hits, top similarity; each is a previously-validated XQL query with metadata about what it did.

If the KB has no relevant entries, skip directly to step 4 — the cortex-docs lookup alone is usable, just less idiomatic.

### Step 3 — Extract stages and functions from the examples

Parse each example query and pull out:

- **Stages** — `filter`, `comp`, `alter`, `sort`, `dedup`, `bin`, `arrayexpand`, `call`, `fields`, `config`, etc. (canonical list of XQL stages: see `cortex-docs/xql_lookup --kind stage --product xql` if you need the authoritative set)
- **Functions** — `arrayindexof`, `json_extract_scalar`, `to_timestamp`, `concat`, `lookup`, etc. Functions appear inside `alter` and `filter` clauses; identify them by `(`...`)` patterns following identifiers.
- **Datasets** — names appearing right after `dataset =` or piped from a lookup. Carry these through unchanged; the operator's KB is authoritative for naming.
- **Org-specific lookups** — `| call ...` references and named query inclusions. Carry through.

Deduplicate. You typically end up with 8-15 unique stages + functions across 5 examples.

### Step 4 — Look up each stage and function in Cortex docs

For each unique stage/function name from step 3, call `cortex-docs/xql_lookup`:

```
cortex-docs/xql_lookup(term="dedup", kind="stage", product="<product from step 1>")
cortex-docs/xql_lookup(term="arrayindexof", kind="function", product="xql")
```

Tactics:

- **Default `kind`** to `auto` only if you can't tell from context; the upstream's stage list (`alter`, `arrayexpand`, `bin`, `call`, `comp`, `config`, `dedup`, `fields`, `filter`, `sort`) gives correct inference for the canonical 10. Anything else is a function.
- **Narrow `product`** when the operator gave a product context. Default `xql` searches all products and is fine when no context is given, but `xsiam` / `xdr` / `agentix` / `cloud` returns more focused docs.
- **Run lookups in parallel** if your runtime supports it — the docs API tolerates concurrent reads, and 8-15 lookups serialised would noticeably stretch the response.

For each lookup, capture:

- `title` — the canonical name (often differs from the term you queried; e.g. `arrayindexof` → `Arrayindexof Function`)
- `summary_content` — the truncated docs body (≤2,200 chars)
- `source` — citation string for the response
- `reader_url` — let the operator click through to the full docs page if needed

If `cortex-docs/xql_lookup` returns `found: false`:

- Check `suggestions` for a typo correction (e.g. operator wrote `dedupe` → suggestion `dedup`)
- Fall back to `cortex-docs/search` with the bare term + product context
- If still nothing, note the gap in your response — don't invent syntax

### Step 5 — Author the query, citing per stage/function

Compose the XQL query using:

- The operator's KB examples as the **pattern prior** — match dataset names, field aliases, ordering conventions
- The cortex-docs lookups as the **syntax reference** — use exact stage/function syntax, argument order, and behavioral notes from the docs

### `xdr_data` field + value conventions (resolve BEFORE authoring)

The XQL *language* (stages/functions) is dataset-agnostic, but **field names and enum values are dataset-specific** — guessing them is the #1 cause of a first-attempt failure. Before authoring against a tenant dataset:

- **Enum-typed columns use the `ENUM.<VALUE>` literal, NOT a quoted string.** In `xdr_data`, `event_type` is an enum: write `filter event_type = ENUM.PROCESS` (live-confirmed members: `ENUM.PROCESS`, `ENUM.NETWORK`, `ENUM.FILE`, `ENUM.REGISTRY`, `ENUM.LOAD_IMAGE`, `ENUM.LOGIN_EVENT`). `event_type = "PROCESS"` (a string) silently matches nothing, and so does an enum member that doesn't exist — confirm the member before using it. **`event_sub_type`: you CAN filter on it, but you can NOT group by it.** `filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START` works (live-verified); but `comp ... by event_sub_type` FAILS with `validation_message: "The event_sub_type field cannot be queried…"`, so never use it as an aggregation key — and always pair an `event_sub_type` filter with its `event_type`. Other `*_raw` datasets often store plain strings — confirm per dataset.
- **Resolve exact field names from the schema, don't guess prefixes.** `xdr_data` distinguishes the *acting* process (`actor_process_*`) from the *target/affected* process (`action_process_*`) and the *causality* chain (`causality_actor_process_*`). Common fields: `actor_process_image_name`, `actor_process_command_line`, `action_process_image_name`, `action_process_image_command_line`, `action_remote_ip`, `action_local_ip`, `agent_hostname`, `actor_effective_username`. The `xql_examples_search` result's `dataset_fields` block and **`xsiam.datamodel_describe(dataset="…")`** are authoritative — prefer them over memory.
- **`xsiam.datamodel_describe` is the airtight discovery tool — use it on ANY unfamiliar dataset.** It returns `{method, field_count, fields}`: `method="datamodel"` gives the XDM-typed schema where that stage is licensed; otherwise it FALLS BACK to sampling real rows and returns the native column names actually present (`method="sampled"`). So it works on every tenant — you never have to guess a field. (`method="sampled"` only sees fields present in sampled data; if a known field is missing, raise `sample_rows` or widen the window.)
- **Cross-product: there are hundreds of datasets, not just `xdr_data`.** Run **`xsiam.get_datasets`** first to see what the tenant ingests — `xdr_data` (XDR endpoint telemetry), `cloud_audit_logs` (cloud control-plane), `host_firewall_events`, `endpoints`/`host_inventory` (asset state), `forensics_*` (DFIR artifacts: amcache, event_log, dns_cache, handles, browser history…), plus per-vendor `*_raw` datasets. Field families differ per product (the `actor_process_*`/`action_*`/`ENUM.*` conventions are `xdr_data`-specific) — so `get_datasets` → `datamodel_describe(<target>)` → author, for anything outside `xdr_data`.
- **Flat fields vs `xdm.*` datamodel paths.** A direct `dataset = xdr_data | filter …` query uses the **flat** field names above (`actor_process_image_name`, `action_remote_ip`, `event_type`). The dotted `xdm.<...>` paths (e.g. `xdm.auth.auth_method`) are the **datamodel** view — only valid in a `datamodel dataset = xdr_data | …` query. Do NOT put `xdm.*` paths in a plain `dataset =` query (they resolve to null). NOTE: the standalone `| datamodel` stage is not available on every tenant — `datamodel_describe` handles that for you via its sampling fallback.
- When unsure between two field names, run a 1-row probe (`dataset = X | fields <candidate> | limit 1`) before committing the full query.

### XQL syntax gotchas (the top first-shot failure causes — internalize these)

These were each verified against a live tenant; every one silently 400s or zero-results a query that *looks* right:

- **`bin` is a STANDALONE STAGE, not a function.** Bucket time with `| bin _time span = 5m` and then group by `_time` in `comp`. **Do NOT** write `alter x = bin(_time, 5m)` — that is `bad query syntax at 'bin'`. (`span` accepts `1m,5m,1h,1d`, etc.)
- **No infix arithmetic. No parentheses-grouped math.** `(a / b) * 100` is rejected. Use the function forms inside `alter`: `add(a,b)`, `subtract(a,b)`, `multiply(a,b)`, `divide(a,b)` — nest them: `alter pct = multiply(divide(part, total), 100)`. Wrap integer operands in `to_float(...)`/`to_number(...)` first when you need a fractional result (`divide` on integers truncates).
- **No SQL `OVER()` window clause.** Anything analytic — a grand total beside per-group rows, a running sum, ranking — uses the **`windowcomp`** stage, never `agg() over ()` inside `alter`. **`as <alias>` is the LAST clause — it comes AFTER `by` and `sort`, NOT right after the function.** `windowcomp sum(x) as t by host` 400s (`bad query syntax at 'by'`, live-verified); the correct form is `windowcomp sum(x) by host sort asc _time as t`. Verified forms:
  - global total beside every row: `| windowcomp sum(x) as grand_total`
  - partitioned running sum (ordered within the partition): `| windowcomp sum(x) by host sort asc _time as running`
  - rank within a group: `| windowcomp row_number() by host sort desc bytes as rnk`
  - **un-partitioned ordered window** (e.g. a global top-N rank) takes its order from a **PRECEDING `| sort`**, not an inline `sort` — `windowcomp row_number() sort desc x` is rejected; do `| sort desc x | windowcomp row_number() as rnk`.
  - **`row_number()` works; `rank()` 500-errors** ("unexpected error") — use `row_number()` for both row-numbering and ranking.
- **Comparison operators in `filter` are `=` (not `==`)**, `!=`, `<`, `>`, `<=`, `>=`, `contains`, `in (...)`, `~=` (regex). Chain with `and`/`or`/`not`.

### Working with JSON columns

A text column that holds a JSON string is passed **directly** to the `json_extract_*` functions — only wrap a *native* object/array field in `to_json_string()` first.

- `json_extract_scalar(col, "$.path")` → one scalar, **always returned as a STRING** (even for JSON numbers). For math/aggregation wrap it: `to_integer(json_extract_scalar(col,"$.risk"))`. Nested path = `"$.geo.country"`. Sugar form: `col -> geo.country` (dotted, unquoted).
- `json_extract_scalar_array(col, "$.tags")` → array of **unquoted** scalars. **Use this** when you will explode-then-filter/count (`filter`/`comp by` match correctly).
- `json_extract_array(col, "$.tags")` → array with each element **quote-wrapped** (`"admin"`). A downstream `filter arr = "admin"` then silently mismatches — the #1 JSON-array zero-result trap. Prefer `json_extract_scalar_array` for categorical work.
- `json_path_extract(col, "<jsonpath>")` → full JSONPath (`$..author`, filters, slices) for deep/wildcard paths `json_extract_scalar` can't express.
- `arrayexpand` needs a **native array**, never a JSON string. Explode recipe: `| alter tags = json_extract_scalar_array(payload, "$.tags") | arrayexpand tags | comp count() by tags`.
- **A column that IS itself a top-level JSON array** (e.g. `roles = ["admin","vpn"]`) uses path `"$"`: `json_extract_scalar_array(roles, "$")`. The `$.key` form is only for an array nested *under* a key.
- **JSON write path** (building JSON, not reading it): `object_create("k1", v1, "k2", v2)` builds an object and `object_merge(a, b)` merges two — but **every value argument must be string-coercible**, so wrap numerics: `object_create("host", host, "max_sev", to_string(max_sev))`. Serialize the result with `to_json_string(obj)` for a JSON-string column.

### Working with arrays + composite (delimited) fields

- `split(col, "|")` → array. Index with `arrayindex(arr, 0)` (0-based; **`arrayindex(arr, -1)` = last element** — use it when the split arity varies). `array_length(arr)`, `arraycreate(a,b,...)`, `arrayconcat`, `arraydistinct`, `arraymerge`, `arrayrange`.
- `arraystring(<array>, ",")` joins an **array** → string (first arg is an array, not a string — it is the inverse of `arrayexpand`).
- `arrayindexof(arr, "@element" = "login")` — the membership/position test **requires the `"@element"` literal**; `arrayindexof(arr, "login")` is wrong. Same `@element` convention in `arrayfilter`/`arraymap`.
- Composite-field-split pattern (most common real-world parse): `| alter parts = split(combo, "|") | alter user = arrayindex(parts,0), host = arrayindex(parts,1), cnt = to_number(arrayindex(parts,3)) | comp sum(cnt) by user, host`.
- Post-aggregation flattening: `comp values(action) as acts by user | alter acts_csv = arraystring(acts, ","), n = array_length(acts)` — `values()`/`list()` produce arrays that pair with `arraystring`/`array_length`. **`values()` returns DISTINCT values; `list()` returns ALL values (with duplicates)** — pick by whether you want a set or the full multiset.
- Array predicate/transform helpers take the `"@element"` form: `array_any(arr, "@element" = "admin")` (any match), `array_all(arr, "@element" != "")` (all match), `arrayfilter(arr, "@element" contains "x")`, `arraymap(arr, lowercase("@element"))`. `arraymerge(arraycreate(colA, colB))` merges two array columns into one. The `"@element"` predicate also accepts **`in (...)`** — `arrayfilter(roles, "@element" in ("admin","root","dba"))` keeps the listed values (live-verified).
- **Match an ADJACENT scalar column against an array** (e.g. "is each row's `required_role` present in its `roles` array?") with `array_any(roles, "@element" = required_role)` — the right side of `"@element" = …` can be another column, giving a per-row membership test (returns boolean; `filter … = false` finds the gaps).
- **Two-array intersection / overlap has NO single-call form, and the obvious nested-`@element` attempt is a SILENT BUG.** `arrayfilter(a, array_any(b, "@element" = "@element"))` returns **all of `a`** (not the overlap) — the inner `@element` shadows the outer, so `"@element" = "@element"` is a tautology that always passes. Correct idiom: **explode one array, then test the resulting SCALAR against the other array** — `| arrayexpand a | filter array_any(b, "@element" = a) | comp values(a) as shared by <key>`. After `arrayexpand`, `a` is a scalar column, so `array_any(b, "@element" = a)` correlates the two arrays correctly.

### Lookup datasets (operator-built reference tables)

- **Create then populate then query** — a lookup must exist before you write to it (writing to a non-existent dataset hangs). Create with `xsiam_create_dataset(dataset_name, dataset_schema={col: type}, dataset_type="lookup")` (types: `text | number | boolean | datetime`); populate with `xsiam_add_lookup_data(dataset_name, data=[{row}, {row}], key_fields=[...])` (`data` is an **array of row objects**; `key_fields` make it an upsert). Both are approval-gated writes.
- **Query a lookup exactly like an event dataset:** `dataset = <lookup_name> | ...`. Lookup **text columns are plain strings** — no `ENUM.*` literal (that is `xdr_data`-specific). Numbers stored as `number` type compare/aggregate directly.
### Joins (enriching across datasets) — the alias-scope gotcha

`| join (dataset = <other>) as <alias> <on-condition>` — but the `<alias>` is in scope **only inside the on-condition**. This is the single biggest join failure and the bundled `xql_doc.md` documents it WRONG (it shows `join1.agent_id` downstream — that 400s at query time):

- **In the on-condition**, use `alias.col` to name the joined dataset's key: `join (dataset = ioc_ip) as ioc ioc.indicator = action_remote_ip`.
- **Downstream (alter/comp/fields/filter), reference the joined dataset's other columns by their BARE name** — `threat`, `severity`, `tier` — NOT `ioc.threat` / `ioc.severity`. `alter sev = ioc.severity` fails with `unknown field ioc.severity`; `alter sev = severity` works.
- **Name collisions:** if both sides have a column of the same name (e.g. both have `host`), add `conflict_strategy = both` to the join and the joined side becomes `<col>_joined_<NN>`; or `alter`-rename one side before the join. Default keeps the inner (joined) side's value on a clash.
- **Unmatched rows after a left join:** `replacenull` targets the **bare** joined field — `| replacenull threat = "none"`, not `replacenull ioc.threat`.

```xql
dataset = xdr_data | filter event_type = ENUM.NETWORK and action_remote_ip != null
| join (dataset = gx_ioc_ip) as ioc ioc.indicator = action_remote_ip
| replacenull threat = "benign"
| comp count() as hits by action_remote_ip, threat, severity
| filter threat != "benign" | sort desc severity, desc hits
```

### Working with IP / CIDR fields

- `incidr` / `incidr6` are **dual-form**: an OPERATOR inside `filter` (`src_ip incidr "10.0.0.0/8"`) and a FUNCTION inside `alter` (`alter internal = incidr(src_ip, "10.0.0.0/8, 192.168.0.0/16")` — a single call takes a **comma-separated multi-CIDR string**, OR semantics).
- **The comma-OR multi-CIDR is a STRING-LITERAL feature only — a SILENT trap with columns.** `incidr(ip, allowed)` where `allowed` is a **column** holding a delimited list (`"10.0.0.5, 8.8.8.8"`) is NOT split: it silently returns **false** for every multi-value row (a column holding a *single* CIDR still matches). `incidr`'s CIDR arg also **cannot be `"@element"`** (`Expecting field/array, but received @element in the incidr function`). To test an IP against a **column-held** delimited CIDR/IP list, explode it so each element is a scalar single-CIDR field incidr accepts: `| alter arr = split(allowed, ", ") | arrayexpand arr | alter hit = incidr(ip, arr) | filter hit = true | comp count() by username, ip` (all live-verified).
- `incidrlist(ip, "1.1.1.1, 8.8.8.8")` takes a comma-separated **string** of IPs (flatten an array first with `arraystring(arr, ", ")`); returns true only when **all** listed IPs are in range.
- `is_ipv4` / `is_ipv6` / `is_known_private_ipv4` / `is_known_private_ipv6` return **false (not null)** for non-matches. To keep all rows with a classification column use them in `alter`; `filter is_ipv4(x) = true` will silently drop rows.
- `int_to_ip` / `ip_to_int` are **IPv4-only**; pair with `min()/max()` over the integer form to compute address-range bounds, then `int_to_ip` back.

### Free-text / regex parsing

- `regextract(field, "<re2-with-ONE-group>")` returns an **array** of the (single) capture group's matches — RE2 allows only ONE capture group per call. Grab the first: `arrayindex(regextract(line, "user=(\\w+)"), 0)`. Run one `regextract` per field you need.
- **`regexcapture()` does NOT work in dataset queries** — it is parsing-rules-only and at query time silently returns `{"dummy": null}` (no error), so a PASS/result-count check won't catch it. Never use it for query-time multi-group parse; use multiple `regextract` calls.
- Normalize case-variant values with `lowercase(...)` **before** `comp ... by <field>` so `Alice`/`alice` collapse to one group. `wildcard_match(field, "*admin*")`, `replace`/`replex`, `string_count` round out free-text work.

### Geo-enrichment (iploc stage)

- `| iploc <ip-field>` enriches each row with geo columns from the IP: `loc_country`, `loc_city`, `loc_continent`, `loc_region`, `loc_asn`, `loc_asn_org`, `loc_latlon`. Rename inline: `| iploc dst_ip loc_country as country, loc_city as city`. Suffix-all form: `| iploc dst_ip suffix = _geo` → `loc_country_geo`, etc.
- `loc_latlon` is a single comma-separated `"lat,lon"` **string** — split it for numeric use: `alter lat = arrayindex(split(loc_latlon, ","), 0), lon = arrayindex(split(loc_latlon, ","), 1)`.
- **`iploc` enriches IPv4 only.** For a column that may hold IPv6, `filter is_ipv4(<ip-field>) = true` first, or those rows get null geo.

### Unions (merging datasets)

- `| union <dataset>` or `| union (<dataset> | <stages>)` appends rows from another source. **Both sides must project matching column names** for a downstream `comp`/`dedup` to align — `fields`/`alter`-rename each side to a common schema *before* the union, then aggregate. `coalesce(a, b, ...)` picks the first non-null when filling a unified column (cast an IP field with `to_string()` if it must share a text column).

### Other stage notes

- `top N <field> by <group> top_count as cnt, top_percent as pct` is the `top` stage form (N first, then `by`, then the count/percent aliases) — e.g. `| top 10 bytes_out by host top_count as cnt`.
- `to_float` / `to_number` accept a **numeric or aggregated field** too (not only strings) — wrap the operands of `divide` to get a real ratio (`divide(to_float(out), to_float(in))`); raw integer `divide` truncates.

### Verified function/stage vocabulary (and the names that SILENTLY 500)

All confirmed live on a real XSIAM tenant. XQL reports an invalid function name as a **generic HTTP 500 (`"An unexpected error occurred"`) with no hint about which token is wrong**, and one bad name poisons the whole query — so reaching for a Splunk/KQL name you *think* exists is the single most common first-shot failure. Use the confirmed names:

- **`comp` aggregations (confirmed):** `count()`, `count_distinct(x)`, `sum`, `avg`, `min`, `max`, `var(x)`, `values(x)` (distinct set), `earliest(x)`/`latest(x)` (min/max of a time field).
- **`windowcomp` functions (confirmed):** `row_number()`, `lag(x)`, `avg(x)`, `sum(x)`, `count()` — partitioned by `by P sort D F`, alias `as a` LAST.
- **Conditionals/null (confirmed):** `if(c, then, else)` (nest for multi-branch), `coalesce(x, default)`.
- **Strings (confirmed):** `uppercase(x)`, `lowercase(x)`, `replace(field, "old", "new")`.
- **Time (confirmed):** `timestamp_diff(current_time(), _time, "SECOND")`, `format_timestamp("%Y-%m-%d %H:%M:%S", _time)`, `current_time()`.
- **Stages (confirmed):** `dedup <field>` (keeps the FIRST row per distinct value — precede with `sort` to choose which survives), `join type = left|inner (subquery) as r r.k = k`.

**Names that DO NOT exist in XQL → silent 500. Substitute:**

| You might reach for | Use instead |
|---|---|
| `dcount(x)` | `count_distinct(x)` |
| `stddev(x)` / `stdev` / `std` | `var(x)` then `\| alter sd = sqrt(v)` (no window stddev exists) |
| `percentile(x, n)` / `approx_percentile` | no equivalent — rank with `windowcomp row_number()` over a `sort`ed stream |
| `case(c1, a, c2, b, …)` | nested `if(c1, a, if(c2, b, …))` |
| `lead(x)` (next row) | only `lag(x)` (prior row) exists |
| `windowcomp var/stddev` | not window-aggregable → use per-group deviation: `windowcomp avg(x) by g as ga \| alter dev = subtract(x, ga)` |

**Anti-join gotcha:** after `join type = left … as r`, you CANNOT keep non-matches with `filter r.<col> = null` — the joined column isn't exposed as `r.<col>` for unmatched rows (`unknown field r.<col>`). For "rows with no match", put a presence flag inside the subquery or aggregate-and-compare instead.

Output shape:

````markdown
**Query:**

```xql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and actor_process_image_name != null
| bin _time span = 5m
| comp count() as execs by actor_process_image_name, _time
| filter execs > 50
| sort desc execs
```

**Authored from:**

- 5 similar queries in the org KB (paths: ...).
- Cortex docs lookups for: `filter`, `alter`, `bin`, `comp`, `sort`.
  Source: docs-cortex.paloaltonetworks.com - Filter Stage (Cortex XSIAM Documentation), Alter Stage (Cortex XSIAM Documentation), bin Function (Cortex XSIAM Documentation), Comp Stage (Cortex XSIAM Documentation), Sort Stage (Cortex XSIAM Documentation).

**Notes:**

- `bin` is applied as a standalone stage (`| bin _time span = 5m`), which rewrites `_time` to the bucket start; `comp ... by _time` then aggregates per bucket. (`bin` is NOT a function — `alter x = bin(...)` is a syntax error.)
- Counts > 50 in 5 minutes is the threshold the example queries used; tune via the `filter logins > N` clause.
````

Always cite the docs as `docs-cortex.paloaltonetworks.com - <Title> (<Publication>)` — that's the source string the connector returns.

### Step 5.5 — Verify before returning (catch syntax AND silent-wrong-results)

**When an XSIAM instance is connected, do NOT return an unverified query.** A query that is syntactically valid can still be *silently wrong* — it returns HTTP 200 with plausible-looking but incorrect rows (live-observed examples: `incidr(ip, <column-with-comma-list>)` returns `false` for every row; a nested-`@element` array intersection returns the whole array instead of the overlap). "Does it parse" and "does it return rows" both pass these. The only general defense is to **run it on a bounded window and check the actual values**.

Call **`xsiam_xql_verify(query=<the authored query>, lookback_hours=<narrow, e.g. 0.5–2>)`** — it runs the query cheaply (cost is driven by the window, not the sample) and returns a verdict: `parses`, `columns`, `row_count`, a `sample` of rows, `compute_units_used`, and `warnings`. Then:

- **`parses = false`** → it's a syntax error. Fix the XQL per `error` and re-verify; do not return a broken query.
- **`verified = true` but check the SAMPLE** → confirm the `columns` you expected are present and the sample VALUES are what the question asks for (e.g. an "external IPs" hunt should show external IPs, not internal ones). If the values are wrong, the query is silently wrong — fix the logic (re-read the array/incidr/windowcomp gotchas above) and re-verify.
- **`row_count = 0` (a warning)** → either a true negative (rare event in the window) or a wrong field/filter/enum. Widen `lookback_hours`, relax the filter, or confirm field names with `xsiam_datamodel_describe` before concluding "nothing found".
- **Surface the cost** → include `compute_units_used` in your answer so the operator sees what the (real) hunt will cost; pre-flight a wide hunt with `xsiam_get_xql_quota` if the verification window's cost extrapolates past the daily budget.

If no XSIAM instance is configured, skip this step (author-only) and tell the operator the query is **unverified** — they should run it once on a narrow window before trusting it. Reserve verification skips for genuinely free lookup-dataset queries only when an instance is absent.

### Step 5.6 — Budget the real run from the verified cost (CU-aware planning)

The verify in Step 5.5 already gives you a **measured price tag** on a narrow window — use it to plan the real hunt instead of running wide and hoping. (Deep dive: the `cortex_compute_unit_forecasting` skill.)

1. **Extrapolate.** Verify ran on `lookback_hours = W_v` and reported `compute_units_used = C_v`. A hot `xdr_data` scan's cost scales ~linearly with the window, so the full hunt over `W_t` hours costs roughly **`C_v × (W_t / W_v)`**. Example: verify on 0.5 h cost 0.02 CU → a 72 h hunt ≈ `0.02 × 144 = ~2.9 CU`.
2. **Check headroom.** Call `xsiam_get_xql_quota` and read `daily_used_quota` against the daily budget. If the extrapolated cost would exceed remaining headroom, do NOT run the wide query blind.
3. **Narrow or warn — in this order:**
   - **Reduce the scan** (cheapest lever, since cost = data scanned, not query complexity): tighten `lookback_hours`, push filters as early as possible (filter before comp/join), target a lookup dataset instead of a wide `xdr_data` scan, or select fewer `fields`.
   - If the operator needs the wide window anyway, **warn with the number**: *"This hunt over 72 h is estimated at ~2.9 CU (verified 0.02 CU on 30 min); you have ~X CU left today. Run it, or should I narrow the window?"* — let them decide before spending the budget.
4. **Self-calibrate.** The extrapolation is an estimate; after the real run, compare its actual `compute_units_used` to your prediction and adjust the multiplier for the next hunt in the session (cold-storage scans and heavy joins cost more than the linear model predicts).

This keeps Guardian inside the ~1 CU/day budget on a metered tenant while still letting the operator authorize an expensive hunt with eyes open. **Never silently run a hunt you've estimated could exhaust the daily quota.**

### Step 6 — Offer to broaden if the result feels under-grounded

If only 0-1 examples came back from step 2, tell the operator and offer a `cortex-docs/deep_research` follow-up for the broader topic:

> "I had no similar queries in your KB to anchor this against, so the result is leaning on Cortex docs alone. Want me to also run a `deep_research` against `<topic>` to surface multi-topic context? It takes 1-3 minutes."

Reserve `deep_research` for explicit operator opt-in; don't fire it as part of the default flow.

## Incident-investigation use (Guardian)

XQL authoring isn't only ad-hoc — during an investigation, use it to **scope an incident**. Given a case's indicators (host, user, IP, hash, time window):

1. Pull the case context (e.g. `xsoar_get_incident` / the investigation tools) to get the indicators + the incident's time span.
2. `xql_examples_search(intent=...)` for the relevant hunt pattern — e.g. "lateral movement from host", "process tree for hash", "outbound connections by host" — to get an idiomatic starting query plus the dataset's field list.
3. Bind the case's indicators into the query's `filter` clause and narrow the time window to the incident's span.
4. Confirm any unfamiliar stage/function with `cortex-docs/xql_lookup`.
5. Run it with `xsiam_run_xql_query` to enumerate affected assets / sessions, then feed the findings back into the case (notes, evidence, related indicators).

This turns the example KB + live docs into a **blast-radius / threat-hunting loop anchored to the incident under investigation** — the IR counterpart to ad-hoc query authoring. The `xql-examples` KB ships an ATT&CK-tagged `threat-hunting` set for exactly these pivots (search by technique, e.g. "T1021 RDP lateral movement").

## Failure handling

| Symptom | Likely cause | Fix |
|---|---|---|
| `cortex-docs/xql_lookup` returns `ok: false, error: "cortex-docs API call failed"` | Docs API unreachable (network blip, GitHub Actions runner egress, customer firewall) | Retry once. If still failing, tell the operator "Cortex docs are temporarily unreachable; falling back to operator-KB-only" and proceed with reduced confidence |
| `found: false` even with correct spelling | Term may be product-specific. Re-call with explicit `product` (e.g. `xsiam` instead of default `xql`) | Cortex publications occasionally hide a function under one product but not others |
| Only release-notes pages come back | The lookup ranking subtracts heavy points from release notes, so this is rare. If it happens, search with `cortex-docs/search` + the `product` scope; release notes show up because the search hit no canonical reference page | Tell the operator the canonical reference page is missing; cite the release note with that caveat |
| No KB examples + docs say `found: false` for everything | The operator's question is outside Cortex's documented surface (private internal field, custom playbook, etc.) | Don't invent. Tell the operator and ask for example syntax from their environment |
| `run_xql_query` returns HTTP 500 `reached max allowed amount of parallel running queries` or `Connection reset by peer` | Tenant-side concurrency throttle / transient infra — NOT a query syntax error | Retry once after a short pause; serialize rather than fan out many simultaneous queries. Do not rewrite the query |
| `run_xql_query` returns HTTP 500 `query usage exceeded max daily quota` / `error_type: QUOTA_EXCEEDED` (`used_quota` = `max_quota`) | Tenant **daily** XQL scan-quota is exhausted — a hard wall, NOT a query error and it does NOT reset within the session | Stop running queries; the quota resets at UTC midnight. Do not retry (it will keep 500-ing) and do not rewrite the query. Lookup-dataset queries scan far less than `xdr_data` scans, so prefer narrow time windows + `limit` to conserve quota |
| `xsiam_get_datasets` returns `{"error": "xsiam instance has no papiAuthHeader (API key) configured"}` or similar XSIAM connector error | The operator hasn't installed/configured an XSIAM provider, OR the configured instance is missing the API key | **Do NOT retry via other XSIAM tools** (they will all fail the same way). Ask the operator directly for the dataset name (e.g. `cisco_esa_raw`, `xdr_data`) and proceed with `xql_examples_search` + cortex-docs/xql_lookup for syntax. The skill is designed to work end-to-end without XSIAM access — the bundled `xql-examples` KB and cortex-docs cover the authoring path. Only mention XSIAM tools as a side note: *"If you'd like the agent to discover datasets automatically, configure an XSIAM instance in /connectors."* |

## Operator-visible surfaces

After this skill runs, the agent's chat response should include:

- The composed query in a code fence
- One short sentence per cited docs source (e.g. "filter from Cortex XSIAM Documentation")
- A 1-2 line "notes" block flagging anything non-obvious (window size choice, threshold defaults, alternatives the agent considered but didn't pick)

The `cortex-docs` connector's full tool surface is also visible in `/observability/connectors` — operators auditing what the agent called can see each `cortex_search` and `cortex_xql_lookup` invocation in the live tool-call log.

## Adapting per deployment

Per-product narrowing matters. Different Cortex products have different idiomatic XQL — XSIAM datasets are wider than XDR's; AgentiX adds extension functions some other products don't expose. When the operator's product context is clear, **always** narrow `product` on the `cortex-docs/xql_lookup` calls. The cross-product `xql` default is correct only when context is absent.

For an operator who runs multiple Cortex products (XDR + XSIAM + Cloud), keep two fallback strategies in mind:

- **Same query intent, multiple products** — run lookups against each product's scope and present a comparison table
- **Org idioms cross products** — the operator's KB examples are the tiebreaker; the docs say "either form is valid", the org KB picks one

## Skill bodies elsewhere

This skill complements but doesn't replace the broader `cortex-deep-search` workflow (also in this connector via `cortex-docs/deep_research`). Use this skill for query authoring; use deep-research for whitepapers / partner briefings / migration guides.
