---
id: XQL-769-aa7094e7
title: Alert author actor — who/which engine generates which alerts (30d)
category: investigation
dataset: alerts
tags:
  - filter
  - comp
  - sort
  - limit
  - alerts
---

# Alert author actor — who/which engine generates which alerts (30d)

**Dataset**: `alerts`

```sql
config timeframe = 30d
| dataset = alerts
| filter alert_source != null
| comp count() as cnt, count_distinct(host_name) as affected_hosts by alert_source
| sort desc cnt
| limit 10
```

## When to use

Per-engine alert production volume + per-engine blast radius (affected hosts). Useful for the SOC manager to see which engines drive the alert workload.

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
