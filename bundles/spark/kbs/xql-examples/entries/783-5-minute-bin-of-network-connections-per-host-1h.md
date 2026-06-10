---
id: XQL-783-3d147b2f
title: 5-minute bin of network connections per host (1h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - bin
  - comp
  - sort
  - limit
  - xdr_data
  - network
---

# 5-minute bin of network connections per host (1h)

**Dataset**: `xdr_data`

```sql
config timeframe = 1h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK
| bin _time span = 5m
| comp count() as connections by _time, agent_hostname
| sort desc _time, connections
| limit 10
```

## When to use

Fine-grained (5min) network connection rate per host. Useful for tight burst-detection windows during incident response.

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
