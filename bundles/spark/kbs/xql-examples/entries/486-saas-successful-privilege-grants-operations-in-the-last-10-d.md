---
id: XQL-486-c41413b9
title: SaaS Successful Privilege Grants Operations in the Last 10 Days
category: investigation
dataset: saas_audit_logs
tags:
  - config
  - filter
  - alter
  - fields
  - saas_audit_logs
  - source:dataset
  - operator-authored
---

# SaaS Successful Privilege Grants Operations in the Last 10 Days

**Dataset**: `saas_audit_logs`

```sql
config timeframe = 10d
| dataset = saas_audit_logs
| filter operation_name = "PRIVILEGE_GRANT"
| filter operation_status = "SUCCESS"
| alter user = identity_normalized -> username
| fields user, operation_name_orig, *
```

## When to use

Lists the successful privilege grant operations in SaaS environments performed in the last 10 days

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
