---
id: XQL-714-c30abbdf
title: DNS query volume per host (24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - comp
  - sort
  - limit
  - xdr_data
  - network
  - dns
---

# DNS query volume per host (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK and action_remote_port = 53
| comp count() as dns_queries by agent_hostname
| sort desc dns_queries
| limit 10
```

## When to use

Hosts with abnormally high DNS query volume can indicate DNS tunneling or malware C2 over DNS. The query filters to port 53 to capture DNS-protocol traffic.

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
