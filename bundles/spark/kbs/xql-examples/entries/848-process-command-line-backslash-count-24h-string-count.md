---
id: XQL-848-61db6424
title: Process command-line backslash count (24h, string_count)
category: investigation
dataset: xdr_data
tags:
  - filter
  - alter
  - fields
  - sort
  - limit
  - xdr_data
  - process
  - string_count
---

# Process command-line backslash count (24h, string_count)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| filter action_process_image_command_line != null
| alter backslash_count = string_count(action_process_image_command_line, "\\\\")
| filter backslash_count > 5
| fields _time, agent_hostname, action_process_image_name, backslash_count, action_process_image_command_line
| sort desc backslash_count
| limit 10
```

## When to use

Surfaces command lines with many backslashes — often indicates deep file-path args or obfuscation. `string_count(field, substring)` returns the count.

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
