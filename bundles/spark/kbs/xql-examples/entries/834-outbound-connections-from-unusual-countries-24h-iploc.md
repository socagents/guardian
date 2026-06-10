---
id: XQL-834-de30197e
title: Outbound connections from unusual countries (24h, iploc)
category: detection
dataset: xdr_data
tags:
  - filter
  - iploc
  - comp
  - sort
  - limit
  - xdr_data
  - network
  - geo
---

# Outbound connections from unusual countries (24h, iploc)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK and action_remote_ip != null
| filter not incidr(action_remote_ip, "10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8")
| iploc action_remote_ip loc_country
| comp count() as connections, count_distinct(agent_hostname) as hosts by loc_country
| sort desc connections
| limit 10
```

## When to use

Per-country connection count + unique-host count. Useful for spotting unexpected countries in the traffic mix (could indicate compromised egress, VPN routing changes, or attacker C2 in foreign jurisdictions).

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
