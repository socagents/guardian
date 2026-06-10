---
id: XQL-710-362892cb
title: Top 10 remote destinations by connection count (24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - comp
  - sort
  - limit
  - xdr_data
  - network
---

# Top 10 remote destinations by connection count (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK
| filter action_remote_ip != null
| comp count() as connections by action_remote_ip, action_remote_port
| sort desc connections
| limit 10
```

## When to use

Aggregates outbound + inbound connections by remote IP+port pair. Useful for surfacing top external services + spotting C2-like patterns (high connection count to a single unknown IP).

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
