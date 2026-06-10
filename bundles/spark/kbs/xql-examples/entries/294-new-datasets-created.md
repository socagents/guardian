---
id: XQL-294-990fd7da
title: New Datasets Created
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

# New Datasets Created

**Dataset**: `management_auditing`

```sql
dataset = management_auditing 
| filter subtype = "Create dataset"
| alter datasetName=arrayindex(regextract(description , "Dataset\s(.*?)\sof"),0), datasetType=arrayindex(regextract(description , "type\s(.*?)\swas"),0)
| fields _time, user_name, subtype , datasetType ,datasetName , description,*
| sort desc _time
```

## When to use

Lists the new datasets created, and provides the dataset type, user information, and timestamp details

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
