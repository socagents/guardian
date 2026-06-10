---
id: XQL-745-006a5d1e
title: Extract file basename from full path (24h)
category: detection
dataset: xdr_data
tags:
  - filter
  - alter
  - comp
  - sort
  - limit
  - xdr_data
  - file
  - split
---

# Extract file basename from full path (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.FILE
| filter action_file_path != null
| alter basename = arrayindex(split(action_file_path, "\\"), -1)
| comp count() as writes by basename, action_file_extension
| sort desc writes
| limit 10
```

## When to use

Splits the full file path on backslash and takes the last element via `arrayindex(arr, -1)` — gives the file basename without directory. Aggregates writes by basename.

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
