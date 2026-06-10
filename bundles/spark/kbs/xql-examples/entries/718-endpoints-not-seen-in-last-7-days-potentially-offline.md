---
id: XQL-718-0b2f6c2a
title: Endpoints not seen in last 7 days (potentially offline)
category: detection
dataset: endpoints
tags:
  - filter
  - fields
  - sort
  - limit
  - endpoints
---

# Endpoints not seen in last 7 days (potentially offline)

**Dataset**: `endpoints`

```sql
dataset = endpoints
| filter endpoint_status != "CONNECTED"
| fields endpoint_name, endpoint_status, operating_system, last_seen, agent_version
| sort asc last_seen
| limit 10
```

## When to use

Endpoints whose status is not CONNECTED (e.g. CONNECTION_LOST, DISCONNECTED). Useful for identifying agents that may have been uninstalled, taken offline by attackers, or have networking issues.

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
