---
id: XQL-746-d3613d2f
title: Uppercase agent_hostname normalization (24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - alter
  - comp
  - sort
  - limit
  - xdr_data
  - string
---

# Uppercase agent_hostname normalization (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS
| alter host_upper = uppercase(agent_hostname)
| comp count() as cnt by host_upper
| sort desc cnt
| limit 10
```

## When to use

Normalizes hostnames to uppercase for case-insensitive aggregation. Useful when the same host appears with mixed-case names due to legacy logging.

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
