---
id: XQL-777-222632bb
title: Process activity by day-of-week (7d)
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
  - format_timestamp
---

# Process activity by day-of-week (7d)

**Dataset**: `xdr_data`

```sql
config timeframe = 7d
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| alter dow = format_timestamp("%A", _time)
| comp count() as cnt by dow
| sort desc cnt
| limit 10
```

## When to use

Day-of-week activity distribution. Weekend activity volumes vs weekday are useful for baseline + spotting bursts on unusual days.

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
