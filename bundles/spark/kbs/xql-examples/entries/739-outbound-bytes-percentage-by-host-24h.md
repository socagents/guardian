---
id: XQL-739-b747c169
title: Outbound bytes percentage by host (24h)
category: detection
dataset: xdr_data
tags:
  - filter
  - comp
  - alter
  - sort
  - limit
  - xdr_data
  - network
  - exfil
  - math
---

# Outbound bytes percentage by host (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK
| comp sum(action_total_upload) as upload, sum(action_total_download) as download by agent_hostname
| alter total_bytes = add(upload, download)
| filter total_bytes > 0
| alter upload_pct = multiply(divide(upload, total_bytes), 100)
| sort desc upload_pct
| limit 10
```

## When to use

Computes upload/download ratio per host using XQL math functions (add, divide, multiply). High upload_pct = exfiltration signal — host sending much more than receiving.

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
