---
id: XQL-800-f116e8a9
title: Alert detection-source breakdown (30d)
category: investigation
dataset: alerts
tags:
  - filter
  - comp
  - sort
  - limit
  - alerts
---

# Alert detection-source breakdown (30d)

**Dataset**: `alerts`

```sql
config timeframe = 30d
| dataset = alerts
| filter alert_source != null
| comp count() as cnt by alert_source, severity
| sort desc cnt
| limit 10
```

## When to use

Per-detection-source alert volume by severity. Reveals which detector source generates which severities. (Corrected: `source` field → `alert_source`.)

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
