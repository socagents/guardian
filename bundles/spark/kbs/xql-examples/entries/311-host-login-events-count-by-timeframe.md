---
id: XQL-311-cf4b442c
title: Host Login Events Count by Timeframe
category: investigation
dataset: xdr_login_events
tags:
  - preset
  - filter
  - comp
  - sort
  - fields
  - xdr_login_events
  - source:preset
  - operator-authored
---

# Host Login Events Count by Timeframe

**Dataset**: `xdr_login_events`

```sql
preset = xdr_login_events
| filter array_length(assigned_privileges ) > 0 or elevated_token != null
| filter agent_hostname in($host)
| comp count() as login_count by agent_hostname, agent_ip_addresses, agent_os_type
| sort desc login_count
| fields agent_hostname, agent_ip_addresses, agent_os_type, login_count
```

## When to use

Counts log in events per host within a defined timeframe to help monitor authentication activity and identify potential security concerns related to abnormal log in behaviors

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
