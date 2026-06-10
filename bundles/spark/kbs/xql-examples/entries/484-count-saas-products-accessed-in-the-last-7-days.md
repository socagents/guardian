---
id: XQL-484-66da93b8
title: Count SaaS Products Accessed in the Last 7 Days
category: investigation
dataset: saas_audit_logs
tags:
  - config
  - comp
  - fields
  - saas_audit_logs
  - source:dataset
  - operator-authored
---

# Count SaaS Products Accessed in the Last 7 Days

**Dataset**: `saas_audit_logs`

```sql
config timeframe = 7d
| dataset = saas_audit_logs
| comp count_distinct(product) by product
| fields product, *
```

## When to use

Counts the number of distinct SaaS products accessed in the Last 7 Days

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
