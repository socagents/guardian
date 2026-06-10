---
id: XQL-757-8c8424a4
title: Rare process hashes — fewer than 3 executions (24h)
category: detection
dataset: xdr_data
tags:
  - filter
  - comp
  - sort
  - limit
  - xdr_data
  - process
  - rare
  - hash
---

# Rare process hashes — fewer than 3 executions (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START and action_process_image_sha256 != null
| comp count() as cnt by action_process_image_sha256, action_process_image_name
| filter cnt < 3
| sort asc cnt
| limit 10
```

## When to use

Rare-by-hash executions. New + unfamiliar binaries surface as low-count rows. The pattern relies on hash distinctiveness to catch packed/repacked malware that varies its filename.

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
