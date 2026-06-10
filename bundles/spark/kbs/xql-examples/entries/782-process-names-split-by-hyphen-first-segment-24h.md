---
id: XQL-782-bbc60977
title: Process names split by hyphen — first segment (24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - alter
  - comp
  - sort
  - limit
  - xdr_data
  - process
  - split
---

# Process names split by hyphen — first segment (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START and action_process_image_name != null
| alter prefix = arrayindex(split(action_process_image_name, "-"), 0)
| comp count() as cnt by prefix
| sort desc cnt
| limit 10
```

## When to use

Splits process names on hyphen + aggregates by the first segment. Useful for vendor-prefix aggregation (e.g. `chrome-helper-*` all become `chrome`).

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
