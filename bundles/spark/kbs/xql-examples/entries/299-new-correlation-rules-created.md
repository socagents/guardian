---
id: XQL-299-40cabc14
title: New Correlation Rules Created
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

# New Correlation Rules Created

**Dataset**: `management_auditing`

```sql
dataset = management_auditing
| filter subtype = "Create" and description ~= "Correlations rule created"
| alter correlationName=arrayindex(regextract(description,"name:\s(.*?)\,"),0)
| fields _time, subtype , description , correlationName , user_name , user_roles,*
| sort desc _time
```

## When to use

Lists the new correlation rules created, and provides the correlation rule name, user information, and timestamp

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
