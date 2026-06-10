---
id: XQL-717-e9fd6835
title: All endpoints with status + OS + agent version
category: investigation
dataset: endpoints
tags:
  - fields
  - sort
  - limit
  - endpoints
---

# All endpoints with status + OS + agent version

**Dataset**: `endpoints`

```sql
dataset = endpoints
| fields endpoint_name, endpoint_status, operating_system, agent_version, last_seen, ip_address
| sort asc last_seen
| limit 10
```

## When to use

Foundational endpoint inventory query. Returns all managed endpoints sorted by last_seen ascending so the oldest-last-seen entries surface first (stale agents).

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
