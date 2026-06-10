---
id: XQL-742-654446ba
title: Alerts classified by severity tier
category: investigation
dataset: alerts
tags:
  - filter
  - alter
  - comp
  - sort
  - limit
  - alerts
  - conditional
---

# Alerts classified by severity tier

**Dataset**: `alerts`

```sql
config timeframe = 7d
| dataset = alerts
| alter tier = if(severity = "CRITICAL", "P1", if(severity = "HIGH", "P2", if(severity = "MEDIUM", "P3", "P4")))
| comp count() as cnt by tier
| sort asc tier
| limit 10
```

## When to use

Maps XSIAM severity to priority tiers (P1-P4) via nested `if()`. Useful for SLA reporting where the operations team tracks alerts by priority class.

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
