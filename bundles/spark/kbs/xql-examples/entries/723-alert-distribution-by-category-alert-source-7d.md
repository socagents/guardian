---
id: XQL-723-5f864da8
title: Alert distribution by category + alert_source (7d)
category: investigation
dataset: alerts
tags:
  - filter
  - comp
  - sort
  - limit
  - alerts
---

# Alert distribution by category + alert_source (7d)

**Dataset**: `alerts`

```sql
config timeframe = 7d
| dataset = alerts
| comp count() as cnt by category, alert_source
| sort desc cnt
| limit 10
```

## When to use

Aggregate alerts by category and source detector. Useful for understanding which detection sources are firing the most + which categories dominate the tenant's alert mix.

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
