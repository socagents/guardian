---
id: XQL-328-58faee20
title: Collectors in Error State
category: investigation
dataset: collection_auditing
tags:
  - filter
  - comp
  - collection_auditing
  - source:dataset
  - operator-authored
---

# Collectors in Error State

**Dataset**: `collection_auditing`

```sql
dataset = collection_auditing
| filter classification = "Error"
| comp latest(_time) by collector_type , instance , classification ,description
```

## When to use

Lists the data collectors in an error state and includes the latest timestamp and description of the issue to help identify malfunctioning data collectors in need of attention

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
