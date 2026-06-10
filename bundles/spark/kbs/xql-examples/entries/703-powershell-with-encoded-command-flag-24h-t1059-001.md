---
id: XQL-703-d05f928f
title: PowerShell with encoded command flag (24h, T1059.001)
category: detection
dataset: xdr_data
tags:
  - filter
  - fields
  - limit
  - xdr_data
  - process
  - powershell
  - T1059.001
---

# PowerShell with encoded command flag (24h, T1059.001)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| filter lowercase(action_process_image_name) = "powershell.exe"
| filter lowercase(action_process_image_command_line) contains "-enc" or lowercase(action_process_image_command_line) contains "-encodedcommand"
| fields _time, agent_hostname, actor_process_image_name, action_process_image_command_line
| limit 10
```

## When to use

PowerShell with -EncodedCommand / -enc is a classic obfuscation technique (MITRE T1059.001). Flag any execution + return the host + parent + full command line for triage.

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
