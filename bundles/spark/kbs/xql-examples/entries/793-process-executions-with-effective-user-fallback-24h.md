---
id: XQL-793-88097884
title: Process executions with effective user fallback (24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - alter
  - comp
  - sort
  - limit
  - xdr_data
  - user
  - coalesce
---

# Process executions with effective user fallback (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| alter user = coalesce(actor_effective_username, actor_primary_username, "unknown")
| comp count() as cnt by user
| sort desc cnt
| limit 10
```

## When to use

Per-user execution count with `coalesce` to fall back to primary_username when effective is null, then to literal 'unknown'. Robust against missing-data gaps.

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
