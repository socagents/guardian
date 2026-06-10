---
id: XQL-770-7a7e89b8
title: Top alert names by host count (30d)
category: investigation
dataset: alerts
tags:
  - filter
  - comp
  - sort
  - limit
  - alerts
---

# Top alert names by host count (30d)

**Dataset**: `alerts`

```sql
config timeframe = 30d
| dataset = alerts
| comp count_distinct(host_name) as host_count, count() as alert_count by alert_name
| sort desc host_count
| limit 10
```

## When to use

Alert names ranked by how many distinct hosts they fired against. High host-count alerts often indicate widespread issues (env-wide misconfig, broad campaign).

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
