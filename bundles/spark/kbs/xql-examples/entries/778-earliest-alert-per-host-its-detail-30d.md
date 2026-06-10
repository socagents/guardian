---
id: XQL-778-54eb983f
title: Earliest alert per host + its detail (30d)
category: detection
dataset: alerts
tags:
  - filter
  - windowcomp
  - fields
  - sort
  - limit
  - alerts
  - row_number
---

# Earliest alert per host + its detail (30d)

**Dataset**: `alerts`

```sql
config timeframe = 30d
| dataset = alerts
| filter host_name != null
| windowcomp row_number() by host_name sort asc _time as rn
| filter rn = 1
| fields _time, host_name, alert_name, severity
| sort desc _time
| limit 10
```

## When to use

First-seen alert per host — useful for compromise-onset triage. `row_number()` partitioned by host + sorted ascending gives the earliest row per host.

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
