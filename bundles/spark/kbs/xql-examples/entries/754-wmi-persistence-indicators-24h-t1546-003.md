---
id: XQL-754-648e1e9b
title: WMI persistence indicators (24h, T1546.003)
category: detection
dataset: xdr_data
tags:
  - filter
  - fields
  - sort
  - limit
  - xdr_data
  - process
  - T1546.003
---

# WMI persistence indicators (24h, T1546.003)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| filter lowercase(action_process_image_name) in ("wmic.exe", "powershell.exe")
| filter lowercase(action_process_image_command_line) contains "__eventfilter" or lowercase(action_process_image_command_line) contains "__eventconsumer" or lowercase(action_process_image_command_line) contains "__filtertoconsumerbinding"
| fields _time, agent_hostname, action_process_image_command_line
| sort desc _time
| limit 10
```

## When to use

WMI Event Subscription persistence — MITRE T1546.003. Rare but high-fidelity. Matches the three WMI classes that compose a persistent subscription.

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
