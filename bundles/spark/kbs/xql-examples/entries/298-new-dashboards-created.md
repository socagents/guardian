---
id: XQL-298-91789324
title: New Dashboards Created
category: investigation
dataset: management_auditing
tags:
  - filter
  - fields
  - sort
  - management_auditing
  - source:dataset
  - operator-authored
---

# New Dashboards Created

**Dataset**: `management_auditing`

```sql
dataset = management_auditing
| filter subtype="Create New Dashboard"
| fields _time, user_name , subtype , description,*
| sort desc _time
```

## When to use

Lists the new dashboards created, and provides the user and timestamp of the action

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
