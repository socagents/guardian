---
id: XQL-780-ad078d3a
title: Process command lines containing base64-encoded blocks (24h, T1027)
category: detection
dataset: xdr_data
tags:
  - filter
  - fields
  - sort
  - limit
  - xdr_data
  - process
  - T1027
  - regex
---

# Process command lines containing base64-encoded blocks (24h, T1027)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| filter action_process_image_command_line ~= "[A-Za-z0-9+/]{50,}={0,2}"
| fields _time, agent_hostname, action_process_image_name, action_process_image_command_line
| sort desc _time
| limit 10
```

## When to use

Command lines containing long base64-looking blocks (MITRE T1027 — Obfuscated Files or Information). The regex matches 50+ base64 chars optionally padded with =.

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
