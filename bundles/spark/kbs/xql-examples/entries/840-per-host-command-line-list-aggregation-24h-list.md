---
id: XQL-840-1e83b7cc
title: Per-host command-line list aggregation (24h, list)
category: investigation
dataset: xdr_data
tags:
  - filter
  - comp
  - alter
  - fields
  - sort
  - limit
  - xdr_data
  - process
  - list
---

# Per-host command-line list aggregation (24h, list)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START and action_process_image_command_line != null
| comp list(action_process_image_command_line) as commands by agent_hostname
| alter command_count = array_length(commands)
| filter command_count >= 3
| fields agent_hostname, command_count
| sort desc command_count
| limit 10
```

## When to use

Per-host command-line collection via `list()` aggregation. Unlike `values()` (which deduplicates), `list()` keeps duplicates. Useful for forensic per-host command timelines.

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
