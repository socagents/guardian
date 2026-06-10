---
id: XQL-851-7d988f1f
title: Top 3 ranked processes per host (rank, 24h)
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
  - rank
---

# Top 3 ranked processes per host (rank, 24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| comp count() as cnt by agent_hostname, action_process_image_name
| windowcomp rank() by agent_hostname sort desc cnt as proc_rank
| filter proc_rank <= 3
| sort asc agent_hostname, asc proc_rank
| limit 10
```

## When to use

Top-3 processes PER HOST using `rank()`. Handles ties unlike `row_number()`. Canonical top-N-per-group idiom.

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
