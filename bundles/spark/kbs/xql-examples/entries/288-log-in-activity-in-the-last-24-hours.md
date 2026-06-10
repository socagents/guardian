---
id: XQL-288-fb415026
title: Log in Activity in the Last 24 Hours
category: investigation
dataset: management_auditing
tags:
  - config
  - filter
  - fields
  - sort
  - management_auditing
  - source:dataset
  - operator-authored
---

# Log in Activity in the Last 24 Hours

**Dataset**: `management_auditing`

```sql
config timeframe = 24H 
| dataset = management_auditing 
| filter subtype="Login"
| fields _time , subtype , user_name , user_roles , source_ip ,email , user_agent,*
| sort desc _time
```

## When to use

Displays the users who performed a log in within the last 24 hours and includes the user information, source IP, and timestamp

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
