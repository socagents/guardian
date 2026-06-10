---
id: XQL-297-7a534e2a
title: Deleted Dashboards
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

# Deleted Dashboards

**Dataset**: `management_auditing`

```sql
dataset = management_auditing
| filter subtype="Delete Dashboard"
| fields _time, user_name , subtype , description,*
| sort desc _time
```

## When to use

Lists the dashboards deleted and provides the user and timestamp of the action

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
