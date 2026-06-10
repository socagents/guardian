---
id: XQL-766-a9183e8e
title: Top source/destination IP pairs by data volume (24h)
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

# Top source/destination IP pairs by data volume (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK
| comp sum(action_total_upload) as bytes_out, sum(action_total_download) as bytes_in, count() as cnt by action_local_ip, action_remote_ip
| sort desc bytes_out
| limit 10
```

## When to use

Top network conversation pairs by outbound volume. Useful for understanding chatty workloads + identifying potential exfiltration flows.

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
