---
id: XQL-367-23f30ad2
title: Auth Story Sources
category: investigation
dataset: authentication_story
tags:
  - preset
  - comp
  - arrayexpand
  - authentication_story
  - source:preset
  - operator-authored
---

# Auth Story Sources

**Dataset**: `authentication_story`

```sql
preset = authentication_story
| comp values(associated_products) as sources
| arrayexpand sources
```

## When to use

Lists all sources that feed the auth_story preset

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
