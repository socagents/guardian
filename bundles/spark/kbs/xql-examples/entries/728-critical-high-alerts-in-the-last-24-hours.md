---
id: XQL-728-680eaa09
title: Critical + high alerts in the last 24 hours
category: investigation
dataset: alerts
tags:
  - filter
  - fields
  - sort
  - limit
  - alerts
---

# Critical + high alerts in the last 24 hours

**Dataset**: `alerts`

```sql
config timeframe = 24h
| dataset = alerts
| filter severity in ("CRITICAL", "HIGH")
| fields _time, severity, alert_name, host_name, description
| sort desc _time
| limit 10
```

## When to use

Triage view for the high-severity tail. Returns the most recent CRITICAL + HIGH alerts in the last day with the description for quick context.

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
