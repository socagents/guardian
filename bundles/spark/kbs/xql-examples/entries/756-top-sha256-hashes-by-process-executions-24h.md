---
id: XQL-756-edca7344
title: Top SHA256 hashes by process executions (24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - comp
  - sort
  - limit
  - xdr_data
  - process
  - hash
---

# Top SHA256 hashes by process executions (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START and action_process_image_sha256 != null
| comp count() as cnt, count_distinct(agent_hostname) as hosts by action_process_image_sha256, action_process_image_name
| sort desc cnt
| limit 10
```

## When to use

Most-executed binaries by hash. The SHA256 is reputation-lookup-ready (VT, ThreatGrid, internal allowlists). Pair with host-count for blast-radius assessment.

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
