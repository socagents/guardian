---
id: XQL-784-46cd1c6a
title: Daily alert trend by category (14d)
category: investigation
dataset: alerts
tags:
  - filter
  - bin
  - comp
  - sort
  - limit
  - alerts
---

# Daily alert trend by category (14d)

**Dataset**: `alerts`

```sql
config timeframe = 14d
| dataset = alerts
| filter category != null
| bin _time span = 1d
| comp count() as cnt by _time, category
| sort desc _time
| limit 10
```

## When to use

Two-week daily alert trend per category. Reveals category-level patterns + spikes.

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
