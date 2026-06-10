---
id: XQL-760-f33b855d
title: Files written with double extension (24h, T1036.007)
category: detection
dataset: xdr_data
tags:
  - filter
  - fields
  - sort
  - limit
  - xdr_data
  - file
  - T1036.007
---

# Files written with double extension (24h, T1036.007)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.FILE
| filter action_file_path ~= "(?i)\\.(pdf|doc|xls|jpg|png|txt|zip)\\.(exe|scr|bat|cmd|com|lnk)$"
| fields _time, agent_hostname, action_process_image_name, action_file_path
| sort desc _time
| limit 10
```

## When to use

Files written with double-extension naming (e.g. report.pdf.exe). MITRE T1036.007 — common social-engineering trick that exploits Windows's hide-extension default.

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
