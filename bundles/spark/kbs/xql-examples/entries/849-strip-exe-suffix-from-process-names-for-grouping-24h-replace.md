---
id: XQL-849-227ada38
title: Strip .exe suffix from process names for grouping (24h, replace)
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
  - replace
---

# Strip .exe suffix from process names for grouping (24h, replace)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| alter proc_root = lowercase(replace(action_process_image_name, ".exe", ""))
| comp count() as cnt by proc_root
| sort desc cnt
| limit 10
```

## When to use

Aggregate process executions by name without the .exe suffix — useful for cross-OS aggregation (Linux/macOS don't have the suffix). Uses `replace(field, old, new)`.

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
