---
id: XQL-716-a57dc0aa
title: Persistence via autorun-key registry writes (24h, T1547)
category: detection
dataset: xdr_data
tags:
  - filter
  - fields
  - sort
  - limit
  - xdr_data
  - registry
  - T1547
---

# Persistence via autorun-key registry writes (24h, T1547)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.REGISTRY
| filter action_registry_key_name contains "\\Run" or action_registry_key_name contains "\\RunOnce" or action_registry_key_name contains "\\Image File Execution Options"
| fields _time, agent_hostname, actor_process_image_name, action_registry_key_name, action_registry_value_name
| sort desc _time
| limit 10
```

## When to use

MITRE T1547 — Boot or Logon Autostart Execution. Captures writes to the canonical autorun registry locations + Image File Execution Options (a debugger-hijack persistence vector).

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
