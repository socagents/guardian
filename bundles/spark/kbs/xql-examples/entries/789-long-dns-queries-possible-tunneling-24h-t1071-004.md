---
id: XQL-789-cf378833
title: Long DNS queries — possible tunneling (24h, T1071.004)
category: detection
dataset: xdr_data
tags:
  - filter
  - alter
  - fields
  - sort
  - limit
  - xdr_data
  - network
  - dns
  - T1071.004
---

# Long DNS queries — possible tunneling (24h, T1071.004)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK and action_remote_port = 53
| filter dns_query_name != null
| alter q_len = len(dns_query_name)
| filter q_len > 100
| fields _time, agent_hostname, dns_query_name, q_len
| sort desc q_len
| limit 10
```

## When to use

Long DNS query names (>100 chars) — DNS tunneling indicator (MITRE T1071.004 Application Layer Protocol: DNS). Tunnel encodings produce abnormally long labels.

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
