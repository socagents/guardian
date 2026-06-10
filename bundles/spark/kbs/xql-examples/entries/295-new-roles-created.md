---
id: XQL-295-242f5dff
title: New Roles Created
category: investigation
dataset: management_auditing
tags:
  - filter
  - fields
  - management_auditing
  - source:dataset
  - operator-authored
---

# New Roles Created

**Dataset**: `management_auditing`

```sql
dataset = management_auditing
| filter subtype="Role Created"
| fields _time , user_name , user_roles ,description,*
```

## When to use

Identifies the new roles created and the user who created them

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
