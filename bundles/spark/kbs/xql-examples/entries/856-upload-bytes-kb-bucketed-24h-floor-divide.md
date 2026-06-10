---
id: XQL-856-dbee3440
title: Upload bytes KB-bucketed (24h, floor + divide)
category: investigation
dataset: xdr_data
tags:
  - filter
  - alter
  - comp
  - sort
  - limit
  - xdr_data
  - network
  - floor
  - math
---

# Upload bytes KB-bucketed (24h, floor + divide)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK and action_total_upload > 0
| alter kb_bucket = floor(divide(action_total_upload, 1000))
| comp count() as cnt by kb_bucket
| sort desc cnt
| limit 10
```

## When to use

KB-bucketed upload byte distribution. `floor(divide(bytes, 1000))` truncates to KB. Useful for histogram-style upload-size profiling.

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
