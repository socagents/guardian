---
id: XQL-712-533d4d23
title: Outbound connections to public IPs from internal hosts (24h)
category: detection
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

# Outbound connections to public IPs from internal hosts (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK
| filter not incidr(action_remote_ip, "10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8, 169.254.0.0/16")
| comp count() as connections, sum(action_total_upload) as upload_bytes by agent_hostname, action_remote_ip
| sort desc upload_bytes
| limit 10
```

## When to use

Outbound connections to public (non-RFC1918) IP space. Useful for surfacing legitimate-vs-suspicious external traffic. The `incidr` function with negation filters out internal-network traffic.

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
