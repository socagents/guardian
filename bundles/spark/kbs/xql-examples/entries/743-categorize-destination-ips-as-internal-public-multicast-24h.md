---
id: XQL-743-303894f2
title: Categorize destination IPs as internal / public / multicast (24h)
category: detection
dataset: xdr_data
tags:
  - filter
  - alter
  - comp
  - sort
  - limit
  - xdr_data
  - network
  - incidr
  - conditional
---

# Categorize destination IPs as internal / public / multicast (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK and action_remote_ip != null
| alter ip_class = if(incidr(action_remote_ip, "10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16"), "internal", if(incidr(action_remote_ip, "224.0.0.0/4"), "multicast", if(incidr(action_remote_ip, "127.0.0.0/8"), "loopback", "public")))
| comp count() as cnt, sum(action_total_upload) as upload by ip_class, agent_hostname
| sort desc upload
| limit 10
```

## When to use

IP-class labeling via nested `if` + `incidr`. Aggregates upload bytes per (class, host) so you can see per-host traffic distribution by destination type.

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
