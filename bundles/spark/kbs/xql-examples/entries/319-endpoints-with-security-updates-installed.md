---
id: XQL-319-d2f378e8
title: Endpoints with Security Updates Installed
category: investigation
dataset: host_inventory_kbs
tags:
  - preset
  - filter
  - fields
  - comp
  - sort
  - host_inventory_kbs
  - source:preset
  - operator-authored
---

# Endpoints with Security Updates Installed

**Dataset**: `host_inventory_kbs`

```sql
preset = host_inventory_kbs
| filter description = "Security Update"
| fields endpoint_name, endpoint_type, name
| comp count() as kb by name
| sort desc name
```

## When to use

Counts the number of endpoints that have security updates applied and provides the specific updates and the number of endpoints using each to ensure patch management visibility

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
