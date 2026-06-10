---
id: XQL-324-bef46220
title: Installed Applications Count
category: investigation
dataset: host_inventory_applications
tags:
  - preset
  - comp
  - sort
  - host_inventory_applications
  - source:preset
  - operator-authored
---

# Installed Applications Count

**Dataset**: `host_inventory_applications`

```sql
preset = host_inventory_applications
| comp count() as application_counter by application_name, version
| sort desc application_counter
```

## When to use

Counts all installed applications across the environment to ensure visibility into application deployment and supporting compliance with approved software lists

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
