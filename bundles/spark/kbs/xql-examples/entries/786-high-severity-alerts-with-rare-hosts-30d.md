---
id: XQL-786-f353f82b
title: High-severity alerts with rare hosts (30d)
category: detection
dataset: alerts
tags:
  - filter
  - comp
  - sort
  - limit
  - alerts
  - rare
---

# High-severity alerts with rare hosts (30d)

**Dataset**: `alerts`

```sql
config timeframe = 30d
| dataset = alerts
| filter severity in ("HIGH", "CRITICAL")
| comp count() as alerts_per_host by host_name, severity
| filter alerts_per_host = 1
| sort desc alerts_per_host
| limit 10
```

## When to use

Hosts that only had ONE high/critical alert in the timeframe. Lower-noise hosts where a single hit is more meaningful + more likely a true positive.

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
