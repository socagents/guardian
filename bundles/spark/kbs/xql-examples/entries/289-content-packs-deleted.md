---
id: XQL-289-c0711568
title: Content Packs Deleted
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

# Content Packs Deleted

**Dataset**: `management_auditing`

```sql
dataset = management_auditing 
| filter subtype="Delete - ContentPack"
| fields _time, subtype , description  , user_name , email,*
| sort desc _time
```

## When to use

Identifies the content packs deleted and includes relevant details, such as the user, timestamp, and description

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
