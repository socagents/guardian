---
name: cortex_compute_unit_forecasting
displayName: Cortex Compute-Unit (XQL quota) forecasting
category: foundation
description: 'Explain, measure, and forecast Cortex XSIAM Compute-Unit (CU) consumption so XQL queries stay inside the tenant''s daily quota. Covers the full CU accounting model (free annual bank, purchased add-on, daily limit options, 00:00-UTC reset, no rollover), what consumes CU (XQL API / Cold Storage / Notebooks / BQ), how to READ actuals (the xsiam_get_xql_quota tool for headroom, and the compute_units_used + remaining_quota_cu fields now returned by xsiam_run_xql_query), an empirical cost model calibrated against thousands of real queries (cost scales with data scanned, not query complexity), how to forecast how many queries a daily budget allows, the levers to cut cost, and how to handle the QUOTA_EXCEEDED daily-cap error. Triggers when the operator asks how CU/quota is consumed, why a query was rejected, how to budget or forecast XQL usage, how much a query will cost, or how to reduce compute-unit spend.'
icon: savings
source: platform
loadingMode: on-demand
locked: false
attack: []
---

# Cortex Compute-Unit (XQL quota) forecasting

Cortex XSIAM meters data-lake queries in **Compute Units (CU)**. Every XQL API
query draws down a **daily CU limit**; when the day's CUs are spent, further
queries are **rejected** (`QUOTA_EXCEEDED`) until the counter resets. This skill
lets you explain consumption, read the live quota, estimate a query's cost
*before* running it, forecast how many queries a budget allows, and cut spend.

The hard rule that makes all of this matter: **CU cost is driven by the volume
of data scanned, not by how clever the query is.** A 20-stage query over a tiny
lookup table is ~free; a one-line `dataset = xdr_data | sort desc _time` over a
30-day window is expensive.

## The accounting model (from the Cortex XSIAM 3.x docs)

| Element | Meaning |
|---|---|
| **Free annual quota** | CU bank allocated by **license size**, per license year. (`license_quota`) |
| **Compute Unit add-on** | Optional purchase: **+1 CU/day for a year** on top of the free annual quota (annual basis; **minimum 50 CU**). (`additional_purchased_quota`) |
| **Eval/trial quota** | 30-day trial = **1/12 of the annual quota**, for XQL API + Cold Storage queries. (`eval_quota`) |
| **No rollover** | Unused balance **does not** carry to the next licensing period. |
| **Daily limit** | Configurable cap on CU spent per day (Settings → Configurations → Data Management → Compute Unit Usage; needs *Edit permissions for Public APIs*). Options: **Divide annual evenly** (annual ÷ 365), **1% of annual**, **No limit**, or **Custom** (integer ≥ annual ÷ 365). **Default = annual ÷ 365.** |
| **Reset cadence** | The daily counter resets at **00:00 UTC**. |
| **MSSP** | For Managed-Security tenants, the figures **sum parent + child** tenant usage. |

**What consumes CU** (each counts against the daily limit + annual quota):
`XQL API queries` (timestamped at execution), `Cold Storage queries`,
`Notebooks` (timestamped at *charge* time, not execution), and `BQ queries`.
The UI also surfaces an **Agents & LLM consumption** view for visibility — that
panel is a UI feature (it is *not* described on the 3.x Compute-units-usage doc
page), so do not assert from docs whether it counts against the daily limit;
state it as "shown in the UI for visibility" only.

## Read the ACTUALS (don't guess when you can measure)

Two tools surface live CU data — neither requires running the query you're worried about:

