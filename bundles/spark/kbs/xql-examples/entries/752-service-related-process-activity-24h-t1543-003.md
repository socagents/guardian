---
id: XQL-752-1227d0d3
title: Service-related process activity (24h, T1543.003)
category: detection
dataset: xdr_data
tags:
  - filter
  - fields
  - sort
  - limit
  - xdr_data
  - process
  - T1543.003
---

# Service-related process activity (24h, T1543.003)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| filter lowercase(action_process_image_name) in ("sc.exe", "services.exe", "net.exe")
| filter action_process_image_command_line ~= "(?i)(create|config|start|stop|delete)"
| fields _time, agent_hostname, actor_effective_username, action_process_image_command_line
| sort desc _time
| limit 10
```

## When to use

Service create/modify/delete activity — MITRE T1543.003 (Windows Service Persistence). Captures both legitimate admin activity and attacker service-installation.

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
