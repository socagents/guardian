---
id: XQL-761-3cbd8c31
title: Large files written by non-system processes (24h)
category: detection
dataset: xdr_data
tags:
  - filter
  - fields
  - sort
  - limit
  - xdr_data
  - file
---

# Large files written by non-system processes (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.FILE and event_sub_type = ENUM.FILE_WRITE
| filter action_file_size > 100000000
| filter lowercase(actor_process_image_name) not in ("system", "svchost.exe", "explorer.exe", "wsappx.exe", "taskhostw.exe")
| fields _time, agent_hostname, actor_process_image_name, action_file_path, action_file_size
| sort desc action_file_size
| limit 10
```

## When to use

Large file writes (>100MB) by non-system processes — possible exfiltration staging, ransomware encryption progress, or unexpected log production. The exclusion list filters common system writers.

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
