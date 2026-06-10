---
id: XQL-368-e0bb2a79
title: Auth Story Failed Clients
category: investigation
dataset: authentication_story
tags:
  - preset
  - filter
  - comp
  - sort
  - limit
  - authentication_story
  - source:preset
  - operator-authored
---

# Auth Story Failed Clients

**Dataset**: `authentication_story`

```sql
preset = authentication_story
| filter auth_outcome = "FAILURE"
| comp count(auth_client) as failed_count by auth_client
| sort desc failed_count
| limit 5
```

## When to use

Lists the top 5 clients failing to authenticate

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
