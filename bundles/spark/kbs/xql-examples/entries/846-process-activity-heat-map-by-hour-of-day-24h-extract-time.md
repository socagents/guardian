---
id: XQL-846-eb3ed09d
title: Process activity heat-map by hour-of-day (24h, extract_time)
category: detection
dataset: xdr_data
tags:
  - filter
  - alter
  - comp
  - sort
  - limit
  - xdr_data
  - process
  - extract_time
---

# Process activity heat-map by hour-of-day (24h, extract_time)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| alter hour = extract_time(_time, "HOUR")
| comp count() as executions by hour, agent_hostname
| sort asc agent_hostname, asc hour
| limit 10
```

## When to use

Per-host hour-of-day execution heat map. `extract_time(timestamp, 'HOUR')` returns the hour component (0-23). Off-hours activity is a compromise indicator.

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
