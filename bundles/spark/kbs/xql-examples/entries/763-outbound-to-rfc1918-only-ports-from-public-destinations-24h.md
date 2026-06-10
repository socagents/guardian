---
id: XQL-763-c4b27d2d
title: Outbound to RFC1918-only ports from public destinations (24h)
category: detection
dataset: xdr_data
tags:
  - filter
  - fields
  - sort
  - limit
  - xdr_data
  - network
  - incidr
---

# Outbound to RFC1918-only ports from public destinations (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK and action_remote_port in (445, 139, 135, 3389)
| filter not incidr(action_remote_ip, "10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8")
| fields _time, agent_hostname, action_remote_ip, action_remote_port
| sort desc _time
| limit 10
```

## When to use

Connections to Windows-internal ports (SMB 445, NetBIOS 139, RPC 135, RDP 3389) on PUBLIC IPs. Highly suspicious — these ports should never traverse the internet. Misconfiguration or attacker activity.

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
