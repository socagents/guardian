---
id: XQL-736-621881cd
title: Distinct users per host (24h)
category: investigation
dataset: xdr_data
tags:
  - filter
  - comp
  - sort
  - limit
  - xdr_data
  - user
---

# Distinct users per host (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter actor_effective_username != null
| comp count_distinct(actor_effective_username) as unique_users, values(actor_effective_username) as users by agent_hostname
| sort desc unique_users
| limit 10
```

## When to use

How many distinct users were active per host? `count_distinct` + `values()` together give both the count and the list. Useful for finding shared-account hosts or atypical user activity.

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
