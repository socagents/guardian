---
id: XQL-705-5fd60291
title: Process spawned with explicit credentials in command line (24h)
category: detection
dataset: xdr_data
tags:
  - filter
  - fields
  - limit
  - xdr_data
  - process
  - credentials
---

# Process spawned with explicit credentials in command line (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| filter action_process_image_command_line ~= "(?i)(/user:|-user |-u \S+ -p \S+|password=|passwd=)"
| fields _time, agent_hostname, actor_effective_username, action_process_image_name, action_process_image_command_line
| limit 10
```

## When to use

Processes with credentials hardcoded in command line — often indicates poor secret-hygiene or active attack (psexec, runas variants). The regex matches Windows-style credential flags.

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
