---
id: XQL-853-98004ae4
title: First + last process per host (first_value/last_value, 24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - windowcomp
  - dedup
  - fields
  - sort
  - limit
  - xdr_data
  - process
  - first_value
  - last_value
---

# First + last process per host (first_value/last_value, 24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| windowcomp first_value(action_process_image_name) by agent_hostname sort asc _time as first_proc
| windowcomp last_value(action_process_image_name) by agent_hostname sort asc _time as last_proc
| dedup agent_hostname
| fields agent_hostname, first_proc, last_proc
| sort asc agent_hostname
| limit 10
```

## When to use

Per-host first + last process names of the day via window functions. `dedup` collapses to one row per host.

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
