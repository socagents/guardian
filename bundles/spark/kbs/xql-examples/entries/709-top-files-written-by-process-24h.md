---
id: XQL-709-7c7c9a43
title: Top files written by process (24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - comp
  - sort
  - limit
  - xdr_data
  - file
---

# Top files written by process (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.FILE
| comp count() as writes by actor_process_image_name, action_file_extension
| sort desc writes
| limit 10
```

## When to use

Which processes write the most files, by extension. Useful for understanding normal-state writers (system processes) so you can spot anomalies (e.g. unexpected process writing .exe files).

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
