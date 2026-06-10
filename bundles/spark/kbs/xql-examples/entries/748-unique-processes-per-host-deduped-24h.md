---
id: XQL-748-5b33884f
title: Unique processes per host (deduped, 24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - dedup
  - fields
  - sort
  - limit
  - xdr_data
  - process
---

# Unique processes per host (deduped, 24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| dedup agent_hostname, action_process_image_name
| fields agent_hostname, action_process_image_name
| sort asc agent_hostname
| limit 10
```

## When to use

DEDUP stage collapses to one row per (host, process). Returns the unique processes seen per host — useful for whitelist generation + process-inventory snapshots.

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
