---
id: XQL-485-e917a850
title: SaaS Operations Performed in the Last 7 Days
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

# SaaS Operations Performed in the Last 7 Days

**Dataset**: `saas_audit_logs`

```sql
config timeframe = 7d
| dataset = saas_audit_logs
| comp count_distinct(operation_name) by operation_name
| fields operation_name, *
```

## When to use

Lists the number of distinct operations in SaaS environments performed by the name of the operation in the Last 7 Days

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
