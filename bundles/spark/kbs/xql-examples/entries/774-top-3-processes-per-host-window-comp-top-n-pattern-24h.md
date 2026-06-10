---
id: XQL-774-ad747036
title: Top-3 processes per host (window-comp top-n pattern, 24h)
category: detection
dataset: xdr_data
tags:
  - filter
  - comp
  - windowcomp
  - sort
  - limit
  - xdr_data
  - process
  - top-n
---

# Top-3 processes per host (window-comp top-n pattern, 24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| comp count() as cnt by agent_hostname, action_process_image_name
| windowcomp row_number() by agent_hostname sort desc cnt as rank
| filter rank <= 3
| sort asc agent_hostname, asc rank
| limit 10
```

## When to use

Top-3 most-spawned processes PER HOST — classic window-function top-N pattern. `row_number()` partitioned by host + sorted by count gives the per-host rank.

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
