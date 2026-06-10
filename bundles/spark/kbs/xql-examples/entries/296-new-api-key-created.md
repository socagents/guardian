---
id: XQL-296-5f344456
title: New API Key Created
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

# New API Key Created

**Dataset**: `management_auditing`

```sql
dataset = management_auditing
| filter subtype = "Add New Key"
| alter apiKeyID=arrayindex(regextract(description ,"ID\s(\d+)\swas"),0)
| fields _time, user_name , subtype , apiKeyID ,description,*
| sort desc _time
```

## When to use

Finds all the created API keys, and shows who created that API key, when, and what role is accosiated with that key

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
