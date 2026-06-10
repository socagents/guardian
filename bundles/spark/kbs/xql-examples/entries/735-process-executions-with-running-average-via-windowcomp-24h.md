---
id: XQL-735-4757ed35
title: Process executions with running average via windowcomp (24h)
category: detection
dataset: xdr_data
tags:
  - filter
  - bin
  - comp
  - windowcomp
  - sort
  - limit
  - xdr_data
  - process
---

# Process executions with running average via windowcomp (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| bin _time span = 1h
| comp count() as exec_count by _time, agent_hostname
| windowcomp avg(exec_count) by agent_hostname as rolling_avg
| sort desc _time
| limit 10
```

## When to use

Hourly execution counts with a rolling average per host computed via `windowcomp`. Foundation for anomaly-detection queries (compare current count vs rolling baseline).

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