- **`xsiam_get_xql_quota`** — read-only, **consumes no CU**. Returns the live picture:
  - `license_quota`, `additional_purchased_quota`, `eval_quota` — the annual bank
  - `used_quota` — cumulative CU spent this license year
  - `remaining_annual_cu` — `(license + purchased + eval) − used` (computed by the tool)
  - `daily_used_quota` — CU spent **today** (resets 00:00 UTC)
  - `total_daily_running_queries` — today's query **count** (volume, not CU)
  - `total_daily_concurrent_rejected_queries` — queries rejected (quota/concurrency)
  - `current_concurrent_active_queries_count`, `max_daily_concurrent_active_query_count`
  - **The daily LIMIT is not in the API** (it's a UI setting) — compare `daily_used_quota`
    against the operator's configured daily limit to compute headroom.
- **`xsiam_run_xql_query`** now returns, alongside the rows:
  - `compute_units_used` — the CU this query actually cost
  - `remaining_quota_cu` — CU remaining after it
  - `number_of_results`

**Workflow:** before a wide blast-radius hunt, call `xsiam_get_xql_quota` to confirm
headroom; after each query, read `compute_units_used` to learn the real cost and
refine your estimate for the next one.

## The empirical cost model (calibrated on thousands of real queries)

Costs below are from a large live sample; treat them as **order-of-magnitude
anchors**, then correct with the actual `compute_units_used` you observe.

| Query shape | Typical CU | Why |
|---|---|---|
| Lookup-dataset query (small operator table) | **~0.0003** (often 0.0) | tiny dataset → almost nothing scanned |
| `xdr_data` scan, narrow window + early `filter` | **~0.005** | bounded rows scanned |
| `xdr_data` / `datamodel` scan, wide window | **0.1 – 0.35** | many rows scanned |
| `windowcomp` / multi-stage over a scan | **~0.003 – 0.03** | follows the underlying scan |
| `iploc` (per-row geo enrichment) | **0.1 – 0.4** | heavy per-row work; one of the priciest functions |
| `config timeframe = 30d` over a native dataset | **~0.3** | window dominates the scan |
| `preset = metrics_view` / wide aggregate presets | **1 – 3+** | scans huge spans — **can exceed a whole day's budget in one query** |

**The drivers, in priority order:**
1. **Time window** — cost scales ~linearly with `config timeframe` / `lookback_hours`. A 30-day window costs ~30× a 1-day window over the same data.
2. **Dataset size** — lookups are ~free; `xdr_data` and native vendor datasets are where CU goes.
3. **Filter selectivity** — an early `filter` prunes scanned rows and cost.
4. **Per-row functions** (`iploc`, heavy enrichment) and **wide presets** (`metrics_view`) multiply cost.
5. **`| limit` does NOT reduce cost** — it caps *output*, not the *scan*. Narrow the window/filter instead.

### Two cost regimes — hot (calibrate) vs cold (analytical)

The anchors above are **hot/standard** XQL (hot-retention data). The two regimes are estimated differently:

- **Hot / standard XQL API queries — NO published CU-per-GB constant.** Palo Alto documents cost only as *"timeframe, complexity, and number of API response results."* So the only reliable hot estimate is **calibration**: run one representative query, read its `compute_units_used` (the API's `query_cost`, a fractional CU), then multiply by how often you'll run it. The table above is the calibration starting point; replace it with your own measured numbers. (PA's own samples: a 3-result query ≈ 0.0016 CU; a 1,000,000-result streamed query ≈ 0.0117 CU — results matter, sub-linearly.)
- **Cold Storage queries — analytical: documented at 1 CU per 35 GB queried.** Two rules dominate cold cost:
  - the queried time window is **rounded UP to whole days** — querying any slice of a day bills that *whole day* of the dataset; and
  - re-queries on the **same range within a 7-day "rewarm" cache are FREE**.

  So `CU_cold ≈ ceil_to_days(window) × (GB/day of the queried dataset) ÷ 35`, charged once per range per 7-day window. Cold is where long-retention/compliance/retrospective work lives, and where a single query can cost hundreds of CU — estimate it *before* you run it.

## Forecasting against a daily budget

```
queries_per_day ≈ daily_limit_CU / estimated_CU_per_query
```

Estimate `estimated_CU_per_query` from the table above (dataset class × window),
then divide. Example reference points for a **1 CU/day** limit:

| Mostly running… | ~Queries/day before exhaustion |
|---|---|
| Lookup queries (~0.0003) | ~3,000+ |
| Narrow `xdr_data` scans (~0.005) | ~80–190 |
| `iploc` enrichment (~0.1–0.4) | ~3–10 |
| Wide `metrics_view` (1–3+) | **<1** (a single query can detonate the day) |

For a wide hunt, **pre-flight**: estimate cost, call `xsiam_get_xql_quota`, and if
`estimated_cost > remaining_daily`, narrow the window or split the hunt across days.

## Best practices to save Compute Units

A playbook of CU-saving practices, grouped by where they apply. Each was verified
against the cost model above; **#1 (window) and #2 (filter) dominate** — apply them
to every query before reaching for the rest.

### A. Author cheaper queries (reduce the scan)

1. **Shrink the time window to the actual question — the biggest lever.** Hot cost
   scales ~linearly with the window; set `lookback_hours` / `config timeframe` to the
   real incident span, not a habitual default (`lookback_hours=2` for a fresh alert,
   not 72). For **cold**, the window rounds up to whole days — don't straddle a UTC
   midnight you don't need (23:30→00:30 bills *two* whole days), and query one day at
   a time when one day is all you need.
2. **Filter early, most-selective-first, on real fields.** Lead the pipe with the
   tightest predicate — `dataset = X | filter src_ip = "1.2.3.4" | ...` — so fewer
   rows reach later stages. Bind the incident's concrete indicators into the `filter`;
   don't pull a window of everything and post-filter in the agent. **`| limit` is NOT
   a cost lever** — it caps output, not the scan.
3. **Confirm field names first with `xsiam_datamodel_describe`.** Filtering on a
   misspelled/non-existent field silently scans wide (or errors). Resolve the dataset's
   real, filterable columns before authoring the `filter`.
4. **Query the dataset that lets you filter tightest.** A specific typed dataset
   (e.g. `corelight_http_raw`) helps *when* it avoids scanning unrelated telemetry and
   exposes selective fields — the driver is **window + filter selectivity**, not the
   dataset name itself. Reach for `xdr_data` only when the hunt genuinely spans sources.
5. **Aggregate server-side — return a rollup, not thousands of rows.** End hunts with
   `| comp count() by agent_hostname` (or `comp values(...)`) so the API returns a few
   rows. Hot cost is partly driven by the number of results returned, and the connector
   pulls up to 1000 rows per read.
6. **Answer multiple questions in ONE pass.** Hot queries have no free re-run, so use
   one multi-aggregation `comp` (`comp count() as c, values(user) as users,
   values(dst_ip) as dsts by agent_hostname`) instead of three separate queries over
   the same window.
7. **Don't enrich the firehose.** `iploc`/geo per-row enrichment is 0.1–0.4 CU and wide
   presets (`preset = metrics_view`) are 1–3+ CU. Filter to a small set *first*, then
   enrich the survivors — or push repeated enrichment into a **lookup dataset**
   (reads ≈0.0003 CU) and `join`, instead of recomputing it every query.
8. **Project only needed fields early** (`| fields host, action_remote_ip, _time`
   right after the filter). This is hygiene that trims response payload/complexity —
   not a documented per-column charge, but it keeps result sets lean.

### B. Route hot vs cold deliberately

9. **Default to hot; reach into cold only past hot retention.** Cold is metered
   (1 CU / 35 GB queried, whole-day-rounded); a narrow filtered hot scan can be
   near-free. Keep recent work on hot datasets.
10. **For a deep cold dive, exploit the free 7-day rewarm.** The first query on a cold
    range pays the CU; re-queries on the **same range** are free for 7 days. Plan the
    investigation as a one-week sprint on a *fixed* range — iterate filters/projection
    over it rather than nudging the window each attempt.
11. **Narrow on hot first, then cold-sweep filtered.** Use cheap hot queries to pin the
    key indicators/datasets, then run the (expensive) cold sweep scoped to just those —
    far fewer GB billed. Target the narrowest cold dataset; avoid wide presets on cold.

### C. Operate within the budget

12. **Calibrate before you scale.** There's no published CU-per-GB constant for hot —
    run a tiny probe (small window / tight filter), read `compute_units_used` from
    `xsiam_run_xql_query`, then extrapolate before going wide or scheduling a query to
    run ×daily.
13. **Pre-flight wide hunts with `xsiam_get_xql_quota`** (read-only, costs 0 CU). If the
    estimated cost exceeds `remaining` headroom for the day, narrow the window or defer.
14. **Skip XQL entirely when the data is already materialized.** For host/user/alert
    facts already on the object, use the direct REST tools (`xsiam_incidents_get_extra_data`,
    `xsiam_alerts_list`, `xsiam_endpoints_get`) — the cheapest query is the one you never run.
15. **Respect the concurrency cap (~5).** Serialize/space automation; excess queries are
    rejected (`total_daily_concurrent_rejected_queries`). Don't blindly re-fire a rejected
    query, and remember **parallel PAPI keys don't buy more budget** — all keys share the
    one tenant daily limit.
16. **Tune the limit + spread the load.** Set the daily limit near your average; raise it
    temporarily during an incident and restore it after; consider the add-on for sustained
    need. The limit resets 00:00 UTC with **no rollover**, so spread heavy/cold work across
    days rather than burning a day in one batch.
17. **Monitor + self-throttle.** Track `compute_units_used` per query and the Compute Unit
    Usage page; for automated loops, set an internal threshold (e.g. stop at X% of the
    daily limit via `xsiam_get_xql_quota`) so the loop self-throttles before exhaustion.
18. **Target the right instance.** With 2+ enabled XSIAM instances, pass the `instance`
    selector — a query fired at the wrong tenant is pure wasted CU on the wrong data.

## Handling the daily-cap error

When the daily CU limit is spent, `xsiam_run_xql_query` returns a `QUOTA_EXCEEDED`
error (the connector surfaces it with a hint). What to tell the operator:
- The **daily** limit is reached; it **resets at 00:00 UTC** — not a query bug.
- Show current state with `xsiam_get_xql_quota` (`daily_used_quota`, `remaining_annual_cu`).
- The operator can **raise the daily limit** in the UI for an active investigation
  (Settings → Configurations → Data Management → Compute Unit Usage — *Custom* /
  *No limit*), or buy the **Compute Unit add-on** (+1 CU/day/year, min 50 CU).
- The daily limit and the add-on are **UI-only** — there is no public API to set the
  limit or enable the add-on; `xsiam_get_xql_quota` is read-only.

## Worked customer estimation examples

Each example follows the same method: **profile → workload → estimate → verdict →
recommendation.** Hot numbers are calibration anchors — always re-measure with
`compute_units_used` on the customer's own tenant; cold numbers are computed from the
documented **35 GB/CU** rule. (`daily limit` defaults to `annual ÷ 365` unless the
customer set a Custom/1%/No-limit value.)

### Example 1 — IR investigation (hot data, bursty)

- **Profile:** mid-size SOC. License **1,825 annual CU** → default daily limit **5 CU**. Hot retention 30 days. Runs blast-radius hunts during incident response via the API.
- **Workload:** ~8 incidents/day × ~6 hunts each, 24–72h windows, filtered to the incident's indicators (host/user/IP). Calibrated: a filtered 72h `xdr_data` hunt ≈ **0.02 CU**. Plus ~50 ad-hoc analyst queries/day ≈ 0.005 CU.
- **Estimate:** `8 × 6 × 0.02 = 0.96` + `50 × 0.005 = 0.25` ≈ **1.2 CU/day** (≈24% of 5). Annual ≈ 440 of 1,825.
- **Verdict:** comfortable day-to-day. **Spike risk:** a major-breach day with 40 deep hunts over 30-day windows (~0.3 CU each) = ~12 CU → **exceeds the 5 CU limit and will reject mid-investigation**.
- **Recommendation:** for a major incident, **raise the daily limit** (UI → Custom/No-limit) for the duration, then restore it. Keep routine hunts on the narrowest window that answers the question.

### Example 2 — Threat hunting via the API (hot data, scheduled)

- **Profile:** enterprise. License **10,950 annual CU** → default daily **30 CU**. Hot retention 90 days. Runs a programmatic hunt pack (cron / autonomous loop) over the API.
- **Workload:** daily pack of **25 hunts** over 24h windows, avg ≈ **0.04 CU** (some `windowcomp`/agg) = 1 CU/day; plus a **weekly** deep pack of 25 hunts over 30-day windows (~0.3 CU each) = 7.5 CU on that day.
- **Estimate:** `1 + 7.5/7` ≈ **2.1 CU/day** avg (≈7% of 30).
- **Verdict:** tiny against budget — but **one careless wide hunt detonates it**: a 90-day `metrics_view`-style aggregate ≈ 3+ CU each; 25 of those = 75 CU > 30/day → rejected. Also the API caps **max 5 concurrent queries**, so a 25-hunt pack must serialize.
- **Recommendation:** keep scheduled hunts on narrow windows; **calibrate each new hunt's `query_cost` once before scheduling it ×daily**; reserve wide retrospective sweeps for explicit, budgeted runs; serialize/space the pack to respect the concurrency cap.

### Example 3 — Compliance reporting (Cold Storage, periodic, long window)

- **Profile:** regulated customer. License **3,650 annual CU** → default daily **10 CU**. Hot 30 days; **Cold Storage retention 12 months**. Auth/audit dataset ≈ **40 GB/day**.
- **Workload:** quarterly access-review report = query **90 days** of cold auth/audit data.
- **Estimate (analytical):** `90 days × 40 GB/day = 3,600 GB`; `3,600 ÷ 35` ≈ **103 CU** for that one query. Annual = 4 × 103 ≈ **412 CU** of 3,650 (fine yearly) — but the **daily spike (103 ≫ 10)** is the binding constraint.
- **Verdict:** the report **will reject** at the default 10 CU/day limit.
- **Recommendation:** (a) **raise the daily limit** the day you run it (or split the window across days); (b) the window **rounds up to whole days**, so a 90-day report bills 90 days regardless of the hour you pick; (c) **iterate on the free 7-day rewarm** — the first run pays ~103 CU, refinements on the same range within 7 days are free; (d) scope to the specific dataset + needed columns to shrink the GB scanned.

### Example 4 — SOC continuous monitoring / automation (hot, high-frequency, tiny)

- **Profile:** **1,825 annual CU** → daily **5 CU**. Hot 30 days. Heavy automation: enrichment lookups, dashboard refreshes, playbook XQL steps over the API.
- **Workload:** ~**3,000 small queries/day** (single-indicator filters, short windows, lookups) ≈ 0.0005 CU each; plus ~200 medium hunts ≈ 0.01 CU each.
- **Estimate:** `3,000 × 0.0005 = 1.5` + `200 × 0.01 = 2.0` ≈ **3.5 CU/day** (70% of 5).
- **Verdict:** fits, but **tight** — the cost here is **volume × tiny unit cost**, not any single expensive query. Bursts also hit the **5-concurrent cap**.
- **Recommendation:** watch the query **count**, not just per-query cost; move reference data into **lookup datasets** (≈free); trim dashboard-refresh frequency; serialize automation; raise the limit if the automation footprint grows.

### Example 5 — DFIR retrospective / breach scoping (Cold Storage, deep one-off)

- **Profile:** IR-retainer engagement. Customer license **7,300 annual CU** → daily **20 CU**. Hot 30 days; **Cold 6 months**. A breach with **~4-month dwell time** must be scoped across cold data. Relevant datasets (network + process + auth) ≈ **120 GB/day combined**.
- **Workload:** scope the breach across **120 days** of cold storage.
- **Estimate (analytical):** `120 days × 120 GB/day = 14,400 GB`; `14,400 ÷ 35` ≈ **411 CU** for a full-scope sweep (≫ 20/day).
- **Verdict:** a single full cold sweep dwarfs the daily limit — must be planned, not run blind.
- **Recommendation:** (a) **narrow on hot data first** (cheap) to pin the key indicators/datasets, *then* run the cold sweep filtered to those — far fewer GB; (b) **raise the limit / buy the add-on** for the engagement, or spread the sweep across days; (c) exploit the **free 7-day rewarm**: pay the CU once on the 4-month range, then run all iterative pivots on that rewarmed window **free for a week** — plan the deep-dive as a one-week sprint; (d) remember the **whole-day rounding** (120 days billed as 120 whole days).

## Notes / caveats

- There is **no public API** for the per-query usage *list* (the UI "Compute Unit
  Usage" table, exportable as TSV). To capture per-query cost programmatically, read
  `compute_units_used` from each `xsiam_run_xql_query` response, or aggregate from
  `xsiam_get_xql_quota`.
- CU is attributed **per PAPI (API) key** in the usage table — multiple keys on one
  tenant all draw from the same tenant daily limit.
- `used_quota` is **cumulative for the license year**; `daily_used_quota` is the one
  that resets daily. Don't confuse the two when explaining "remaining".
