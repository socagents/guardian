---
id: XQL-715-309d319b
title: Top registry keys modified (24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - comp
  - sort
  - limit
  - xdr_data
  - registry
---

# Top registry keys modified (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.REGISTRY
| comp count() as modifications by action_registry_key_name
| sort desc modifications
| limit 10
```

## When to use

Most-modified registry keys baseline. Windows housekeeping dominates; spikes in autoruns / boot-execute / image-file-execution paths are persistence indicators.

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
