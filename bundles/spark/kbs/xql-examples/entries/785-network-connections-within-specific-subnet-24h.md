---
id: XQL-785-a68e1225
title: Network connections within specific subnet (24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - comp
  - sort
  - limit
  - xdr_data
  - network
  - incidr
---

# Network connections within specific subnet (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK and action_remote_ip != null
| filter incidr(action_remote_ip, "10.0.0.0/8")
| comp count() as cnt by action_remote_ip
| sort desc cnt
| limit 10
```

## When to use

Connections targeting the 10/8 RFC1918 range. Useful for understanding internal-network communication patterns.

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
