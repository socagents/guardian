---
id: XQL-264-9ee09b28
title: App Service component modification
category: investigation
dataset: cloud_audit_logs
tags:
  - filter
  - comp
  - cloud_audit_logs
  - source:dataset
  - operator-authored
---

# App Service component modification

**Dataset**: `cloud_audit_logs`

```sql
// Cloud provider - Azure
// Cloud component - AppService
config case_sensitive = false | 
dataset = cloud_audit_logs |
filter cloud_provider = Azure and operation_name_orig in ("MICROSOFT.WEB/*/WRITE","MICROSOFT.WEB/*/DELETE","MICROSOFT.WEB/*/CREATE") // Filter for privileged actions on Azure App Service
| comp count(_time) as PrivilegedActions by operation_name_orig ,referenced_resource_name // Count the operations performed on App Service Resource
```

## When to use

Displays suspicious activities performed in the App Service component.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
