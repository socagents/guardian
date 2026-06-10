---
id: XQL-278-d7ab7d20
title: Impossible traveler - sso
category: investigation
dataset: authentication_story
tags:
  - preset
  - filter
  - comp
  - alter
  - authentication_story
  - source:preset
  - operator-authored
---

# Impossible traveler - sso

**Dataset**: `authentication_story`

```sql
preset = authentication_story
| filter action_country != "" and action_country != "-" AND auth_outcome = "SUCCESS" AND action_country != null
| comp values(action_country) as countries by auth_identity
| alter count_distinct_action_country = array_length(countries)
| filter count_distinct_action_country > 1
```

## When to use

Display potential Impossible traveler authenticating sso from more than one country.Recommended to run hourly

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-16.
