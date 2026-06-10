---
id: XQL-724-81405d9d
title: Top 10 alert names by occurrence (7d)
category: investigation
dataset: alerts
tags:
  - filter
  - comp
  - sort
  - limit
  - alerts
---

# Top 10 alert names by occurrence (7d)

**Dataset**: `alerts`

```sql
config timeframe = 7d
| dataset = alerts
| comp count() as cnt by alert_name
| sort desc cnt
| limit 10
```

## When to use

Surfaces the most-fired alert rules. Helps prioritize tuning effort (high-volume rules with low fidelity) or identify campaign-level activity (sudden spikes on a single alert name).

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
