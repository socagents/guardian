---
id: XQL-822-fd98386e
title: Process activity duration per host (24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - comp
  - alter
  - sort
  - limit
  - xdr_data
  - process
  - timestamp_diff
---

# Process activity duration per host (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| comp min(_time) as first_seen, max(_time) as last_seen, count() as cnt by agent_hostname
| alter duration_minutes = divide(timestamp_diff(last_seen, first_seen, "MINUTE"), 1)
| sort desc cnt
| limit 10
```

## When to use

Per-host first/last process time + active duration in minutes. Uses `timestamp_diff(end, start, unit)` for time arithmetic on date fields.

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
