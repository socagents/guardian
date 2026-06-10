---
id: XQL-260-199a6936
title: Secret Manager component modification
category: investigation
dataset: cloud_audit_logs
tags:
  - filter
  - cloud_audit_logs
  - source:dataset
  - operator-authored
---

# Secret Manager component modification

**Dataset**: `cloud_audit_logs`

```sql
// Cloud provider - Any
// Cloud component - Secret
dataset = cloud_audit_logs |
filter operation_name_orig contains "secret" and (operation_name = Delete or operation_name = Create or operation_name = Modify or operation_name = Put) // Filter the logs for action on the secrets component
```

## When to use

Displays modification actions performed on the Secret Manager component.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
