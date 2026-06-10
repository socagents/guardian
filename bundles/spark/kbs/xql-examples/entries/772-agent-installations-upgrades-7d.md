---
id: XQL-772-2d5d7d5b
title: Agent installations + upgrades (7d)
category: investigation
dataset: agent_auditing
tags:
  - filter
  - comp
  - sort
  - limit
  - agent_auditing
---

# Agent installations + upgrades (7d)

**Dataset**: `agent_auditing`

```sql
config timeframe = 7d
| dataset = agent_auditing
| filter agent_auditing_subtype in (ENUM.AGENT_AUDIT_INSTALL, ENUM.AGENT_AUDIT_UPGRADE)
| comp count() as cnt by endpoint_name, agent_auditing_subtype
| sort desc cnt
| limit 10
```

## When to use

Agent install + upgrade activity. Reveals rollout progress + endpoints that have had unusual lifecycle activity.

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
