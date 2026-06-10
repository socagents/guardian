---
id: XQL-318-3dc14b75
title: Installed Applications in Environment
category: investigation
dataset: host_inventory_applications
tags:
  - preset
  - fields
  - host_inventory_applications
  - source:preset
  - operator-authored
---

# Installed Applications in Environment

**Dataset**: `host_inventory_applications`

```sql
preset = host_inventory_applications
| fields install_date, vendor , application_name, raw_version , platform,*
```

## When to use

Lists all applications currently installed on endpoints to help maintain software inventory, detect unauthorized software, and manage software compliance

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
