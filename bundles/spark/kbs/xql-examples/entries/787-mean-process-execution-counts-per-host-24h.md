---
id: XQL-787-e619d553
title: Mean process-execution counts per host (24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - comp
  - limit
  - xdr_data
  - process
  - stats
---

# Mean process-execution counts per host (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| comp count() as host_total by agent_hostname
| comp avg(host_total) as mean_per_host, count() as host_count
| limit 10
```

## When to use

Fleet-level statistic — average process executions per host + total host count. Useful baseline for sizing + outlier-comparison queries.

## Variations

_(v0.7.0 hand-curated — variations not yet authored. Operator's
curation pass adds these.)_

## Source

Hand-curated for v0.7.0's 100-query KB expansion. Validated against
the operator's live XDR tenant before being written to this file:
the query body was POSTed to `xdr_run_xql_query` and returned
`status: SUCCESS` (any row count, including 0). The `## When to use`
description above was hand-written to match the operator-language
norms of the existing KB.
