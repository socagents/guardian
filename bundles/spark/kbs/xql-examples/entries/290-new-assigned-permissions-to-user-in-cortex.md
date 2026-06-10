---
id: XQL-290-b3022e78
title: New assigned permissions to user in cortex
category: investigation
dataset: management_auditing
tags:
  - filter
  - alter
  - fields
  - sort
  - management_auditing
  - source:dataset
  - operator-authored
---

# New assigned permissions to user in cortex

**Dataset**: `management_auditing`

```sql
dataset = management_auditing 
| filter subtype = "User Permissions Assigned"
| alter targetUser=arrayindex(regextract(description,"(.*?)\swas"),0), newRole=arrayindex(regextract(description,"role\s(.*?)$"),0)
| fields _time, subtype , user_name , targetUser , newRole , description,* 
| sort desc _time
```

## When to use

Identifies who assigned the user permissions and to whom, and includes the new roles and relevant user information

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
