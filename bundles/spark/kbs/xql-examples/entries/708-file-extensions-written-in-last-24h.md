---
id: XQL-708-bf3622c5
title: File extensions written in last 24h
category: investigation
dataset: xdr_data
tags:
  - filter
  - comp
  - sort
  - limit
  - xdr_data
  - file
---

# File extensions written in last 24h

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.FILE
| comp count() as cnt by action_file_extension
| sort desc cnt
| limit 10
```

## When to use

Aggregate file events by extension to baseline file-write patterns. Spikes in unusual extensions (.lnk, .scr, .ps1) can indicate attacker tooling drops.

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
