---
id: XQL-711-8e67530f
title: Top hosts by outbound upload bytes (24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - comp
  - sort
  - limit
  - xdr_data
  - network
  - exfil
---

# Top hosts by outbound upload bytes (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK
| comp sum(action_total_upload) as total_upload by agent_hostname
| sort desc total_upload
| limit 10
```

## When to use

Aggregate upload bytes per host to identify data-exfiltration candidates. Hosts with anomalously high upload totals + minimal legitimate egress reason are worth investigating.

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
