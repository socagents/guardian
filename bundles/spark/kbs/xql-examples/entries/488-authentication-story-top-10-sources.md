---
id: XQL-488-3d2b3ecb
title: Authentication Story Top 10 Sources
category: investigation
dataset: authentication_story
tags:
  - preset
  - comp
  - sort
  - limit
  - authentication_story
  - source:preset
  - operator-authored
---

# Authentication Story Top 10 Sources

**Dataset**: `authentication_story`

```sql
preset = authentication_story
| comp count() as event_count by associated_products
| sort desc event_count
| limit 10
```

## When to use

Identifies the top 10 sources for the authentication_story preset

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
