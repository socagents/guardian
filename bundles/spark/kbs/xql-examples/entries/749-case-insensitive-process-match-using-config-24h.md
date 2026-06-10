---
id: XQL-749-a856ccc0
title: Case-insensitive process match using config (24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - fields
  - sort
  - limit
  - xdr_data
  - process
  - config
---

# Case-insensitive process match using config (24h)

**Dataset**: `xdr_data`

```sql
config case_sensitive = false timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| filter action_process_image_name = "powershell.exe"
| fields _time, agent_hostname, action_process_image_name, action_process_image_command_line
| sort desc _time
| limit 10
```

## When to use

Uses `config case_sensitive = false` so the equality match is case-insensitive without needing `lowercase()` wrapping. Useful for cleaner queries on case-mixed Windows paths.

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
