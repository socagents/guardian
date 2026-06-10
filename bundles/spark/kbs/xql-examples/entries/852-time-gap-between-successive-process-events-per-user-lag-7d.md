---
id: XQL-852-8dfd6ba0
title: Time gap between successive process events per user (lag, 7d)
category: detection
dataset: xdr_data
tags:
  - filter
  - windowcomp
  - alter
  - fields
  - sort
  - limit
  - xdr_data
  - process
  - lag
---

# Time gap between successive process events per user (lag, 7d)

**Dataset**: `xdr_data`

```sql
config timeframe = 7d
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START and actor_effective_username != null
| windowcomp lag(_time) by actor_effective_username sort asc _time as prev_time
| filter prev_time != null
| alter gap_seconds = divide(timestamp_diff(_time, prev_time, "SECOND"), 1)
| filter gap_seconds < 5
| fields _time, actor_effective_username, agent_hostname, action_process_image_name, gap_seconds
| sort asc gap_seconds
| limit 10
```

## When to use

Successive process executions within 5s of the previous by the same user. `lag()` returns the prior row in the partition. Burst-detection without `transaction`.

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
