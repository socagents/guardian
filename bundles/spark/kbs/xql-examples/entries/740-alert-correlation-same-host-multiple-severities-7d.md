---
id: XQL-740-324d1f53
title: Alert correlation — same host + multiple severities (7d)
category: detection
dataset: alerts
tags:
  - filter
  - comp
  - sort
  - limit
  - alerts
---

# Alert correlation — same host + multiple severities (7d)

**Dataset**: `alerts`

```sql
config timeframe = 7d
| dataset = alerts
| filter host_name != null
| comp count_distinct(severity) as sev_count, values(severity) as severities, count() as alert_count by host_name
| filter sev_count >= 2
| sort desc alert_count
| limit 10
```

## When to use

Hosts with alerts at multiple severities within the timeframe. Could indicate an active campaign (multiple detection rules firing) or chronic noise (always-noisy host).

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
