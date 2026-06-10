---
id: XQL-707-f7462c8c
title: Long process command lines — possible obfuscation (24h)
category: detection
dataset: xdr_data
tags:
  - filter
  - alter
  - fields
  - sort
  - limit
  - xdr_data
  - process
---

# Long process command lines — possible obfuscation (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| alter cmd_len = len(action_process_image_command_line)
| filter cmd_len > 500
| fields _time, agent_hostname, action_process_image_name, cmd_len, action_process_image_command_line
| sort desc cmd_len
| limit 10
```

## When to use

Excessively long command lines (>500 chars) often indicate obfuscated PowerShell, base64 payloads, or other evasion techniques. `len()` builds the length column for sorting.

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
