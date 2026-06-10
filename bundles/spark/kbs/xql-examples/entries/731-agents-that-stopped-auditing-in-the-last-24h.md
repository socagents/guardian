---
id: XQL-731-da5a4454
title: Agents that stopped auditing in the last 24h
category: detection
dataset: agent_auditing
tags:
  - filter
  - fields
  - sort
  - limit
  - agent_auditing
---

# Agents that stopped auditing in the last 24h

**Dataset**: `agent_auditing`

```sql
config timeframe = 24h
| dataset = agent_auditing
| filter agent_auditing_subtype = ENUM.AGENT_AUDIT_STOP
| fields _time, endpoint_name, endpoint_id, xdr_agent_version, description
| sort desc _time
| limit 10
```

## When to use

Agent audit-stop events — when the XDR agent stopped its self-audit. Can indicate normal stop (uninstall, restart) or attacker action to disable visibility. Triage candidates.

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
