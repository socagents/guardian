---
id: XQL-738-861d6303
title: Hourly file-write rate by extension (24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - bin
  - comp
  - sort
  - limit
  - xdr_data
  - file
---

# Hourly file-write rate by extension (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.FILE
| bin _time span = 1h
| comp count() as writes by _time, action_file_extension
| sort desc _time
| limit 10
```

## When to use

Time-bucketed file-write volume by extension. Reveals daily patterns + sudden bursts (ransomware encryption events drop many similar files).

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
