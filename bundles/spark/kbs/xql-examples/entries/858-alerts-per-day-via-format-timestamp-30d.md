---
id: XQL-858-ae5cd799
title: Alerts per day via format_timestamp (30d)
category: investigation
dataset: alerts
tags:
  - filter
  - alter
  - comp
  - sort
  - limit
  - alerts
  - format_timestamp
---

# Alerts per day via format_timestamp (30d)

**Dataset**: `alerts`

```sql
config timeframe = 30d
| dataset = alerts
| alter day_bucket = format_timestamp("%Y-%m-%d", _time)
| comp count() as cnt by day_bucket, severity
| sort desc day_bucket
| limit 10
```

## When to use

Daily alert count per severity using `format_timestamp("%Y-%m-%d", _time)` for day-precision string buckets. Alternative to `bin _time span = 1d` when you want ISO-date strings in the output.

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
