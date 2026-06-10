---
id: XQL-750-6c82ccc7
title: Network events to specific port across all hosts (1h)
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

# Network events to specific port across all hosts (1h)

**Dataset**: `xdr_data`

```sql
config timeframe = 1h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK and action_remote_port = 443
| comp count() as cnt by agent_hostname
| sort desc cnt
| limit 10
```

## When to use

Per-host HTTPS connection count over the last hour. Short timeframe + simple aggregation — useful as a real-time signal during incident response.

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
