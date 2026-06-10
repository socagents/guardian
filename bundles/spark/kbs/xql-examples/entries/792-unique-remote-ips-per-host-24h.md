---
id: XQL-792-ac13f3c1
title: Unique remote IPs per host (24h)
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

# Unique remote IPs per host (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK and action_remote_ip != null
| comp count_distinct(action_remote_ip) as unique_destinations by agent_hostname
| sort desc unique_destinations
| limit 10
```

## When to use

Per-host unique-destination count. Hosts with abnormally high destination counts could be scanners (legitimate or otherwise) or compromised hosts spraying connections.

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
