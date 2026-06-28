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

## Levers to cut CU (apply in this order)

1. **Shrink the time window** — set `lookback_hours` / `config timeframe` to the
   minimum that answers the question. Biggest lever by far.
2. **Filter early** — put the most selective `filter` first so fewer rows are scanned.
3. **Prefer lookup datasets** for reference/synthetic data — they're effectively free.
4. **Avoid `iploc` and wide presets over large scans** — enrich a *small* filtered
   set, not the raw dataset; reserve `metrics_view` for genuinely needed spans.
5. **Don't rely on `| limit` to save cost** — it doesn't reduce the scan.
6. **Batch/space concurrency** — there's a max-concurrent-query ceiling; bursts get
   rejected (`total_daily_concurrent_rejected_queries`). Serialize heavy hunts.

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
