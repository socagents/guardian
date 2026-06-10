---
id: XQL-292-9874c3e6
title: New Dataset Views Created
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

# New Dataset Views Created

**Dataset**: `management_auditing`

```sql
dataset = management_auditing 
| filter subtype = "Create Dataset View"
| alter datasetViewName=arrayindex(regextract(description,"View\s(.*?)\s"),0)
|fields _time, subtype ,user_name , datasetViewName , description,*
|sort desc _time
```

## When to use

Identifies the new dataset views created, and includes the user who created the dataset view and relevant timestamp details

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
