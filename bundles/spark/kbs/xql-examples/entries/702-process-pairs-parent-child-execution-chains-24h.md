---
id: XQL-702-edf4c6e4
title: Process pairs — parent → child execution chains (24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - comp
  - sort
  - limit
  - xdr_data
  - process
---

# Process pairs — parent → child execution chains (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| comp count() as cnt by actor_process_image_name, action_process_image_name
| sort desc cnt
| limit 10
```

## When to use

Identifies the most common parent → child process execution pairs. Foundational pattern for behavior-baseline analytics + lateral movement detection (rare pairs = candidates).

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
