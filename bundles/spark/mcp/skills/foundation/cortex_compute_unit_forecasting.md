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

## Notes / caveats

- There is **no public API** for the per-query usage *list* (the UI "Compute Unit
  Usage" table, exportable as TSV). To capture per-query cost programmatically, read
  `compute_units_used` from each `xsiam_run_xql_query` response, or aggregate from
  `xsiam_get_xql_quota`.
- CU is attributed **per PAPI (API) key** in the usage table — multiple keys on one
  tenant all draw from the same tenant daily limit.
- `used_quota` is **cumulative for the license year**; `daily_used_quota` is the one
  that resets daily. Don't confuse the two when explaining "remaining".
