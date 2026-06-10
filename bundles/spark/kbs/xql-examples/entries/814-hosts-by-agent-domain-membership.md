---
id: XQL-814-e95a47e9
title: Hosts by agent-domain membership
category: investigation
dataset: host_inventory
tags:
  - filter
  - comp
  - sort
  - limit
  - host_inventory
---

# Hosts by agent-domain membership

**Dataset**: `host_inventory`

```sql
dataset = host_inventory
| filter agent_domain != null
| comp count() as cnt by agent_domain
| sort desc cnt
| limit 10
```

## When to use

AD domain membership distribution. Field is `agent_domain` in this tenant.

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
