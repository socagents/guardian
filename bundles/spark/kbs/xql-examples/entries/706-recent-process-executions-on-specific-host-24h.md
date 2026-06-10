---
id: XQL-706-df57f8b6
title: Recent process executions on specific host (24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - fields
  - sort
  - limit
  - xdr_data
  - process
---

# Recent process executions on specific host (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| filter lowercase(agent_hostname) = "xdragent"
| fields _time, agent_hostname, actor_process_image_name, action_process_image_name, action_process_image_command_line, actor_effective_username
| sort desc _time
| limit 10
```

## When to use

Investigation pivot — given a specific host of interest, return the most recent process-start events with parent/child + command line + initiating user. Replace 'xdragent' with the target host.

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
