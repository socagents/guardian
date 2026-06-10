---
id: XQL-773-4167f150
title: Failed cloud actions (7d)
category: detection
dataset: cloud_audit_logs
tags:
  - filter
  - comp
  - sort
  - limit
  - cloud_audit_logs
  - cloud
---

# Failed cloud actions (7d)

**Dataset**: `cloud_audit_logs`

```sql
config timeframe = 7d
| dataset = cloud_audit_logs
| filter operation_status != "success"
| comp count() as cnt by cloud_provider, operation_name, operation_status
| sort desc cnt
| limit 10
```

## When to use

Failed cloud operations by provider/op/status. High failure counts on sensitive ops (DeleteRole, AssumeRole) often indicate probing or misconfig.

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
