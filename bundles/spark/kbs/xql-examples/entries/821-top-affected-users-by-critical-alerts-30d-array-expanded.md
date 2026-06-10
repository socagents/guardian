---
id: XQL-821-38310801
title: Top affected users by critical alerts (30d) — array-expanded
category: investigation
dataset: alerts
tags:
  - filter
  - arrayexpand
  - comp
  - sort
  - limit
  - alerts
---

# Top affected users by critical alerts (30d) — array-expanded

**Dataset**: `alerts`

```sql
config timeframe = 30d
| dataset = alerts
| filter severity = "CRITICAL" and user_name != null
| arrayexpand user_name
| comp count() as alerts, count_distinct(alert_name) as unique_alert_types by user_name
| sort desc alerts
| limit 10
```

## When to use

Users with the most critical-severity alerts. `user_name` is array-typed — arrayexpand to enable aggregation.

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
