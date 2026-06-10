---
id: XQL-306-3c86ff3e
title: Agent Audit Quota Exceeded
category: investigation
dataset: agent_auditing
tags:
  - filter
  - fields
  - sort
  - agent_auditing
  - source:dataset
  - operator-authored
---

# Agent Audit Quota Exceeded

**Dataset**: `agent_auditing`

```sql
dataset = agent_auditing
| filter agent_auditing_subtype=ENUM.AGENT_AUDIT_QUOTA_EXCEEDED
| fields _time, agent_auditing_subtype , endpoint_name , endpoint_id ,xdr_agent_version , domain, description,*
| sort desc _time
```

## When to use

Lists the agents that exceeded their audit quota, and includes endpoint information and version details

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
