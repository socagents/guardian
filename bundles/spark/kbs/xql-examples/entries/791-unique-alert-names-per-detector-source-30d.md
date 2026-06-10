---
id: XQL-791-e221fccd
title: Unique alert names per detector source (30d)
category: investigation
dataset: alerts
tags:
  - filter
  - comp
  - sort
  - limit
  - alerts
---

# Unique alert names per detector source (30d)

**Dataset**: `alerts`

```sql
config timeframe = 30d
| dataset = alerts
| filter alert_source != null
| comp count_distinct(alert_name) as unique_rules, count() as fires by alert_source
| sort desc unique_rules
| limit 10
```

## When to use

Per-detector source: how many unique alert rules fired + how many total fires. Reveals detector breadth (many rules) vs depth (few rules, many fires).

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
