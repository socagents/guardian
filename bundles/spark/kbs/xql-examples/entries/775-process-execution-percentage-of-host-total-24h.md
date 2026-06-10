---
id: XQL-775-841db690
title: Process execution percentage of host total (24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - comp
  - windowcomp
  - alter
  - sort
  - limit
  - xdr_data
  - process
  - math
---

# Process execution percentage of host total (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| comp count() as cnt by agent_hostname, action_process_image_name
| windowcomp sum(cnt) by agent_hostname as host_total
| alter pct = multiply(divide(cnt, host_total), 100)
| sort desc pct
| limit 10
```

## When to use

Each process's share of its host's total execution count. Single dominant process (>50%) on a host often indicates loop / batch activity worth investigating.

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
