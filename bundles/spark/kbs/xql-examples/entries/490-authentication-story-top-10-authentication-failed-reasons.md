---
id: XQL-490-6dd2c22b
title: Authentication Story Top 10 Authentication Failed Reasons
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

# Authentication Story Top 10 Authentication Failed Reasons

**Dataset**: `authentication_story`

```sql
preset = authentication_story
| filter auth_outcome = "FAILURE"
| comp count(auth_outcome_reason) as failed_count by auth_outcome_reason
| sort desc failed_count
| limit 10
```

## When to use

Lists the top 10 reasons for failing to authenticate in the authentication_story preset

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
