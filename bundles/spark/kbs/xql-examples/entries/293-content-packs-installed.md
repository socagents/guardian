---
id: XQL-293-dcb813f7
title: Content Packs Installed
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

# Content Packs Installed

**Dataset**: `management_auditing`

```sql
dataset = management_auditing 
| filter subtype="Install - ContentPack"
| fields _time, subtype , user_name , description,*
| sort desc _time
```

## When to use

Lists the new content packs installed with the user details and timestamp information

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
