---
id: XQL-771-1d0c649c
title: Alerts grouped by week (12w)
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

# Alerts grouped by week (12w)

**Dataset**: `alerts`

```sql
config timeframe = 12w
| dataset = alerts
| bin _time span = 1w
| comp count() as cnt by _time, severity
| sort desc _time
| limit 10
```

## When to use

Weekly alert-volume trend across severities. Useful for executive reporting + spotting macro trends (e.g. steady increase in HIGH alerts over a quarter).

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
