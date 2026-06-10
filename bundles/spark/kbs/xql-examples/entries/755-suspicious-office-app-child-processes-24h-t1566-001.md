---
id: XQL-755-4089d525
title: Suspicious Office-app child processes (24h, T1566.001)
category: detection
dataset: xdr_data
tags:
  - filter
  - fields
  - sort
  - limit
  - xdr_data
  - process
  - T1566.001
---

# Suspicious Office-app child processes (24h, T1566.001)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| filter lowercase(actor_process_image_name) in ("winword.exe", "excel.exe", "powerpnt.exe", "outlook.exe")
| filter lowercase(action_process_image_name) in ("cmd.exe", "powershell.exe", "wscript.exe", "cscript.exe", "mshta.exe", "rundll32.exe")
| fields _time, agent_hostname, actor_process_image_name, action_process_image_name, action_process_image_command_line
| sort desc _time
| limit 10
```

## When to use

Office applications spawning script hosts/cmd — MITRE T1566.001 (Spearphishing Attachment). One of the highest-fidelity detection patterns for macro-based attacks.

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
