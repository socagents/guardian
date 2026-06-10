---
id: XQL-326-10ed9036
title: Data Sources by Collector Type
category: investigation
dataset: metrics_view
tags:
  - preset
  - filter
  - alter
  - dedup
  - fields
  - metrics_view
  - source:preset
  - operator-authored
---

# Data Sources by Collector Type

**Dataset**: `metrics_view`

```sql
preset = metrics_view
| filter _collector_type in ($collector_type)
| alter ven_product = concat(_vendor, " (", _product , ") ")
| dedup ven_product
| fields _collector_type, ven_product
```

## When to use

Lists the data sources ingested using a specified collector type to provide details on vendors and products associated with each collector type

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
