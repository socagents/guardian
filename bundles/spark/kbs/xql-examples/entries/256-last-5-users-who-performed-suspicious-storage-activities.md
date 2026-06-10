---
id: XQL-256-3e221592
title: Last 5 users who performed suspicious storage activities.
category: investigation
dataset: cloud_audit_logs
tags:
  - filter
  - comp
  - sort
  - limit
  - cloud_audit_logs
  - source:dataset
  - operator-authored
---

# Last 5 users who performed suspicious storage activities.

**Dataset**: `cloud_audit_logs`

```sql
// Cloud provider - GCP
// Cloud component - Storage
config case_sensitive = false 
| dataset = cloud_audit_logs // Query the normalized cloud audit logs table
| filter resource_type = CloudStorage and operation_name_orig in ("storage.setIamPermissions","storage.buckets.delete","storage.buckets.update","storage.buckets.create") // Query for suspicious storage actions
| comp count(_time) as LeastUsers by identity_name // Count the users that made the actions and sort for the least 5
| sort asc LeastUsers 
| limit 5
```

## When to use

Displays last 5 users who performed suspicious storage activities.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
