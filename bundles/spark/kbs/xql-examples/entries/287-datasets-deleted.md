---
id: XQL-287-ab4519ac
title: Datasets Deleted
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

# Datasets Deleted

**Dataset**: `management_auditing`

```sql
dataset = management_auditing 
| filter subtype="Delete dataset"
| alter datasetName=arrayindex(regextract(description , "Dataset\s(.*?)\sof"),0), datasetType=arrayindex(regextract(description , "type\s(.*?)\swas"),0)
| fields _time , user_name , user_roles , subtype , datasetType , datasetType ,description 
| sort desc _time
```

## When to use

Identifies the datasets deleted and provides the timestamp, user who performed the action, user roles, and dataset details

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
