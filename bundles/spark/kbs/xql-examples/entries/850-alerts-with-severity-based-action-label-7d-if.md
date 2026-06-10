---
id: XQL-850-9abd7a3f
title: Alerts with severity-based action label (7d, if)
category: investigation
dataset: alerts
tags:
  - filter
  - alter
  - comp
  - sort
  - limit
  - alerts
  - if
  - conditional
---

# Alerts with severity-based action label (7d, if)

**Dataset**: `alerts`

```sql
config timeframe = 7d
| dataset = alerts
| alter action_needed = if(severity = "CRITICAL", "immediate-page", if(severity = "HIGH", "same-day", if(severity = "MEDIUM", "next-business-day", "backlog")))
| comp count() as cnt by action_needed
| sort desc cnt
| limit 10
```

## When to use

Maps each alert to an SLA action label via nested `if()`. Useful for SLA reporting + operator-facing dashboards.

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
