---
id: XQL-321-2837a358
title: Installed Browser Count in Environment
category: investigation
dataset: host_inventory_applications
tags:
  - preset
  - filter
  - comp
  - host_inventory_applications
  - source:preset
  - operator-authored
---

# Installed Browser Count in Environment

**Dataset**: `host_inventory_applications`

```sql
preset = host_inventory_applications
| filter application_name ~= "Google Chrome|Microsoft Edge|Firefox|Internet Explore"
| comp count() as version_counter by version, application_name
```

## When to use

Counts the different browsers installed on the endpoints, which provides insights into software diversity and potential risks from outdated or unapproved browser versions

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
