---
id: XQL-767-2ff8fb81
title: Agent version distribution
category: investigation
dataset: endpoints
tags:
  - comp
  - sort
  - limit
  - endpoints
---

# Agent version distribution

**Dataset**: `endpoints`

```sql
dataset = endpoints
| comp count() as cnt by agent_version, platform
| sort desc cnt
| limit 10
```

## When to use

Agent version landscape across the fleet. Useful for rollout-progress tracking + spotting outdated agents that need upgrading.

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
