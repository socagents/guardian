---
id: XQL-302-2abe9eee
title: Failed Agent Policy Update (Last 24 Hours)
category: investigation
dataset: agent_auditing
tags:
  - config
  - filter
  - fields
  - agent_auditing
  - source:dataset
  - operator-authored
---

# Failed Agent Policy Update (Last 24 Hours)

**Dataset**: `agent_auditing`

```sql
config timeframe =24H
|dataset = agent_auditing
| filter agent_auditing_subtype=ENUM.AGENT_AUDIT_POLICY_UPDATE and agent_auditing_result=ENUM.AGENT_AUDIT_FAIL
| fields _time, agent_auditing_subtype , endpoint_name , endpoint_id ,xdr_agent_version , domain , agent_auditing_result , description,*
```

## When to use

Lists the agents that had a failed policy update in the last 24 hours, and provides endpoint information and version details

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
