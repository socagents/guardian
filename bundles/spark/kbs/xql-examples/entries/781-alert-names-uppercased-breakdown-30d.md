---
id: XQL-781-f16592d3
title: Alert names — uppercased breakdown (30d)
category: investigation
dataset: alerts
tags:
  - filter
  - alter
  - comp
  - sort
  - limit
  - alerts
  - uppercase
---

# Alert names — uppercased breakdown (30d)

**Dataset**: `alerts`

```sql
config timeframe = 30d
| dataset = alerts
| alter alert_upper = uppercase(alert_name)
| comp count() as cnt by alert_upper
| sort desc cnt
| limit 10
```

## When to use

Case-normalized alert-name aggregation. Useful when alert names show up with mixed casing from different sources.

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
