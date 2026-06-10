---
id: XQL-854-bba99a73
title: Median upload bytes per host (24h, median)
category: investigation
dataset: xdr_data
tags:
  - filter
  - comp
  - sort
  - limit
  - xdr_data
  - network
  - median
---

# Median upload bytes per host (24h, median)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK and action_total_upload > 0
| comp median(action_total_upload) as median_bytes, avg(action_total_upload) as avg_bytes, count() as conn_count by agent_hostname
| sort desc median_bytes
| limit 10
```

## When to use

Per-host MEDIAN upload bytes (more robust to outliers than avg). Median vs avg: close = uniform; median much less than avg = skewed by a few large outliers.

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
