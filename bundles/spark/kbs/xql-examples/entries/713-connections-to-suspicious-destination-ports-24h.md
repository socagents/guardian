---
id: XQL-713-222973ca
title: Connections to suspicious destination ports (24h)
category: detection
dataset: xdr_data
tags:
  - filter
  - comp
  - sort
  - limit
  - xdr_data
  - network
  - c2
---

# Connections to suspicious destination ports (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK
| filter action_remote_port in (4444, 1337, 8080, 9001, 9050, 3389, 5900, 23, 1433)
| comp count() as connections by agent_hostname, action_remote_ip, action_remote_port
| sort desc connections
| limit 10
```

## When to use

Connections to commonly-abused destination ports — Metasploit defaults (4444), Tor relay ports (9001/9050), legacy services (telnet 23, SQL Server 1433), RDP/VNC. Triage candidates.

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
