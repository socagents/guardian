---
id: XQL-835-d67342cb
title: Round-to-100 normalized command-line lengths (24h, round)
category: investigation
dataset: xdr_data
tags:
  - filter
  - alter
  - comp
  - sort
  - limit
  - xdr_data
  - process
  - round
  - math
---

# Round-to-100 normalized command-line lengths (24h, round)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START and action_process_image_command_line != null
| alter cmd_len = len(action_process_image_command_line)
| alter len_bucket = multiply(round(divide(cmd_len, 100)), 100)
| comp count() as cnt by len_bucket
| sort desc cnt
| limit 10
```

## When to use

Process command-line lengths bucketed to nearest 100 chars. `round + divide + multiply` chains together for clean rounding. Histogram pattern adaptable to other numeric fields.

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
