---
id: XQL-836-15499912
title: Network destinations sortable by IP-integer order (24h, ip_to_int)
category: investigation
dataset: xdr_data
tags:
  - filter
  - comp
  - alter
  - sort
  - limit
  - xdr_data
  - network
  - ip_to_int
---

# Network destinations sortable by IP-integer order (24h, ip_to_int)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK and action_remote_ip != null
| filter not incidr(action_remote_ip, "10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16")
| comp count() as connections by action_remote_ip
| alter ip_int = ip_to_int(action_remote_ip)
| sort asc ip_int
| limit 10
```

## When to use

External IPs sorted in numerical (IP-integer) order. `ip_to_int(ipv4)` converts to a 32-bit integer for proper sorting. Useful for range-based analysis + identifying nearby IPs in the same subnet.

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
