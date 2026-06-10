---
id: XQL-762-f7c545c2
title: Top file-write directories (24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - alter
  - comp
  - sort
  - limit
  - xdr_data
  - file
---

# Top file-write directories (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.FILE and action_file_path != null
| alter dir = arrayindex(regextract(action_file_path, "^(.+)\\\\[^\\\\]+$"), 0)
| comp count() as writes by dir
| sort desc writes
| limit 10
```

## When to use

Directory-level file-write distribution. Reveals which paths are most-written-to in the tenant — useful for tuning detections (exclude noisy paths) + spotting unusual destinations.

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
